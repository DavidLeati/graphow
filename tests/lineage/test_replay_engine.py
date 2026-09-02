"""Testes unitários para ReplayEngine e Diff de forks."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, TipoNo
from graphow.lineage.replay_engine import ReplayEngine
from graphow.storage.in_memory_store import InMemoryEventStore


def test_replay_engine_reproducao_por_seq_nominal() -> None:
    """Testa reprodução temporal exata por número de sequência."""
    store = InMemoryEventStore()
    for i in range(1, 6):
        dados = DadosCriacaoEvento(i, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": f"t{i}", "tipo": TipoNo.TASK.value})
        store.append_evento(EventoLog.criar(dados))

    engine = ReplayEngine(store)
    estado_no_seq_3 = engine.reproduzir_ate_seq("main", 3)
    assert len(estado_no_seq_3.nos) == 3
    assert estado_no_seq_3.contem_no("t1") is True
    assert estado_no_seq_3.contem_no("t4") is False


def test_replay_engine_diff_entre_ramos_edge_case() -> None:
    """Caso de borda: cálculo de nós e arestas adicionadas/removidas entre dois estados."""
    store = InMemoryEventStore()
    engine = ReplayEngine(store)

    ev_main_1 = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1", "tipo": TipoNo.GOAL.value}, ramo_id="main"))
    ev_main_2 = EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n2", "tipo": TipoNo.TASK.value}, ramo_id="main"))
    store.append_evento(ev_main_1)
    store.append_evento(ev_main_2)

    ev_fork_1 = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1", "tipo": TipoNo.GOAL.value}, ramo_id="fork-1"))
    ev_fork_2 = EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n3", "tipo": TipoNo.TASK.value}, ramo_id="fork-1"))
    store.append_evento(ev_fork_1)
    store.append_evento(ev_fork_2)

    estado_main = engine.reproduzir_ate_seq("main", 2)
    estado_fork = engine.reproduzir_ate_seq("fork-1", 2)

    diff = engine.calcular_diff(estado_main, estado_fork)
    assert diff["nos_comuns"] == ["n1"]
    assert diff["nos_adicionados"] == ["n3"]
    assert diff["nos_removidos"] == ["n2"]
