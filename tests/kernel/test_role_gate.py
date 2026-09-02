"""Testes unitários para o RoleGate (Portão 2)."""

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
)
from graphow.kernel.role_gate import RoleGate


def test_role_gate_humano_permissao_irrestrita_nominal() -> None:
    """Testa que autor humano possui autorização ampla."""
    gate = RoleGate()
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/c1", value={"id": "c1", "tipo": TipoNo.CONSTRAINT.value}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), GrafoEstado())
    assert res.aprovado is True


def test_role_gate_rejeita_executor_editando_constraint_edge_case() -> None:
    """Caso de borda: executor tentando editar Constraint é rejeitado com mensagem descritiva."""
    gate = RoleGate()
    estado = GrafoEstado(nos={"c1": NoGrafo(id="c1", tipo=TipoNo.CONSTRAINT, rotulo="Restrição")})
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/c1/rotulo", value="Restrição burlada"),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "Constraint" in str(res.mensagem_erro)


def test_role_gate_rejeita_planejador_fechando_task_edge_case() -> None:
    """Caso de borda: planejador tentando fechar Task é rejeitado."""
    gate = RoleGate()
    estado = GrafoEstado(nos={"t1": NoGrafo(id="t1", tipo=TipoNo.TASK, rotulo="Tarefa 1")})
    dados = DadosPropostaPatch(
        autor="planejador-1",
        papel=PapelAutor.PLANEJADOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.CONCLUIDO.value),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "fechar/concluir Task" in str(res.mensagem_erro)


def test_role_gate_rejeita_executor_criando_task_edge_case() -> None:
    """Caso de borda: executor tentando criar nova Task é rejeitado."""
    gate = RoleGate()
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/t2", value={"id": "t2", "tipo": TipoNo.TASK.value}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), GrafoEstado())
    assert res.aprovado is False
    assert "não possui permissão para criar nó" in str(res.mensagem_erro)


def _montar_estado_com_projeto(nivel_autonomia: str) -> GrafoEstado:
    """Monta um estado com Projeto, Sessao e a aresta de producao que os liga."""
    projeto = NoGrafo(
        id="proj-1",
        tipo=TipoNo.PROJETO,
        rotulo="Projeto",
        propriedades={"nivel_autonomia": nivel_autonomia},
    )
    sessao = NoGrafo(id="sess-1", tipo=TipoNo.SESSAO, rotulo="Sessao")
    contencao = ArestaGrafo(id="cont-1", origem_id="proj-1", destino_id="sess-1", tipo=TipoAresta.CONTEM)
    return GrafoEstado(nos={"proj-1": projeto, "sess-1": sessao}, arestas={"cont-1": contencao})


def test_role_gate_permite_agente_em_projeto_ilimitado() -> None:
    """Valida que agentes ganham tipos adicionais dentro de um projeto ilimitado."""
    gate = RoleGate()
    estado = _montar_estado_com_projeto("ilimitado")
    aresta_producao = {
        "id": "prod-t2",
        "origem_id": "sess-1",
        "destino_id": "t2",
        "tipo": TipoAresta.PRODUZ.value,
    }
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/t2",
                value={"id": "t2", "tipo": TipoNo.TASK.value, "origem_id": "sess-1"},
            ),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/prod-t2", value=aresta_producao),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is True


def test_role_gate_autonomia_ilimitada_nao_libera_constraint_edge_case() -> None:
    """Caso de borda: nem sob autonomia ilimitada um agente cria Constraint."""
    gate = RoleGate()
    estado = _montar_estado_com_projeto("ilimitado")
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/c9",
                value={"id": "c9", "tipo": TipoNo.CONSTRAINT.value, "origem_id": "sess-1"},
            ),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "Constraint" in str(res.mensagem_erro)


def test_role_gate_autonomia_de_outro_projeto_nao_vaza_edge_case() -> None:
    """Caso de borda: um projeto ilimitado nao afrouxa operacoes fora dele."""
    gate = RoleGate()
    estado = _montar_estado_com_projeto("ilimitado")
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/t9", value={"id": "t9", "tipo": TipoNo.TASK.value}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False


def test_role_gate_rejeita_agente_em_projeto_estrito() -> None:
    """Valida que em projeto estrito as barreiras do RoleGate continuam vigentes."""
    gate = RoleGate()
    estado = _montar_estado_com_projeto("estrito")

    # Executor criando Task em projeto estrito deve ser rejeitado
    dados = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/t2", value={"id": "t2", "tipo": TipoNo.TASK.value}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False

