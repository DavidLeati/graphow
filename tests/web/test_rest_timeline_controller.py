"""Testes unitários para o TimelineWebController e Replay Temporal."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.identidade_web import IdentidadeSessaoWeb
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_timeline_controller import TimelineWebController

IDS_HIERARQUIA: frozenset[str] = frozenset({"proj", "setor", "sess"})


def _pendurar_sessao(kernel: WriteKernel) -> str:
    """Monta Projeto, Setor e Sessao sob um autor próprio, fora dos filtros dos testes."""
    controlador = CanvasWebController(kernel, IdentidadeSessaoWeb(autor="fundador"))
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor", id_no="setor", contido_em="proj"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao", id_no="sess", contido_em="setor"),
    )
    for req in requisicoes:
        assert controlador.criar_no(req).sucesso is True
    return "sess"


def test_obter_eventos_timeline_fluxo_nominal() -> None:
    """Valida leitura cronológica de eventos registrados no log."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    timeline_ctrl = TimelineWebController(store)
    sessao_id = _pendurar_sessao(kernel)
    total_hierarquia = len(timeline_ctrl.obter_eventos())

    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david")).criar_no(
        RequisicaoNovoNo(tipo="Goal", rotulo="Objetivo 1", id_no="g-1", sessao_id=sessao_id)
    )
    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="agente-1")).criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="Tarefa 1", id_no="t-1", sessao_id=sessao_id)
    )

    # Cada criação gera dois eventos: o nó e a aresta `produz` que o pendura na Sessao
    eventos = timeline_ctrl.obter_eventos()[total_hierarquia:]
    assert len(eventos) == 4
    assert [e["autor"] for e in eventos] == ["david", "david", "agente-1", "agente-1"]
    assert [e["seq"] for e in eventos] == sorted(e["seq"] for e in eventos)


def test_filtro_timeline_por_autor_e_papel_edge_case() -> None:
    """Valida filtragem de eventos por autor e papel."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    timeline_ctrl = TimelineWebController(store)
    sessao_id = _pendurar_sessao(kernel)

    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david")).criar_no(
        RequisicaoNovoNo(tipo="Goal", rotulo="G1", sessao_id=sessao_id)
    )
    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="ia-1")).criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="T1", sessao_id=sessao_id)
    )

    # Nó e aresta `produz` de cada criação
    ev_david = timeline_ctrl.obter_eventos(autor="david")
    assert len(ev_david) == 2

    ev_ia = timeline_ctrl.obter_eventos(autor="ia-1")
    assert len(ev_ia) == 2

    ev_vazio = timeline_ctrl.obter_eventos(papel="revisor")
    assert len(ev_vazio) == 0


def test_reconstrucao_estado_na_versao_time_travel_edge_case() -> None:
    """Valida reconstrução do estado do grafo em versão passada (Time-Travel)."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    canvas_ctrl = CanvasWebController(kernel)
    timeline_ctrl = TimelineWebController(store)
    sessao_id = _pendurar_sessao(kernel)

    v1 = canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Versao 1", id_no="n-1", sessao_id=sessao_id)).versao_log
    v2 = canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Versao 2", id_no="n-2", sessao_id=sessao_id)).versao_log
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Decision", rotulo="Versao 3", id_no="n-3", sessao_id=sessao_id))

    # Estado na versão do primeiro lote de trabalho deve conter, além da hierarquia, apenas n-1
    estado_v1 = timeline_ctrl.obter_estado_na_versao(v1)
    assert {n.id for n in estado_v1.nos} == IDS_HIERARQUIA | {"n-1"}

    # Estado na versão do segundo lote deve conter n-1 e n-2
    estado_v2 = timeline_ctrl.obter_estado_na_versao(v2)
    assert {n.id for n in estado_v2.nos} == IDS_HIERARQUIA | {"n-1", "n-2"}

    # Estado na versão #0 deve estar completamente vazio
    estado_v0 = timeline_ctrl.obter_estado_na_versao(0)
    assert estado_v0.total_nos == 0
