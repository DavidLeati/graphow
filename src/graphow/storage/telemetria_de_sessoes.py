"""A telemetria das sessões `claude -p` que o orquestrador roda, numa tabela própria do banco.

Cada sessão de planejador, executor ou verificador vira uma linha: o Goal, o
papel, a fatia, a tentativa, a sessão, o modelo, os instantes, o custo, os
tokens, os turnos e como terminou. No grafo, a execução de agente virava nó
`Run`, que era 30% dos nós e poluía a vista; aqui ela fica ao lado do log, no
mesmo arquivo e fora dele.

O custo de uma sessão retomada com `--resume` é acumulado: o resultado de cada
invocação traz o total da sessão até ali. Por isso o total do Goal soma, por
sessão, o último custo que ela declarou. O que não se sabe fica None: a
invocação que morreu sem resultado gastou, só não disse quanto, e entra na
contagem de custos desconhecidos em vez de valer zero, sem apagar o que a
sessão já tinha declarado.

A linha nasce antes de a sessão abrir, `em_andamento`, e é atualizada quando
ela termina. Se o orquestrador cai no meio, a linha fica, com o stream da
invocação, e a retomada a recupera dele (orquestrador/sessoes_de_papel.py).
O banco de antes da coluna `estado` ganha a coluna ao abrir, com `concluida`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
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
        comando_json TEXT NOT NULL DEFAULT '[]',
        estado TEXT NOT NULL DEFAULT 'concluida'
    );
"""
ESTADO_EM_ANDAMENTO: str = "em_andamento"
ESTADO_CONCLUIDA: str = "concluida"
ESTADO_RECUPERADA: str = "recuperada"
COLUNA_DO_ESTADO: str = "estado"
DDL_COLUNA_DO_ESTADO: str = (
    f"ALTER TABLE telemetria_de_sessoes ADD COLUMN {COLUNA_DO_ESTADO} TEXT NOT NULL DEFAULT '{ESTADO_CONCLUIDA}';"
)
DDL_INDICE_DO_GOAL: str = "CREATE INDEX IF NOT EXISTS idx_telemetria_goal ON telemetria_de_sessoes (id_goal, id);"
COLUNAS: tuple[str, ...] = (
    "id_goal", "papel", "fatia", "tentativa", "session_id", "retomada", "modelo", "inicio", "fim", "duracao_s",
    "custo_usd", "tokens_json", "turnos", "codigo_saida", "tempo_esgotado", "is_error", "erro", "arquivo_stream",
    "comando_json", COLUNA_DO_ESTADO,
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
    estado: str = ESTADO_CONCLUIDA
    id_linha: int = field(default=0, compare=False)

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
            json.dumps(list(self.comando), ensure_ascii=False), self.estado,
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
            comando=tuple(json.loads(valores["comando_json"] or "[]")), estado=str(valores[COLUNA_DO_ESTADO]),
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
    em_andamento: int = 0


def totalizar(registros: Sequence[SessaoRegistrada]) -> TotaisDeTelemetria:
    """Soma por sessão o último custo e os últimos tokens que ela declarou (eles acumulam no `--resume`).

    A sessão cuja última invocação morreu sem dizer o custo conta o que já tinha
    declarado e entra também nos custos desconhecidos.
    """
    grupos: dict[str, list[SessaoRegistrada]] = {}
    for indice, registro in enumerate(registros):
        grupos.setdefault(registro.session_id or f"sem-sessao-{indice}", []).append(registro)
    return TotaisDeTelemetria(
        invocacoes=len(registros),
        sessoes=len({registro.session_id for registro in registros if registro.session_id}),
        custo_usd=sum(_ultimo_custo(grupo) for grupo in grupos.values()),
        custos_desconhecidos=sum(1 for grupo in grupos.values() if grupo[-1].custo_usd is None),
        tokens=sum(_ultimos_tokens(grupo) for grupo in grupos.values()),
        duracao_s=sum(registro.duracao_s for registro in registros),
        com_erro=sum(1 for registro in registros if registro.is_error),
        em_andamento=sum(1 for registro in registros if registro.estado == ESTADO_EM_ANDAMENTO),
    )


def _ultimo_custo(invocacoes: Sequence[SessaoRegistrada]) -> float:
    """O último custo declarado pelas invocações de uma sessão; zero quando nenhuma o disse."""
    return next((registro.custo_usd for registro in reversed(invocacoes) if registro.custo_usd is not None), 0.0)


def _ultimos_tokens(invocacoes: Sequence[SessaoRegistrada]) -> int:
    """Os últimos tokens declarados pelas invocações de uma sessão; zero quando nenhuma os disse."""
    return next((registro.tokens_total for registro in reversed(invocacoes) if registro.tokens_total is not None), 0)


class RepositorioTelemetria:
    """A tabela de telemetria numa conexão SQLite: a do banco de eventos, ou uma própria nos testes."""

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao: sqlite3.Connection = conexao
        self._lock: threading.RLock = threading.RLock()
        with self._lock:
            self._conexao.execute(DDL_TABELA_TELEMETRIA)
            self._conexao.execute(DDL_INDICE_DO_GOAL)
            colunas = {str(linha[1]) for linha in self._conexao.execute("PRAGMA table_info(telemetria_de_sessoes);")}
            if COLUNA_DO_ESTADO not in colunas:
                self._conexao.execute(DDL_COLUNA_DO_ESTADO)
            self._confirmar()

    def _confirmar(self) -> None:
        """Fecha a transação aberta, se há uma."""
        if self._conexao.in_transaction:
            self._conexao.commit()

    def registrar(self, registro: SessaoRegistrada) -> int:
        """Acrescenta a invocação e devolve o id da linha."""
        marcadores = ", ".join("?" for _ in COLUNAS)
        with self._lock:
            cursor = self._conexao.execute(
                f"INSERT INTO telemetria_de_sessoes ({', '.join(COLUNAS)}) VALUES ({marcadores});", registro.em_linha()
            )
            self._confirmar()
            return int(cursor.lastrowid or 0)

    def atualizar(self, id_linha: int, registro: SessaoRegistrada) -> None:
        """Reescreve a linha da invocação: a que nasceu em andamento recebe o fim dela."""
        atribuicoes = ", ".join(f"{coluna} = ?" for coluna in COLUNAS)
        with self._lock:
            self._conexao.execute(
                f"UPDATE telemetria_de_sessoes SET {atribuicoes} WHERE id = ?;", (*registro.em_linha(), id_linha)
            )
            self._confirmar()

    def listar(self, id_goal: str) -> tuple[SessaoRegistrada, ...]:
        """As invocações do Goal, na ordem em que foram registradas."""
        with self._lock:
            cursor = self._conexao.execute(
                f"SELECT id, {', '.join(COLUNAS)} FROM telemetria_de_sessoes WHERE id_goal = ? ORDER BY id ASC;", (id_goal,)
            )
            return tuple(replace(SessaoRegistrada.da_linha(linha[1:]), id_linha=int(linha[0])) for linha in cursor.fetchall())

    def totais(self, id_goal: str) -> TotaisDeTelemetria:
        """Os totais do Goal inteiro."""
        return totalizar(self.listar(id_goal))
