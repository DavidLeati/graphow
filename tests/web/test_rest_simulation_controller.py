"""Testes unitários para o SimulationWebController."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoNovoNo, RequisicaoSimularVista
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_simulation_controller import SimulationWebController


def test_simular_vista_tokens_fluxo_nominal() -> None:
    """Valida materialização de vista sob orçamento para agente."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    sim_ctrl = SimulationWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Implementar Token Simulator", id_no="t-sim"))

    resultado = sim_ctrl.simular_vista(RequisicaoSimularVista(id_alvo="t-sim", papel="executor", orcamento_tokens=1000))
    assert resultado["sucesso"] is True
    assert resultado["tokens_estimados"] > 0
    assert resultado["orcamento_tokens"] == 1000
    assert "Implementar Token Simulator" in resultado["conteudo_markdown"]


def test_simular_vista_no_inexistente_edge_case() -> None:
    """Valida retorno de erro quando o nó alvo não existe."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    sim_ctrl = SimulationWebController(kernel)

    resultado = sim_ctrl.simular_vista(RequisicaoSimularVista(id_alvo="no-inexistente"))
    assert resultado["sucesso"] is False
    assert "não encontrado" in resultado["mensagem"]


def test_expandir_no_sob_demanda_edge_case() -> None:
    """Valida expansão detalhada de propriedades e arestas de um nó."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    sim_ctrl = SimulationWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Expandir Meta", id_no="g-exp"))

    res_ok = sim_ctrl.expandir_no("g-exp")
    assert res_ok["sucesso"] is True
    assert res_ok["no"]["id"] == "g-exp"

    res_err = sim_ctrl.expandir_no("g-fantasma")
    assert res_err["sucesso"] is False


def test_fallback_papel_invalido_edge_case() -> None:
    """Valida fallback gracioso para EXECUTOR quando papel inválido é informado."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    sim_ctrl = SimulationWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Fallback", id_no="t-fb"))

    resultado = sim_ctrl.simular_vista(RequisicaoSimularVista(id_alvo="t-fb", papel="papel_desconhecido"))
    assert resultado["sucesso"] is True
    assert resultado["papel"] == "executor"
