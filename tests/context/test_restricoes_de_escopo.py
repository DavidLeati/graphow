"""A vista mostra id e `tipo` de cada restrição, com os critérios de aceite à frente da fronteira."""

from graphow.context.politicas import PoliticaExecutor, PoliticaPlanejador
from graphow.context.restricoes_de_escopo import formatar_restricao, formatar_restricao_curta, ordenar_restricoes
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _constraint(id_no: str, tipo: str | None = None) -> NoGrafo:
    """Constraint com rótulo derivado do id e o `tipo` opcional."""
    propriedades = {"tipo": tipo} if tipo else {"regra": "x"}
    return NoGrafo(id=id_no, tipo=TipoNo.CONSTRAINT, rotulo=f"texto {id_no}", propriedades=propriedades)


def _embaralhadas() -> list[NoGrafo]:
    """Quatro restrições em ordem embaralhada de propósito."""
    return [_constraint("c-front", "fronteira"), _constraint("c-livre"), _constraint("c-crit-2", "criterio_aceite"), _constraint("c-crit-1", "criterio_aceite")]


def _view() -> GrafoView:
    """Goal com Task e as quatro restrições escopando o Goal."""
    nos = {
        "goal": NoGrafo(id="goal", tipo=TipoNo.GOAL, rotulo="goal"),
        "task": NoGrafo(id="task", tipo=TipoNo.TASK, rotulo="task"),
        **{no.id: no for no in _embaralhadas()},
    }
    ligacoes = [("goal", "task", TipoAresta.DECOMPOE)] + [(no.id, "goal", TipoAresta.ESCOPA) for no in _embaralhadas()]
    arestas = {f"{o}->{d}": ArestaGrafo(id=f"{o}->{d}", origem_id=o, destino_id=d, tipo=t) for o, d, t in ligacoes}
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def test_linha_longa_leva_id_e_tipo_sem_repetir_o_tipo_no_json_nominal() -> None:
    """O id e o `tipo` ficam na cabeça da linha, e o JSON não repete o `tipo`."""
    linha = formatar_restricao(_constraint("c-1", "criterio_aceite"))
    assert linha.startswith("- [c-1] (criterio_aceite) texto c-1")
    assert '"tipo"' not in linha


def test_linha_curta_ainda_leva_id_e_tipo_nominal() -> None:
    """Sob pressão a restrição encolhe, mas a Task ainda lê o id do critério que cita."""
    assert formatar_restricao_curta(_constraint("c-1", "fronteira")).startswith("- [c-1] (fronteira) texto c-1")


def test_restricao_sem_tipo_segue_como_antes_edge_case() -> None:
    """Caso de borda: sem `tipo` não há marca, e as propriedades continuam inteiras."""
    linha = formatar_restricao(_constraint("c-2"))
    assert linha.startswith("- [c-2] texto c-2") and '"regra": "x"' in linha
    assert formatar_restricao_curta(_constraint("c-2")).startswith("- [c-2] texto c-2")


def test_criterios_vem_antes_da_fronteira_e_das_demais_nominal() -> None:
    """A ordem é estável: critérios, fronteira, o resto; empate pela ordem de descoberta."""
    ordenadas = ordenar_restricoes(_embaralhadas())
    assert [no.id for no in ordenadas] == ["c-crit-2", "c-crit-1", "c-front", "c-livre"]


def test_secao_de_restricoes_da_task_sobe_o_goal_na_ordem_certa_nominal() -> None:
    """A Task emergente lê, da Task, os critérios e a fronteira do Goal com os ids."""
    for politica in (PoliticaExecutor(), PoliticaPlanejador()):
        secao = politica.extrair_recorte("task", _view()).secoes[0]
        assert secao.titulo == "Restricoes Inviolaveis"
        assert sorted(secao.ids_incluidos[:2]) == ["c-crit-1", "c-crit-2"]
        assert secao.ids_incluidos[2:] == ("c-front", "c-livre")
        assert secao.linhas[0].startswith("- [c-crit-") and "(criterio_aceite)" in secao.linhas[0]
