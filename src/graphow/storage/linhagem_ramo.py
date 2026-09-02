"""Definição e persistência da linhagem entre ramos do log de eventos.

Um fork é um ponteiro para (ramo_base, seq_corte), não uma cópia do prefixo.
Copiar era o que duplicava sequências e quebrava o determinismo. Ver auditoria F-06.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import sqlite3
import threading

from graphow.core.exceptions import GraphowError

DDL_TABELA_RAMOS: str = """
    CREATE TABLE IF NOT EXISTS ramos (
        ramo_id TEXT PRIMARY KEY,
        ramo_base TEXT NOT NULL,
        seq_corte INTEGER NOT NULL,
        evento_corte_id TEXT,
        criado_em TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""

PROFUNDIDADE_MAXIMA_DE_LINHAGEM: int = 32


@dataclass(frozen=True)
class DefinicaoRamo:
    """Ponteiro imutável de um ramo para o ponto de corte no ramo de origem."""

    ramo_id: str
    ramo_base: str
    seq_corte: int
    evento_corte_id: str | None = None


class RepositorioRamos(ABC):
    """Contrato de persistência das definições de ramificação."""

    @abstractmethod
    def registrar(self, definicao: DefinicaoRamo) -> None:
        """Grava a definição de um novo ramo derivado."""
        raise NotImplementedError

    @abstractmethod
    def obter_definicao(self, ramo_id: str) -> DefinicaoRamo | None:
        """Recupera a definição do ramo, ou None se ele for raiz."""
        raise NotImplementedError

    @abstractmethod
    def listar_ramos_derivados(self) -> tuple[str, ...]:
        """Enumera os ramos que possuem definição de linhagem registrada."""
        raise NotImplementedError


class RepositorioRamosEmMemoria(RepositorioRamos):
    """Linhagem mantida apenas em memória, para testes e execução efêmera."""

    def __init__(self) -> None:
        self._definicoes: dict[str, DefinicaoRamo] = {}
        self._lock: threading.RLock = threading.RLock()

    def registrar(self, definicao: DefinicaoRamo) -> None:
        """Grava a definição, recusando a redefinição de um ramo existente."""
        with self._lock:
            if definicao.ramo_id in self._definicoes:
                raise GraphowError(
                    f"O ramo '{definicao.ramo_id}' ja possui linhagem registrada",
                    {"ramo_id": definicao.ramo_id},
                )
            self._definicoes[definicao.ramo_id] = definicao

    def obter_definicao(self, ramo_id: str) -> DefinicaoRamo | None:
        """Consulta a definição do ramo informado."""
        with self._lock:
            return self._definicoes.get(ramo_id)

    def listar_ramos_derivados(self) -> tuple[str, ...]:
        """Enumera os ramos derivados em ordem estável."""
        with self._lock:
            return tuple(sorted(self._definicoes))


class RepositorioRamosSQLite(RepositorioRamos):
    """Linhagem persistida no mesmo arquivo do log de eventos."""

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao: sqlite3.Connection = conexao
        self._lock: threading.RLock = threading.RLock()
        self._configurar_schema()

    def _configurar_schema(self) -> None:
        """Cria a tabela de ramos, se ainda não existir."""
        with self._lock:
            self._conexao.execute(DDL_TABELA_RAMOS)

    def registrar(self, definicao: DefinicaoRamo) -> None:
        """Grava a definição, recusando a redefinição de um ramo existente."""
        with self._lock:
            try:
                self._conexao.execute(
                    "INSERT INTO ramos (ramo_id, ramo_base, seq_corte, evento_corte_id) VALUES (?, ?, ?, ?);",
                    (definicao.ramo_id, definicao.ramo_base, definicao.seq_corte, definicao.evento_corte_id),
                )
            except sqlite3.IntegrityError as erro:
                raise GraphowError(
                    f"O ramo '{definicao.ramo_id}' ja possui linhagem registrada",
                    {"ramo_id": definicao.ramo_id, "detalhe": str(erro)},
                ) from erro

    def obter_definicao(self, ramo_id: str) -> DefinicaoRamo | None:
        """Consulta a definição do ramo informado."""
        with self._lock:
            linha = self._conexao.execute(
                "SELECT ramo_id, ramo_base, seq_corte, evento_corte_id FROM ramos WHERE ramo_id = ?;",
                (ramo_id,),
            ).fetchone()
        if linha is None:
            return None
        return DefinicaoRamo(
            ramo_id=str(linha[0]),
            ramo_base=str(linha[1]),
            seq_corte=int(linha[2]),
            evento_corte_id=str(linha[3]) if linha[3] is not None else None,
        )

    def listar_ramos_derivados(self) -> tuple[str, ...]:
        """Enumera os ramos derivados em ordem estável."""
        with self._lock:
            linhas = self._conexao.execute("SELECT ramo_id FROM ramos ORDER BY ramo_id;").fetchall()
            return tuple(str(linha[0]) for linha in linhas)


class ResolvedorLinhagem:
    """Consulta pura que descreve de onde cada ramo herda os próprios eventos."""

    def __init__(self, repositorio_ramos: RepositorioRamos) -> None:
        self._repositorio: RepositorioRamos = repositorio_ramos

    def resolver_cadeia(self, ramo_id: str) -> tuple[DefinicaoRamo, ...]:
        """Devolve a cadeia de heranças, do ramo consultado até a raiz."""
        cadeia: list[DefinicaoRamo] = []
        visitados: set[str] = {ramo_id}
        atual = ramo_id
        for _ in range(PROFUNDIDADE_MAXIMA_DE_LINHAGEM):
            definicao = self._repositorio.obter_definicao(atual)
            if definicao is None or definicao.ramo_base in visitados:
                return tuple(cadeia)
            cadeia.append(definicao)
            visitados.add(definicao.ramo_base)
            atual = definicao.ramo_base
        return tuple(cadeia)

    def obter_seq_corte(self, ramo_id: str) -> int:
        """Sequência a partir da qual o ramo passa a ter eventos próprios."""
        definicao = self._repositorio.obter_definicao(ramo_id)
        return definicao.seq_corte if definicao else 0
