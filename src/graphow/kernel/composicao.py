"""Raiz de composição do kernel: monta repositórios e portões numa peça só."""

from pathlib import Path

from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.observability.tracer import Tracer
from graphow.storage.composicao import (
    ConjuntoRepositorios,
    montar_repositorios_em_memoria,
    montar_repositorios_sqlite,
)
from graphow.storage.sqlite_store import SQLiteEventStore


def montar_kernel(
    repositorios: ConjuntoRepositorios,
    tracer: Tracer | None = None,
) -> WriteKernel:
    """Constrói o kernel sobre um conjunto de repositórios já composto.

    Sem `tracer` o kernel usa o destino nulo: a telemetria só custa alguma
    coisa quando alguém a pede. Ver achado A-13.
    """
    dependencias = DependenciasKernel(
        repositorio_locks=repositorios.locks,
        repositorio_ramos=repositorios.ramos,
        tracer=tracer,
    )
    return WriteKernel(repositorios.eventos, dependencias)


def montar_kernel_em_memoria(tracer: Tracer | None = None) -> WriteKernel:
    """Kernel efêmero completo, com linhagem de ramos e locks em memória."""
    return montar_kernel(montar_repositorios_em_memoria(), tracer)


def montar_kernel_sqlite(store: SQLiteEventStore, tracer: Tracer | None = None) -> WriteKernel:
    """Kernel persistente sobre um arquivo SQLite já aberto."""
    return montar_kernel(montar_repositorios_sqlite(store), tracer)


def abrir_kernel_sqlite(
    caminho_banco: str | Path,
    tracer: Tracer | None = None,
) -> tuple[SQLiteEventStore, WriteKernel]:
    """Abre o banco e devolve o store cru junto do kernel montado sobre ele."""
    store = SQLiteEventStore(caminho_banco)
    return store, montar_kernel_sqlite(store, tracer)
