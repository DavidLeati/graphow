"""Testes unitários para SQLiteEventStore."""

from pathlib import Path
import tempfile

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.storage.sqlite_store import SQLiteEventStore


def test_sqlite_store_fluxo_nominal() -> None:
    """Testa persistência e recuperação de eventos em banco SQLite em arquivo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho_db = Path(tmpdir) / "teste_events.db"
        store = SQLiteEventStore(caminho_db)

        dados = DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "no-1", "tipo": "Goal"})
        ev1 = EventoLog.criar(dados)
        store.append_evento(ev1)

        assert store.obter_ultimo_seq("main") == 1
        eventos = store.ler_eventos("main")
        assert len(eventos) == 1
        assert eventos[0].id == ev1.id
        assert eventos[0].payload["id"] == "no-1"
        store.fechar()


def test_sqlite_store_recuperacao_apos_reabertura_edge_case() -> None:
    """Caso de borda: dados persistem após fechar e reabrir a conexão."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho_db = Path(tmpdir) / "teste_persist.db"
        store1 = SQLiteEventStore(caminho_db)
        dados = DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "no-1"})
        ev1 = EventoLog.criar(dados)
        store1.append_evento(ev1)
        store1.fechar()

        store2 = SQLiteEventStore(caminho_db)
        assert store2.obter_ultimo_seq("main") == 1
        ev_recuperado = store2.obter_evento_por_id(ev1.id)
        assert ev_recuperado is not None
        assert ev_recuperado.id == ev1.id
        store2.fechar()


def test_sqlite_store_ramos_e_seq_limite_edge_case() -> None:
    """Caso de borda: filtragem por ramo e sequência limite com trace_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho_db = Path(tmpdir) / "teste_ramos.db"
        store = SQLiteEventStore(caminho_db)

        for i in range(1, 4):
            dados = DadosCriacaoEvento(
                seq=i,
                autor="executor",
                papel=PapelAutor.EXECUTOR,
                tipo_evento=TipoEvento.EXECUCAO_INICIADA,
                payload={"run_id": f"r{i}"},
                origem=OrigemEvento.HARNESS,
                ramo_id="branch-a",
                trace_id="otel-trace-123",
            )
            store.append_evento(EventoLog.criar(dados))

        assert store.listar_ramos() == ["branch-a"]
        eventos_ate_2 = store.ler_eventos_ate_seq("branch-a", 2)
        assert len(eventos_ate_2) == 2
        assert eventos_ate_2[1].trace_id == "otel-trace-123"
        assert store.obter_evento_por_id("nao-existe") is None
        store.fechar()
