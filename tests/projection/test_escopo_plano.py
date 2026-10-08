"""Testes do plano aprovado lido do grafo: versões, referência, conjunto de Tasks e Goal de uma Task."""

from typing import Any

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.escopo_plano import (
    goal_da_task,
    plano_de_referencia,
    plano_vigente,
    planos_do_goal,
    seq_do_ultimo_zero,
    tasks_do_plano,
)
from graphow.projection.graph_view import GrafoView


def _no(id_no: str, tipo: TipoNo, seq: int = 1, **propriedades: Any) -> NoGrafo:
    """Nó de teste com o `seq` de criação informado."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades, ordem=OrdemNoLog(seq_criacao=seq))


def _decompoe(origem: str, destino: str) -> ArestaGrafo:
    """Aresta `decompoe` de teste, com identificador derivado dos extremos."""
    return ArestaGrafo(id=f"{origem}>{destino}", origem_id=origem, destino_id=destino, tipo=TipoAresta.DECOMPOE)


def _view(nos: list[NoGrafo], arestas: list[ArestaGrafo]) -> GrafoView:
    """Vista sobre os nós e arestas dados."""
    return GrafoView(GrafoEstado(nos={no.id: no for no in nos}, arestas={a.id: a for a in arestas}))


def _plano(versao: int, seq: int, papel: str = "humano") -> dict[str, Any]:
    """Uma entrada de `Goal.planos`."""
    return {"versao": versao, "seq": seq, "aprovado_por": "david", "papel": papel}


def _view_do_goal(planos: Any = None, **extras: Any) -> GrafoView:
    """Um Goal com a propriedade `planos` crua."""
    propriedades = dict(extras)
    if planos is not None:
        propriedades["planos"] = planos
    return _view([_no("g", TipoNo.GOAL, **propriedades)], [])


def test_goal_sem_planos_nem_vigente_nem_referencia_nominal() -> None:
    """Goal sem o campo não tem plano, e isso não é erro."""
    view = _view_do_goal()

    assert planos_do_goal(view, "g") == ()
    assert plano_vigente(view, "g") is None
    assert plano_de_referencia(view, "g") is None


def test_planos_malformados_viram_sem_plano_edge_case() -> None:
    """Caso de borda: texto, entrada sem campo, seq booleano e papel desconhecido são descartados."""
    assert planos_do_goal(_view_do_goal("aprovado"), "g") == ()
    lixo = [None, "x", {"versao": 1}, {"versao": 1, "seq": True, "papel": "humano"}, _plano(2, 5, "executor")]
    assert planos_do_goal(_view_do_goal(lixo), "g") == ()
    assert planos_do_goal(_view([], []), "inexistente") == ()


def test_vigente_e_a_ultima_e_a_referencia_e_a_ultima_humana_nominal() -> None:
    """A versão do árbitro é vigente, mas a referência do desvio continua a humana."""
    view = _view_do_goal([_plano(2, 300, "arbitro"), _plano(1, 100, "humano")])

    assert plano_vigente(view, "g").versao == 2  # type: ignore[union-attr]
    assert plano_de_referencia(view, "g").versao == 1  # type: ignore[union-attr]
    assert plano_de_referencia(view, "g").eh_humano  # type: ignore[union-attr]


def test_sem_aprovacao_humana_nao_ha_referencia_edge_case() -> None:
    """Caso de borda: só o árbitro aprovou, então toda Task é emergente."""
    view = _view_do_goal([_plano(1, 100, "arbitro")])

    assert plano_vigente(view, "g") is not None
    assert plano_de_referencia(view, "g") is None


def test_tasks_do_plano_respeitam_o_seq_da_versao_nominal() -> None:
    """Só entra a Task alcançável por `decompoe` nascida até o seq da versão."""
    nos = [
        _no("g", TipoNo.GOAL, planos=[_plano(1, 10)]),
        _no("t1", TipoNo.TASK, seq=5),
        _no("t2", TipoNo.TASK, seq=9),
        _no("t-neta", TipoNo.TASK, seq=8),
        _no("t-tarde", TipoNo.TASK, seq=11),
        _no("t-filha-da-tarde", TipoNo.TASK, seq=9),
        _no("t-solta", TipoNo.TASK, seq=2),
    ]
    arestas = [
        _decompoe("g", "t1"), _decompoe("g", "t2"), _decompoe("t1", "t-neta"),
        _decompoe("g", "t-tarde"), _decompoe("t-tarde", "t-filha-da-tarde"),
    ]
    view = _view(nos, arestas)

    conjunto = tasks_do_plano(view, "g", plano_vigente(view, "g"))  # type: ignore[arg-type]

    assert conjunto == {"t1", "t2", "t-neta"}


def test_tasks_de_uma_versao_antiga_nao_incluem_as_novas_nominal() -> None:
    """Cada versão tem o seu conjunto: a v1 não vê o que entrou na v2."""
    nos = [_no("g", TipoNo.GOAL, planos=[_plano(1, 10), _plano(2, 50)]), _no("a", TipoNo.TASK, 5), _no("b", TipoNo.TASK, 30)]
    view = _view(nos, [_decompoe("g", "a"), _decompoe("g", "b")])
    v1, v2 = planos_do_goal(view, "g")

    assert tasks_do_plano(view, "g", v1) == {"a"}
    assert tasks_do_plano(view, "g", v2) == {"a", "b"}


def test_goal_da_task_sobe_por_decompoe_nominal() -> None:
    """O Goal vem direto ou por Tasks intermediárias; sem ele, None."""
    nos = [_no("g", TipoNo.GOAL), _no("t1", TipoNo.TASK), _no("t2", TipoNo.TASK), _no("solta", TipoNo.TASK)]
    view = _view(nos, [_decompoe("g", "t1"), _decompoe("t1", "t2")])

    assert goal_da_task(view, "t1") == "g"
    assert goal_da_task(view, "t2") == "g"
    assert goal_da_task(view, "solta") is None


def test_goal_da_task_com_dois_caminhos_escolhe_o_mais_proximo_edge_case() -> None:
    """Caso de borda: o Goal de menor distância vence; no empate, o de menor identificador."""
    nos = [_no("g-a", TipoNo.GOAL), _no("g-b", TipoNo.GOAL), _no("meio", TipoNo.TASK), _no("t", TipoNo.TASK)]
    longe = _view(nos, [_decompoe("g-a", "meio"), _decompoe("meio", "t"), _decompoe("g-b", "t")])
    empate = _view(nos, [_decompoe("g-b", "t"), _decompoe("g-a", "t")])

    assert goal_da_task(longe, "t") == "g-b"
    assert goal_da_task(empate, "t") == "g-a"


def test_goal_da_task_resiste_a_ciclo_edge_case() -> None:
    """Caso de borda: um ciclo de `decompoe` entre Tasks não trava a subida."""
    nos = [_no("t1", TipoNo.TASK), _no("t2", TipoNo.TASK)]

    assert goal_da_task(_view(nos, [_decompoe("t1", "t2"), _decompoe("t2", "t1")]), "t1") is None


def test_ultimo_zero_conta_so_humano_nominal() -> None:
    """Plano e resposta de desvio humanos zeram o contador; os do árbitro não."""
    respostas = [
        {"seq": 40, "respondido_por": "david", "papel": "humano", "raiz": None, "resposta": "ok"},
        {"seq": 90, "respondido_por": "arbitro", "papel": "arbitro", "raiz": "d", "resposta": "ok"},
    ]
    view = _view_do_goal([_plano(1, 25), _plano(2, 70, "arbitro")], respostas_de_desvio=respostas)

    assert seq_do_ultimo_zero(view, "g") == 40


def test_ultimo_zero_sem_gestos_e_com_lixo_edge_case() -> None:
    """Caso de borda: sem plano humano nem resposta o zero é 0; entradas malformadas são ignoradas."""
    assert seq_do_ultimo_zero(_view_do_goal(), "g") == 0
    assert seq_do_ultimo_zero(_view_do_goal([_plano(1, 5, "arbitro")]), "g") == 0
    lixo = ["x", {"papel": "humano", "seq": "9"}, {"papel": "humano"}]
    assert seq_do_ultimo_zero(_view_do_goal(respostas_de_desvio=lixo), "g") == 0
    assert seq_do_ultimo_zero(_view_do_goal(respostas_de_desvio="texto"), "g") == 0
