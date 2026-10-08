"""Testes da projeção das propostas fora do Goal: abertas, com Projeto, origem e sessão."""

from graphow.core.escopo import ACAO_PROPOSTA_FORA_DO_GOAL
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.propostas import listar_propostas_abertas, propostas_do_goal


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, str] | None = None) -> NoGrafo:
    """Nó com rótulo igual ao id."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades or {})


def _proposta(id_no: str, **extras: str) -> NoGrafo:
    """Uma Note de proposta fora do Goal."""
    return _no(id_no, TipoNo.NOTE, {"acao": ACAO_PROPOSTA_FORA_DO_GOAL, **extras})


def _view(nos: list[NoGrafo], ligacoes: list[tuple[str, str, TipoAresta]]) -> GrafoView:
    """View sobre os nós e as arestas dadas."""
    arestas = {f"{o}->{d}": ArestaGrafo(id=f"{o}->{d}", origem_id=o, destino_id=d, tipo=t) for o, d, t in ligacoes}
    return GrafoView(GrafoEstado(nos={no.id: no for no in nos}, arestas=arestas))


def _dois_projetos() -> GrafoView:
    """Dois Projetos, cada um com Setor, Sessão e Goal; uma proposta em cada, mais as de outros estados."""
    nos = [
        _no("proj-a", TipoNo.PROJETO), _no("setor-a", TipoNo.SETOR), _no("sess-a", TipoNo.SESSAO),
        _no("goal-a", TipoNo.GOAL), _no("task-a", TipoNo.TASK), _no("ev-a", TipoNo.EVIDENCE),
        _no("proj-b", TipoNo.PROJETO), _no("setor-b", TipoNo.SETOR), _no("sess-b", TipoNo.SESSAO),
        _proposta("prop-a", status="aberta"), _proposta("prop-ev"), _proposta("prop-fechada", status="descartada"),
        _proposta("prop-aceita", status="aceita"), _proposta("prop-b", status="aberta"),
        _no("nota-comum", TipoNo.NOTE, {"acao": "condensacao_de_sessao"}),
    ]
    ligacoes = [
        ("proj-a", "setor-a", TipoAresta.CONTEM), ("setor-a", "sess-a", TipoAresta.CONTEM),
        ("proj-a", "goal-a", TipoAresta.CONTEM), ("goal-a", "task-a", TipoAresta.DECOMPOE),
        ("proj-b", "setor-b", TipoAresta.CONTEM), ("setor-b", "sess-b", TipoAresta.CONTEM),
        ("sess-a", "prop-a", TipoAresta.PRODUZ), ("sess-a", "prop-ev", TipoAresta.PRODUZ),
        ("sess-a", "prop-fechada", TipoAresta.PRODUZ), ("sess-a", "prop-aceita", TipoAresta.PRODUZ),
        ("sess-b", "prop-b", TipoAresta.PRODUZ), ("sess-a", "nota-comum", TipoAresta.PRODUZ),
        ("prop-a", "task-a", TipoAresta.DERIVA_DE), ("prop-ev", "ev-a", TipoAresta.DERIVA_DE),
        ("ev-a", "task-a", TipoAresta.DERIVA_DE),
    ]
    return _view(nos, ligacoes)


def test_lista_so_as_abertas_com_projeto_origem_e_sessao_nominal() -> None:
    """Aberta explícita e status ausente entram (sem seq no log, vale o id); aceita, descartada e Note comum ficam de fora."""
    propostas = listar_propostas_abertas(_dois_projetos())

    assert [p.id for p in propostas] == ["prop-a", "prop-b", "prop-ev"]
    primeira = propostas[0]
    assert (primeira.projeto_id, primeira.sessao_id, primeira.origens, primeira.status) == (
        "proj-a", "sess-a", ("task-a",), "aberta",
    )
    assert propostas[2].status == "aberta"


def test_filtra_pelo_projeto_nominal() -> None:
    """Com o Projeto dado, só as propostas dele aparecem."""
    assert [p.id for p in listar_propostas_abertas(_dois_projetos(), "proj-b")] == ["prop-b"]
    assert listar_propostas_abertas(_dois_projetos(), "proj-inexistente") == ()


def test_proposta_solta_sem_projeto_ainda_e_listada_edge_case() -> None:
    """Caso de borda: sem contenção até um Projeto, a proposta aparece com projeto vazio e some do filtro."""
    view = _view([_proposta("prop-solta")], [])

    assert [(p.id, p.projeto_id) for p in listar_propostas_abertas(view)] == [("prop-solta", None)]
    assert listar_propostas_abertas(view, "proj-a") == ()


def test_goal_pega_a_proposta_derivada_de_task_ou_de_evidence_dela_nominal() -> None:
    """A origem direta numa Task do Goal e a Evidence que deriva dela levam a proposta à vista do Goal."""
    assert [p.id for p in propostas_do_goal(_dois_projetos(), "goal-a")] == ["prop-a", "prop-ev"]


def test_goal_sem_origem_na_decomposicao_nao_recebe_a_proposta_edge_case() -> None:
    """Caso de borda: proposta de outro Projeto ou sem origem não aparece no Goal."""
    view = _dois_projetos()
    assert "prop-b" not in [p.id for p in propostas_do_goal(view, "goal-a")]


def test_origem_pela_propriedade_vale_para_quem_nao_pode_derivar_nominal() -> None:
    """O planejador não é dono de `deriva_de`: os ids em `origens` contam como origem, na lista e no Goal."""
    view = _view(
        [
            _no("proj", TipoNo.PROJETO), _no("goal", TipoNo.GOAL), _no("task", TipoNo.TASK), _no("sess", TipoNo.SESSAO),
            _proposta("prop-pl", origens="task"),
        ],
        [
            ("proj", "goal", TipoAresta.CONTEM), ("goal", "task", TipoAresta.DECOMPOE),
            ("proj", "sess", TipoAresta.CONTEM), ("sess", "prop-pl", TipoAresta.PRODUZ),
        ],
    )

    assert listar_propostas_abertas(view)[0].origens == ("task",)
    assert [p.id for p in propostas_do_goal(view, "goal")] == ["prop-pl"]
