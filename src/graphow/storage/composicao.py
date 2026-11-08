"""Fábricas que montam o conjunto de repositórios usado pelo kernel."""

from dataclasses import dataclass
from pathlib import Path

from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.storage.instantaneos import RepositorioInstantaneos, RepositorioInstantaneosSQLite
from graphow.storage.interfaces import RepositorioEventos, RepositorioLocks
from graphow.storage.linhagem_ramo import (
    RepositorioRamos,
    RepositorioRamosEmMemoria,
    RepositorioRamosSQLite,
)
from graphow.storage.lock_store import LockStoreEmMemoria, LockStoreSQLite
from graphow.storage.repositorio_com_linhagem import RepositorioEventosComLinhagem
from graphow.storage.sqlite_store import SQLiteEventStore


@dataclass(frozen=True)
class ConjuntoRepositorios:
    """Repositórios já compostos e prontos para injeção no kernel."""

    eventos: RepositorioEventos
    ramos: RepositorioRamos
    locks: RepositorioLocks
    instantaneos: RepositorioInstantaneos | None = None


def montar_repositorios_em_memoria() -> ConjuntoRepositorios:
    """Monta o conjunto efêmero, com linhagem de ramos resolvida na leitura."""
    base = InMemoryEventStore()
    ramos = RepositorioRamosEmMemoria()
    return ConjuntoRepositorios(
        eventos=RepositorioEventosComLinhagem(base, ramos),
        ramos=ramos,
        locks=LockStoreEmMemoria(),
    )


def montar_repositorios_sqlite(store: SQLiteEventStore) -> ConjuntoRepositorios:
    """Monta o conjunto persistente sobre um arquivo SQLite já aberto, todos sob a trava da conexão.

    Com uma trava para cada um, a escrita de um adaptador vinda de outra
    thread entrava no lote que o store tinha aberto.
    """
    ramos = RepositorioRamosSQLite(store.conexao, trava=store.trava)
    return ConjuntoRepositorios(
        eventos=RepositorioEventosComLinhagem(store, ramos),
        ramos=ramos,
        locks=LockStoreSQLite(store.conexao, trava=store.trava),
        instantaneos=RepositorioInstantaneosSQLite(store.conexao, trava=store.trava),
    )


def abrir_repositorios_sqlite(caminho_banco: str | Path) -> tuple[SQLiteEventStore, ConjuntoRepositorios]:
    """Abre o arquivo e devolve o store cru junto do conjunto composto."""
    store = SQLiteEventStore(caminho_banco)
    return store, montar_repositorios_sqlite(store)
