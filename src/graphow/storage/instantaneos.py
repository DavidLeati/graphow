"""Instantâneos da projeção guardados junto do log, para a abertura não refazer o replay inteiro.

Abrir o banco dobrava o log desde o primeiro evento: 170 ms com 14 mil eventos,
crescendo em linha reta, e cada chamada de hook abre o banco de novo. O
instantâneo é o estado de um ramo já dobrado até um `seq`, e a abertura parte
dele e dobra só o que veio depois.

Ele é cache, não verdade. O log continua sendo a única fonte: um instantâneo
que falta, que não confere com o log ou que foi escrito por outra versão do
código de projeção é ignorado, e a abertura volta ao replay completo. Este
módulo guarda e devolve texto; quem sabe o que o texto significa é
`graphow.projection.instantaneo`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import sqlite3
import threading

DDL_TABELA_INSTANTANEOS: str = """
    CREATE TABLE IF NOT EXISTS instantaneos (
        ramo_id TEXT PRIMARY KEY,
        seq INTEGER NOT NULL,
        evento_id TEXT NOT NULL,
        impressao TEXT NOT NULL,
        estado TEXT NOT NULL
    );
"""


@dataclass(frozen=True)
class InstantaneoGravado:
    """O estado serializado de um ramo, com o que é preciso para conferi-lo contra o log.

    `evento_id` é o id do evento na posição `seq`: se o log foi reescrito até
    ali, o evento naquela posição muda e o instantâneo deixa de valer.
    `impressao` identifica o código que dobrou o estado.
    """

    ramo_id: str
    seq: int
    evento_id: str
    impressao: str
    estado: str


class RepositorioInstantaneos(ABC):
    """Contrato de guarda dos instantâneos, um por ramo."""

    @abstractmethod
    def obter(self, ramo_id: str) -> InstantaneoGravado | None:
        """O instantâneo mais recente do ramo, se houver."""
        raise NotImplementedError

    @abstractmethod
    def gravar(self, instantaneo: InstantaneoGravado) -> bool:
        """Substitui o instantâneo do ramo; devolve False se não conseguiu, sem levantar."""
        raise NotImplementedError


class RepositorioInstantaneosEmMemoria(RepositorioInstantaneos):
    """Instantâneos mantidos só em memória, para testes."""

    def __init__(self) -> None:
        self._por_ramo: dict[str, InstantaneoGravado] = {}
        self._lock: threading.RLock = threading.RLock()

    def obter(self, ramo_id: str) -> InstantaneoGravado | None:
        """Consulta o instantâneo do ramo."""
        with self._lock:
            return self._por_ramo.get(ramo_id)

    def gravar(self, instantaneo: InstantaneoGravado) -> bool:
        """Guarda o instantâneo no lugar do anterior."""
        with self._lock:
            self._por_ramo[instantaneo.ramo_id] = instantaneo
            return True


class RepositorioInstantaneosSQLite(RepositorioInstantaneos):
    """Instantâneos no mesmo arquivo do log de eventos."""

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao: sqlite3.Connection = conexao
        self._lock: threading.RLock = threading.RLock()
        with self._lock:
            self._conexao.execute(DDL_TABELA_INSTANTANEOS)

    def obter(self, ramo_id: str) -> InstantaneoGravado | None:
        """Lê o instantâneo do ramo."""
        with self._lock:
            linha = self._conexao.execute(
                "SELECT ramo_id, seq, evento_id, impressao, estado FROM instantaneos WHERE ramo_id = ?;",
                (ramo_id,),
            ).fetchone()
        if linha is None:
            return None
        return InstantaneoGravado(str(linha[0]), int(linha[1]), str(linha[2]), str(linha[3]), str(linha[4]))

    def gravar(self, instantaneo: InstantaneoGravado) -> bool:
        """Grava por cima do anterior; banco ocupado só adia o instantâneo para a próxima abertura."""
        with self._lock:
            try:
                self._conexao.execute(
                    "INSERT OR REPLACE INTO instantaneos (ramo_id, seq, evento_id, impressao, estado) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (
                        instantaneo.ramo_id,
                        instantaneo.seq,
                        instantaneo.evento_id,
                        instantaneo.impressao,
                        instantaneo.estado,
                    ),
                )
            except sqlite3.Error:
                return False
            return True


def descartar_instantaneos(conexao: sqlite3.Connection) -> None:
    """Apaga todos os instantâneos do arquivo; quem reescreve o log chama isto."""
    existe = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'instantaneos';"
    ).fetchone()
    if existe is not None:
        conexao.execute("DELETE FROM instantaneos;")
