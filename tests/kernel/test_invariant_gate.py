"""Testes unitários para o InvariantGate (Portão 3)."""

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import (
    PapelAutor,
    StatusQuestion,
    StatusTask,
    TipoAresta,
    TipoNo,
)
from graphow.kernel.invariant_gate import InvariantGate
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
)


def test_invariant_gate_aprovacao_nominal() -> None:
    """Testa aprovação de patch que não viola regras relacionais."""
    gate = InvariantGate()
    estado = GrafoEstado(nos={"sess-1": NoGrafo("sess-1", TipoNo.SESSAO, "Sessao 1")})
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e-prod-t1", value={
                "id": "e-prod-t1", "origem_id": "sess-1", "destino_id": "t1", "tipo": TipoAresta.PRODUZ.value
            }),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is True


def test_invariant_gate_detecta_ciclo_dependencia_edge_case() -> None:
    """Caso de borda: rejeita aresta que cria ciclo A -> B -> C -> A em depende_de."""
    gate = InvariantGate()
    estado = GrafoEstado(
        nos={
            "t1": NoGrafo("t1", TipoNo.TASK, "T1"),
            "t2": NoGrafo("t2", TipoNo.TASK, "T2"),
            "t3": NoGrafo("t3", TipoNo.TASK, "T3"),
        },
        arestas={
            "e1": ArestaGrafo("e1", "t1", "t2", TipoAresta.DEPENDE_DE),
            "e2": ArestaGrafo("e2", "t2", "t3", TipoAresta.DEPENDE_DE),
        },
    )
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e_ciclo", value={
                "id": "e_ciclo", "origem_id": "t3", "destino_id": "t1", "tipo": TipoAresta.DEPENDE_DE.value
            }),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "ciclo proibido" in str(res.mensagem_erro)


def test_invariant_gate_bloqueia_conclusao_com_question_aberta_edge_case() -> None:
    """Caso de borda: rejeita conclusão de Task que tem Question aberta bloqueante."""
    gate = InvariantGate()
    estado = GrafoEstado(
        nos={
            "t1": NoGrafo("t1", TipoNo.TASK, "T1"),
            "q1": NoGrafo("q1", TipoNo.QUESTION, "Dúvida", propriedades={"status": StatusQuestion.ABERTA.value}),
        },
        arestas={
            "e_bloq": ArestaGrafo("e_bloq", "q1", "t1", TipoAresta.BLOQUEIA),
        },
    )
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.CONCLUIDO.value),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "Question aberta bloqueante" in str(res.mensagem_erro)


def test_invariant_gate_rejeita_escrita_com_lock_ativo_de_outro_autor_edge_case() -> None:
    """Caso de borda: rejeita mutação quando a Task está travada por outro escritor."""
    gate = InvariantGate()
    estado = GrafoEstado(nos={"t1": NoGrafo("t1", TipoNo.TASK, "T1")})
    locks = {"t1": "outro-agente"}

    dados = DadosPropostaPatch(
        autor="agente-intruso",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.EM_ANDAMENTO.value),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado, locks_ativos=locks)
    assert res.aprovado is False
    assert "bloqueado para escrita pelo autor 'outro-agente'" in str(res.mensagem_erro)


def _estado_com_duas_tarefas() -> GrafoEstado:
    """Duas Tasks, t2 já dependente de t1."""
    return GrafoEstado(
        nos={"t1": NoGrafo("t1", TipoNo.TASK, "T1"), "t2": NoGrafo("t2", TipoNo.TASK, "T2")},
        arestas={"d-antiga": ArestaGrafo("d-antiga", "t2", "t1", TipoAresta.DEPENDE_DE)},
    )


def _validar_como_planejador(operacao: ItemPatch, estado: GrafoEstado) -> bool:
    """Valida a operação do planejador com t2 travada por um executor."""
    dados = DadosPropostaPatch(autor="planejador-b", papel=PapelAutor.PLANEJADOR, operacoes=[operacao])
    return InvariantGate().validar(PropostaPatch.criar(dados), estado, locks_ativos={"t2": "executor-a"}).aprovado


def test_planejador_nao_redefine_a_tarefa_travada_por_outro_edge_case() -> None:
    """Caso de borda: o lock só olhava `/nos/...`, e o planejador mudava as dependências da tarefa em andamento."""
    estado = _estado_com_duas_tarefas()
    nova = ItemPatch(
        op=OperacaoPatch.ADD,
        path="/arestas/d-nova",
        value={"id": "d-nova", "origem_id": "t1", "destino_id": "t2", "tipo": TipoAresta.DEPENDE_DE.value},
    )
    remocao = ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/d-antiga")

    assert _validar_como_planejador(nova, estado) is False
    assert _validar_como_planejador(remocao, estado) is False


def test_aresta_que_nao_redefine_a_tarefa_segue_livre_nominal() -> None:
    """A escalação e a proveniência continuam chegando à tarefa travada: `bloqueia` e `deriva_de` não a redefinem."""
    estado = _estado_com_duas_tarefas()
    bloqueio = ItemPatch(
        op=OperacaoPatch.ADD,
        path="/arestas/b1",
        value={"id": "b1", "origem_id": "q1", "destino_id": "t2", "tipo": TipoAresta.BLOQUEIA.value},
    )

    assert _validar_como_planejador(bloqueio, estado) is True
