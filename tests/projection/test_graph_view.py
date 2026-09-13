"""Testes unitários para a camada de consultas GrafoView."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusQuestion, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.reducer import GrafoReducer


def test_grafo_view_consultas_nominais() -> None:
    """Testa contagem, busca por tipo e recuperação de nós/arestas."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "g1", "tipo": "Goal", "rotulo": "Objetivo A"})),
        EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "t1", "tipo": "Task", "rotulo": "Tarefa 1"})),
        EventoLog.criar(DadosCriacaoEvento(3, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, {
            "id": "e1", "origem_id": "g1", "destino_id": "t1", "tipo": "decompoe"
        })),
    ]
    estado: GrafoEstado = GrafoReducer.reconstruir(eventos)
    view = GrafoView(estado)

    assert view.total_nos == 2
    assert view.total_arestas == 1
    assert view.obter_no("g1") is not None
    assert len(view.listar_nos_por_tipo(TipoNo.GOAL)) == 1
    assert len(view.obter_arestas_saida("g1")) == 1
    assert len(view.obter_arestas_entrada("t1")) == 1


def test_grafo_view_questoes_bloqueantes_e_status_edge_case() -> None:
    """Caso de borda: detecção de bloqueio em Task com Question aberta e resolvida."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "t1", "tipo": "Task", "rotulo": "Tarefa X"})),
        EventoLog.criar(DadosCriacaoEvento(2, "agente", PapelAutor.PLANEJADOR, TipoEvento.NO_CRIADO, {
            "id": "q1", "tipo": "Question", "rotulo": "Qual formato?", "propriedades": {"status": StatusQuestion.ABERTA.value}
        })),
        EventoLog.criar(DadosCriacaoEvento(3, "agente", PapelAutor.PLANEJADOR, TipoEvento.ARESTA_CRIADA, {
            "id": "e_bloq", "origem_id": "q1", "destino_id": "t1", "tipo": TipoAresta.BLOQUEIA.value
        })),
    ]
    estado = GrafoReducer.reconstruir(eventos)
    view = GrafoView(estado)

    assert view.esta_bloqueada("t1") is True
    assert len(view.obter_questoes_bloqueantes("t1")) == 1

    # Quando a questão é respondida, o bloqueio cessa
    ev_resolvida = EventoLog.criar(DadosCriacaoEvento(4, "david", PapelAutor.HUMANO, TipoEvento.NO_ATUALIZADO, {
        "id": "q1", "propriedades": {"status": StatusQuestion.RESPONDIDA.value}
    }))
    estado_resolvido = GrafoReducer.reduzir(estado, ev_resolvida)
    view_resolvida = GrafoView(estado_resolvido)
    assert view_resolvida.esta_bloqueada("t1") is False


def test_grafo_view_busca_textual_e_vizinhos_1_salto_edge_case() -> None:
    """Caso de borda: busca textual com filtro por tipo e coleta bidirecional de vizinhos a 1 salto."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {
            "id": "n1", "tipo": "Task", "rotulo": "Processar XML ANBIMA", "propriedades": {"modulo": "contabilidade"}
        })),
        EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {
            "id": "n2", "tipo": "Note", "rotulo": "Nota sobre XML ANBIMA", "propriedades": {}
        })),
        EventoLog.criar(DadosCriacaoEvento(3, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, {
            "id": "e1", "origem_id": "n1", "destino_id": "n2", "tipo": "produz"
        })),
    ]
    view = GrafoView(GrafoReducer.reconstruir(eventos))

    busca_todos = view.buscar_nos("xml")
    assert len(busca_todos) == 2

    busca_tasks = view.buscar_nos("xml", [TipoNo.TASK])
    assert len(busca_tasks) == 1
    assert busca_tasks[0].id == "n1"

    vizinhos_n1 = view.obter_vizinhos_1_salto("n1")
    assert len(vizinhos_n1) == 1
    assert vizinhos_n1[0].id == "n2"
