"""A telemetria das sessões `claude -p` que o orquestrador roda, numa tabela própria do banco.

Cada sessão de planejador, executor ou verificador vira uma linha: o Goal, o
papel, a fatia, a tentativa, a sessão, o modelo, os instantes, o custo, os
tokens, os turnos e como terminou. No grafo, a execução de agente virava nó
`Run`, que era 30% dos nós e poluía a vista; aqui ela fica ao lado do log, no
mesmo arquivo e fora dele.

O custo de uma sessão retomada com `--resume` é acumulado: o resultado de cada
invocação traz o total da sessão até ali. Por isso o total do Goal soma, por
sessão, só a última invocação dela. O que não se sabe fica None: a invocação
que morreu sem resultado gastou, só não disse quanto, e entra na contagem de
custos desconhecidos em vez de valer zero.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import sqlite3
import threading
from typing import Any

DDL_TABELA_TELEMETRIA: str = """
    CREATE TABLE IF NOT EXISTS telemetria_de_sessoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_goal TEXT NOT NULL,
        papel TEXT NOT NULL,
        fatia TEXT NOT NULL DEFAULT '',
        tentativa INTEGER NOT NULL DEFAULT 1,
        session_id TEXT NOT NULL DEFAULT '',
        retomada INTEGER NOT NULL DEFAULT 0,
        modelo TEXT NOT NULL DEFAULT '',
        inicio TEXT NOT NULL DEFAULT '',
        fim TEXT NOT NULL DEFAULT '',
        duracao_s REAL NOT NULL DEFAULT 0,
        custo_usd REAL,
        tokens_json TEXT,
        turnos INTEGER,
        codigo_saida INTEGER,
        tempo_esgotado INTEGER NOT NULL DEFAULT 0,
        is_error INTEGER NOT NULL DEFAULT 0,
        erro TEXT NOT NULL DEFAULT '',
        arquivo_stream TEXT NOT NULL DEFAULT '',
        comando_json TEXT NOT NULL DEFAULT '[]'
    );
"""
DDL_INDICE_DO_GOAL: str = "CREATE INDEX IF NOT EXISTS idx_telemetria_goal ON telemetria_de_sessoes (id_goal, id);"
COLUNAS: tuple[str, ...] = (
    "id_goal", "papel", "fatia", "tentativa", "session_id", "retomada", "modelo", "inicio", "fim", "duracao_s",
    "custo_usd", "tokens_json", "turnos", "codigo_saida", "tempo_esgotado", "is_error", "erro", "arquivo_stream",
    "comando_json",
)
CHAVE_DO_TOTAL_DE_TOKENS: str = "total"


@dataclass(frozen=True)
class SessaoRegistrada:
    """Uma invocação de `claude -p` do orquestrador, como a tabela a guarda."""

    id_goal: str
    papel: str
    fatia: str = ""
    tentativa: int = 1
    session_id: str = ""
    retomada: bool = False
    modelo: str = ""
    inicio: str = ""
    fim: str = ""
    duracao_s: float = 0.0
    custo_usd: float | None = None
    tokens: Mapping[str, int] | None = None
    turnos: int | None = None
    codigo_saida: int | None = None
    tempo_esgotado: bool = False
    is_error: bool = False
    erro: str = ""
    arquivo_stream: str = ""
    comando: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tokens_total(self) -> int | None:
        """A soma das quatro categorias, quando o resultado as disse."""
        return None if self.tokens is None else int(self.tokens.get(CHAVE_DO_TOTAL_DE_TOKENS, 0))

    def em_linha(self) -> tuple[Any, ...]:
        """Os valores na ordem das colunas."""
        return (
            self.id_goal, self.papel, self.fatia, self.tentativa, self.session_id, int(self.retomada), self.modelo,
            self.inicio, self.fim, self.duracao_s, self.custo_usd,
            None if self.tokens is None else json.dumps(dict(self.tokens), sort_keys=True), self.turnos,
            self.codigo_saida, int(self.tempo_esgotado), int(self.is_error), self.erro, self.arquivo_stream,
            json.dumps(list(self.comando), ensure_ascii=False),
        )

    @classmethod
    def da_linha(cls, linha: Sequence[Any]) -> "SessaoRegistrada":
        """A linha lida da tabela, na ordem das colunas."""
        valores = dict(zip(COLUNAS, linha))
        tokens = json.loads(valores["tokens_json"]) if valores["tokens_json"] else None
        return cls(
            id_goal=str(valores["id_goal"]), papel=str(valores["papel"]), fatia=str(valores["fatia"]),
            tentativa=int(valores["tentativa"]), session_id=str(valores["session_id"]),
            retomada=bool(valores["retomada"]), modelo=str(valores["modelo"]), inicio=str(valores["inicio"]),
            fim=str(valores["fim"]), duracao_s=float(valores["duracao_s"]), custo_usd=valores["custo_usd"],
            tokens=tokens, turnos=valores["turnos"], codigo_saida=valores["codigo_saida"],
            tempo_esgotado=bool(valores["tempo_esgotado"]), is_error=bool(valores["is_error"]),
            erro=str(valores["erro"]), arquivo_stream=str(valores["arquivo_stream"]),
            comando=tuple(json.loads(valores["comando_json"] or "[]")),
        )


@dataclass(frozen=True)
class TotaisDeTelemetria:
    """O que as sessões de um Goal (ou de um papel dele) custaram, com o que não se sabe à parte."""

    invocacoes: int = 0
    sessoes: int = 0
    custo_usd: float = 0.0
    custos_desconhecidos: int = 0
    tokens: int = 0
    duracao_s: float = 0.0
    com_erro: int = 0


def totalizar(registros: Sequence[SessaoRegistrada]) -> TotaisDeTelemetria:
    """Soma por sessão a última invocação dela (o custo e os tokens acumulam no `--resume`)."""
    ultimas: dict[str, SessaoRegistrada] = {}
    sem_sessao = [registro for registro in registros if not registro.session_id]
    for registro in registros:
        if registro.session_id:
            ultimas[registro.session_id] = registro
    contadas = [*ultimas.values(), *sem_sessao]
    return TotaisDeTelemetria(
        invocacoes=len(registros),
        sessoes=len(ultimas),
        custo_usd=sum(registro.custo_usd for registro in contadas if registro.custo_usd is not None),
        custos_desconhecidos=sum(1 for registro in contadas if registro.custo_usd is None),
        tokens=sum(registro.tokens_total or 0 for registro in contadas),
        duracao_s=sum(registro.duracao_s for registro in registros),
        com_erro=sum(1 for registro in registros if registro.is_error),
    )


class RepositorioTelemetria:
    """A tabela de telemetria numa conexão SQLite: a do banco de eventos, ou uma própria nos testes."""

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao: sqlite3.Connection = conexao
        self._lock: threading.RLock = threading.RLock()
        with self._lock:
            self._conexao.execute(DDL_TABELA_TELEMETRIA)
            self._conexao.execute(DDL_INDICE_DO_GOAL)

    def registrar(self, registro: SessaoRegistrada) -> None:
        """Acrescenta a invocação; a tabela só cresce."""
        marcadores = ", ".join("?" for _ in COLUNAS)
        with self._lock:
            self._conexao.execute(
                f"INSERT INTO telemetria_de_sessoes ({', '.join(COLUNAS)}) VALUES ({marcadores});", registro.em_linha()
            )
            if self._conexao.in_transaction:
                self._conexao.commit()

    def listar(self, id_goal: str) -> tuple[SessaoRegistrada, ...]:
        """As invocações do Goal, na ordem em que foram registradas."""
        with self._lock:
            cursor = self._conexao.execute(
                f"SELECT {', '.join(COLUNAS)} FROM telemetria_de_sessoes WHERE id_goal = ? ORDER BY id ASC;", (id_goal,)
            )
            return tuple(SessaoRegistrada.da_linha(linha) for linha in cursor.fetchall())

    def totais(self, id_goal: str) -> TotaisDeTelemetria:
        """Os totais do Goal inteiro."""
        return totalizar(self.listar(id_goal))
