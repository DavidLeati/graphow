"""Testes unitários para o LineageWebController."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoNovaAresta, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_lineage_controller import LineageWebController


def test_rastrear_linhagem_fluxo_nominal() -> None:
    """Valida cadeia causal completa: Artifact -> Task -> Goal."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    lineage_ctrl = LineageWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Objetivo Raiz", id_no="goal-1"))
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Tarefa Intermediaria", id_no="task-1"))
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Artifact", rotulo="Codigo Gerado", id_no="art-1"))

    canvas_ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="goal-1", destino_id="task-1", tipo="decompoe"))
    canvas_ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="art-1", destino_id="task-1", tipo="deriva_de"))

    resultado = lineage_ctrl.obter_linhagem("art-1")
    assert resultado["id_alvo"] == "art-1"
    assert resultado["goal_raiz"] is not None
    assert resultado["goal_raiz"]["id"] == "goal-1"
    assert len(resultado["passos"]) >= 2


def test_rastrear_linhagem_no_inexistente_edge_case() -> None:
    """Valida retorno gracioso quando o nó alvo não existe."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    lineage_ctrl = LineageWebController(kernel)

    resultado = lineage_ctrl.obter_linhagem("no-fantasma")
    assert resultado["id_alvo"] == "no-fantasma"
    assert resultado["goal_raiz"] is None
    assert len(resultado["passos"]) == 0


def test_rastrear_linhagem_no_isolado_edge_case() -> None:
    """Valida retorno quando o nó alvo não possui ancestrais até o Goal."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    lineage_ctrl = LineageWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Note", rotulo="Nota Avulsa", id_no="note-1"))

    resultado = lineage_ctrl.obter_linhagem("note-1")
    assert resultado["id_alvo"] == "note-1"
    assert resultado["goal_raiz"] is None
    assert len(resultado["passos"]) == 1
