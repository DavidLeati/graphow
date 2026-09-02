"""Testes unitários para o TimelineWebController e Replay Temporal."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.identidade_web import IdentidadeSessaoWeb
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_timeline_controller import TimelineWebController


def test_obter_eventos_timeline_fluxo_nominal() -> None:
    """Valida leitura cronológica de eventos registrados no log."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    timeline_ctrl = TimelineWebController(store)

    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david")).criar_no(
        RequisicaoNovoNo(tipo="Goal", rotulo="Objetivo 1", id_no="g-1")
    )
    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="agente-1")).criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="Tarefa 1", id_no="t-1")
    )

    eventos = timeline_ctrl.obter_eventos()
    assert len(eventos) == 2
    assert eventos[0]["autor"] == "david"
    assert eventos[1]["autor"] == "agente-1"


def test_filtro_timeline_por_autor_e_papel_edge_case() -> None:
    """Valida filtragem de eventos por autor e papel."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    timeline_ctrl = TimelineWebController(store)

    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david")).criar_no(
        RequisicaoNovoNo(tipo="Goal", rotulo="G1")
    )
    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="ia-1")).criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="T1")
    )

    ev_david = timeline_ctrl.obter_eventos(autor="david")
    assert len(ev_david) == 1

    ev_ia = timeline_ctrl.obter_eventos(autor="ia-1")
    assert len(ev_ia) == 1

    ev_vazio = timeline_ctrl.obter_eventos(papel="revisor")
    assert len(ev_vazio) == 0


def test_reconstrucao_estado_na_versao_time_travel_edge_case() -> None:
    """Valida reconstrução do estado do grafo em versão passada (Time-Travel)."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    timeline_ctrl = TimelineWebController(store)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Versao 1", id_no="n-1"))
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Versao 2", id_no="n-2"))
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Decision", rotulo="Versao 3", id_no="n-3"))

    # Estado na versão #1 deve conter apenas n-1
    estado_v1 = timeline_ctrl.obter_estado_na_versao(1)
    assert estado_v1.total_nos == 1
    assert estado_v1.nos[0].id == "n-1"

    # Estado na versão #2 deve conter n-1 e n-2
    estado_v2 = timeline_ctrl.obter_estado_na_versao(2)
    assert estado_v2.total_nos == 2

    # Estado na versão #0 deve estar completamente vazio
    estado_v0 = timeline_ctrl.obter_estado_na_versao(0)
    assert estado_v0.total_nos == 0
