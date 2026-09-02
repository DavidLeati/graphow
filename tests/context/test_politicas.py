"""Testes unitários para as políticas de recorte de contexto por papel."""

from graphow.context.politicas import PoliticaExecutor, PoliticaPlanejador, PoliticaRevisor
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, str] | None = None) -> NoGrafo:
    """Cria um nó com rótulo igual ao identificador."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades or {})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Cria uma aresta tipada com identificador derivado das pontas."""
    return ArestaGrafo(id=f"{origem}->{destino}", origem_id=origem, destino_id=destino, tipo=tipo)


def _montar_view() -> GrafoView:
    """Monta um grafo com dois objetivos independentes, para provar o escopo."""
    nos = {
        "goal-a": _no("goal-a", TipoNo.GOAL),
        "task-a": _no("task-a", TipoNo.TASK),
        "const-a": _no("const-a", TipoNo.CONSTRAINT, {"inviolavel": "sim"}),
        "dec-a": _no("dec-a", TipoNo.DECISION),
        "art-a": _no("art-a", TipoNo.ARTIFACT),
        "quest-a": _no("quest-a", TipoNo.QUESTION, {"status": StatusQuestion.ABERTA.value}),
        "goal-b": _no("goal-b", TipoNo.GOAL),
        "task-b": _no("task-b", TipoNo.TASK),
        "const-b": _no("const-b", TipoNo.CONSTRAINT),
        "dec-b": _no("dec-b", TipoNo.DECISION),
        "art-b": _no("art-b", TipoNo.ARTIFACT),
    }
    arestas = {
        aresta.id: aresta
        for aresta in (
            _aresta("goal-a", "task-a", TipoAresta.DECOMPOE),
            _aresta("const-a", "goal-a", TipoAresta.ESCOPA),
            _aresta("art-a", "task-a", TipoAresta.DERIVA_DE),
            _aresta("dec-a", "task-a", TipoAresta.SUBSTITUI),
            _aresta("quest-a", "task-a", TipoAresta.BLOQUEIA),
            _aresta("goal-b", "task-b", TipoAresta.DECOMPOE),
            _aresta("const-b", "goal-b", TipoAresta.ESCOPA),
            _aresta("art-b", "task-b", TipoAresta.DERIVA_DE),
            _aresta("dec-b", "task-b", TipoAresta.SUBSTITUI),
        )
    }
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def _titulos(recorte) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    """Títulos das seções não vazias do recorte."""
    return tuple(secao.titulo for secao in recorte.secoes_por_exibicao())


def test_executor_recebe_restricao_herdada_do_ancestral_nominal() -> None:
    """A Constraint escopa o Goal e alcança a Task por herança hierárquica."""
    recorte = PoliticaExecutor().extrair_recorte("task-a", _montar_view())
    assert "const-a" in recorte.ids_incluidos()


def test_executor_nao_recebe_material_de_outro_objetivo_nominal() -> None:
    """O recorte é escopado: nada do segundo objetivo aparece."""
    ids = PoliticaExecutor().extrair_recorte("task-a", _montar_view()).ids_incluidos()
    assert not any(id_no.endswith("-b") for id_no in ids), ids


def test_planejador_recebe_a_decomposicao_do_alvo_nominal() -> None:
    """O planejador enxerga as tarefas que decompõem o objetivo consultado."""
    ids = PoliticaPlanejador().extrair_recorte("goal-a", _montar_view()).ids_incluidos()
    assert "task-a" in ids
    assert "task-b" not in ids


def test_revisor_recebe_artefatos_derivados_do_alvo_nominal() -> None:
    """O revisor enxerga o artefato que deriva da tarefa sob revisão."""
    ids = PoliticaRevisor().extrair_recorte("task-a", _montar_view()).ids_incluidos()
    assert "art-a" in ids
    assert "art-b" not in ids


def test_duvida_bloqueante_aparece_em_qualquer_papel_edge_case() -> None:
    """Caso de borda: a dúvida que trava a tarefa é seção universal."""
    for politica in (PoliticaExecutor(), PoliticaRevisor()):
        recorte = politica.extrair_recorte("task-a", _montar_view())
        assert "quest-a" in recorte.ids_incluidos()
        assert "Duvidas Abertas Que Bloqueiam Este No" in _titulos(recorte)


def test_secao_vazia_nao_e_exibida_edge_case() -> None:
    """Caso de borda: um alvo sem decomposição não gera seção de decomposição."""
    recorte = PoliticaPlanejador().extrair_recorte("goal-b", _montar_view())
    assert "Duvidas Abertas Na Decomposicao" not in _titulos(recorte)


def test_alvo_inexistente_e_recusado_edge_case() -> None:
    """Caso de borda: pedir recorte de um nó ausente falha explicitamente."""
    import pytest

    with pytest.raises(KeyError):
        PoliticaExecutor().extrair_recorte("no-fantasma", _montar_view())


def test_secao_de_vizinhos_sempre_presente_quando_ha_arestas() -> None:
    """A afordância de expansão existe em todo recorte de nó conectado."""
    recorte = PoliticaExecutor().extrair_recorte("task-a", _montar_view())
    assert any("Vizinhos a 1 Salto" in titulo for titulo in _titulos(recorte))
