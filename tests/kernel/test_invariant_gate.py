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
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), GrafoEstado())
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
