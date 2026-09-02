"""Repositórios de locks exclusivos de escrita sobre tarefas.

Um lock guardado apenas na memória do processo não protege nada na fronteira que
importa: humano no canvas e agente no MCP são processos distintos. Ver auditoria F-04.
"""

import sqlite3
import threading

from graphow.core.exceptions import GraphowError
from graphow.storage.interfaces import RepositorioLocks

DDL_TABELA_LOCKS: str = """
    CREATE TABLE IF NOT EXISTS locks_de_tarefa (
        id_task TEXT PRIMARY KEY,
        autor TEXT NOT NULL,
        adquirido_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""


class LockStoreEmMemoria(RepositorioLocks):
    """Coordenação de locks dentro de um único processo, para testes e uso efêmero."""

    def __init__(self) -> None:
        self._donos_por_task: dict[str, str] = {}
        self._lock: threading.RLock = threading.RLock()

    def tentar_adquirir(self, id_task: str, autor: str) -> bool:
        """Adquire o lock se estiver livre ou já pertencer ao mesmo autor."""
        with self._lock:
            dono_atual = self._donos_por_task.get(id_task)
            if dono_atual is not None and dono_atual != autor:
                return False
            self._donos_por_task[id_task] = autor
            return True

    def liberar(self, id_task: str, autor: str) -> bool:
        """Libera o lock apenas se o solicitante for o detentor."""
        with self._lock:
            if self._donos_por_task.get(id_task) != autor:
                return False
            del self._donos_por_task[id_task]
            return True

    def obter_dono(self, id_task: str) -> str | None:
        """Consulta o detentor atual do lock da tarefa."""
        with self._lock:
            return self._donos_por_task.get(id_task)

    def listar_locks(self) -> dict[str, str]:
        """Devolve uma cópia do mapa de locks ativos."""
        with self._lock:
            return dict(self._donos_por_task)


class LockStoreSQLite(RepositorioLocks):
    """Coordenação de locks compartilhada entre processos pelo mesmo arquivo SQLite."""

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao: sqlite3.Connection = conexao
        self._lock: threading.RLock = threading.RLock()
        self._configurar_schema()

    def _configurar_schema(self) -> None:
        """Cria a tabela de locks, se ainda não existir."""
        with self._lock:
            self._conexao.execute(DDL_TABELA_LOCKS)

    def tentar_adquirir(self, id_task: str, autor: str) -> bool:
        """Insere o lock de forma atômica, respeitando um detentor preexistente."""
        with self._lock:
            dono_atual = self.obter_dono(id_task)
            if dono_atual is not None:
                return dono_atual == autor
            return self._inserir_lock(id_task, autor)

    def _inserir_lock(self, id_task: str, autor: str) -> bool:
        """Grava o lock, tratando a corrida contra outro processo como derrota."""
        try:
            self._conexao.execute(
                "INSERT INTO locks_de_tarefa (id_task, autor) VALUES (?, ?);", (id_task, autor)
            )
        except sqlite3.IntegrityError:
            return self.obter_dono(id_task) == autor
        except sqlite3.Error as erro:
            raise GraphowError(
                f"Falha ao adquirir lock de tarefa: {erro}", {"id_task": id_task, "autor": autor}
            ) from erro
        return True

    def liberar(self, id_task: str, autor: str) -> bool:
        """Remove o lock apenas quando o autor informado é o detentor registrado."""
        with self._lock:
            cursor = self._conexao.execute(
                "DELETE FROM locks_de_tarefa WHERE id_task = ? AND autor = ?;", (id_task, autor)
            )
            return cursor.rowcount > 0

    def obter_dono(self, id_task: str) -> str | None:
        """Consulta o detentor do lock diretamente no banco compartilhado."""
        with self._lock:
            linha = self._conexao.execute(
                "SELECT autor FROM locks_de_tarefa WHERE id_task = ?;", (id_task,)
            ).fetchone()
            return str(linha[0]) if linha else None

    def listar_locks(self) -> dict[str, str]:
        """Devolve um instantâneo de todos os locks ativos no banco."""
        with self._lock:
            linhas = self._conexao.execute("SELECT id_task, autor FROM locks_de_tarefa;").fetchall()
            return {str(linha[0]): str(linha[1]) for linha in linhas}
