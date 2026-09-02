"""Testes unitários para InMemoryEventStore."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor
from graphow.storage.in_memory_store import InMemoryEventStore


def test_in_memory_store_fluxo_nominal() -> None:
    """Testa inserção e leitura de eventos no InMemoryEventStore."""
    store = InMemoryEventStore()
    assert store.obter_ultimo_seq() == 0

    ev1 = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1"}))
    ev2 = EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n2"}))
    store.append_evento(ev1)
    store.append_evento(ev2)

    assert store.obter_ultimo_seq() == 2
    eventos = store.ler_eventos("main")
    assert len(eventos) == 2
    assert eventos[0].id == ev1.id


def test_in_memory_store_ramos_isolados_edge_case() -> None:
    """Caso de borda: eventos em ramos diferentes são isolados nas consultas."""
    store = InMemoryEventStore()
    ev_main = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1"}, ramo_id="main"))
    ev_fork = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1"}, ramo_id="fork-1"))

    store.append_evento(ev_main)
    store.append_evento(ev_fork)

    assert len(store.ler_eventos("main")) == 1
    assert len(store.ler_eventos("fork-1")) == 1
    assert store.listar_ramos() == ["fork-1", "main"]


def test_in_memory_store_ler_ate_seq_e_busca_id_edge_case() -> None:
    """Caso de borda: leitura até sequência intermediária e busca por ID inexistente."""
    store = InMemoryEventStore()
    for i in range(1, 6):
        ev = EventoLog.criar(DadosCriacaoEvento(i, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": f"n{i}"}))
        store.append_evento(ev)

    eventos_ate_3 = store.ler_eventos_ate_seq("main", 3)
    assert len(eventos_ate_3) == 3
    assert [e.seq for e in eventos_ate_3] == [1, 2, 3]
    assert store.obter_evento_por_id("id-inexistente") is None
