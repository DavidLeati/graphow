"""Testes unitários para os repositórios de lock exclusivo de tarefas."""

from pathlib import Path

import pytest

from graphow.storage.interfaces import RepositorioLocks
from graphow.storage.lock_store import LockStoreEmMemoria, LockStoreSQLite
from graphow.storage.sqlite_store import SQLiteEventStore


@pytest.fixture(name="lock_store_em_memoria")
def _lock_store_em_memoria() -> RepositorioLocks:
    """Repositório de locks isolado por processo."""
    return LockStoreEmMemoria()


def test_adquire_e_libera_lock_nominal(lock_store_em_memoria: RepositorioLocks) -> None:
    """O primeiro autor obtém o lock e consegue devolvê-lo."""
    assert lock_store_em_memoria.tentar_adquirir("task-1", "david") is True
    assert lock_store_em_memoria.obter_dono("task-1") == "david"
    assert lock_store_em_memoria.liberar("task-1", "david") is True
    assert lock_store_em_memoria.obter_dono("task-1") is None


def test_reaquisicao_pelo_mesmo_autor_e_idempotente_nominal(lock_store_em_memoria: RepositorioLocks) -> None:
    """Pedir de novo o lock que já se detém não falha nem duplica."""
    assert lock_store_em_memoria.tentar_adquirir("task-1", "david") is True
    assert lock_store_em_memoria.tentar_adquirir("task-1", "david") is True
    assert lock_store_em_memoria.listar_locks() == {"task-1": "david"}


def test_segundo_autor_e_recusado_edge_case(lock_store_em_memoria: RepositorioLocks) -> None:
    """Caso de borda: lock já detido por outro autor não é cedido."""
    lock_store_em_memoria.tentar_adquirir("task-1", "david")
    assert lock_store_em_memoria.tentar_adquirir("task-1", "agente") is False


def test_liberacao_por_quem_nao_detem_e_recusada_edge_case(lock_store_em_memoria: RepositorioLocks) -> None:
    """Caso de borda: ninguém libera o lock alheio."""
    lock_store_em_memoria.tentar_adquirir("task-1", "david")
    assert lock_store_em_memoria.liberar("task-1", "agente") is False
    assert lock_store_em_memoria.obter_dono("task-1") == "david"


def test_liberar_lock_inexistente_nao_falha_edge_case(lock_store_em_memoria: RepositorioLocks) -> None:
    """Caso de borda: liberar algo que nunca foi travado devolve falso, não erro."""
    assert lock_store_em_memoria.liberar("task-fantasma", "david") is False


def test_listagem_devolve_copia_independente_edge_case(lock_store_em_memoria: RepositorioLocks) -> None:
    """Caso de borda: mutar o instantâneo devolvido não altera o repositório."""
    lock_store_em_memoria.tentar_adquirir("task-1", "david")
    instantaneo = lock_store_em_memoria.listar_locks()
    instantaneo["task-1"] = "invasor"
    assert lock_store_em_memoria.obter_dono("task-1") == "david"


def test_lock_sqlite_e_compartilhado_entre_conexoes(tmp_path: Path) -> None:
    """Duas conexões ao mesmo arquivo enxergam o mesmo conjunto de locks."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as store_a, SQLiteEventStore(str(caminho)) as store_b:
        locks_a = LockStoreSQLite(store_a.conexao)
        locks_b = LockStoreSQLite(store_b.conexao)

        assert locks_a.tentar_adquirir("task-1", "david") is True
        assert locks_b.obter_dono("task-1") == "david"
        assert locks_b.tentar_adquirir("task-1", "agente") is False
        assert locks_b.listar_locks() == {"task-1": "david"}

        assert locks_a.liberar("task-1", "david") is True
        assert locks_b.obter_dono("task-1") is None
