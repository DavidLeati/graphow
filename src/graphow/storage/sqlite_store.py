"""Implementação SQLite append-only do repositório de eventos."""

from collections.abc import Sequence
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from graphow.core.events import EventoLog, TipoEvento
from graphow.core.exceptions import ErroConflitoDeSequencia, GraphowError
from graphow.core.ontologia import VERSAO_ONTOLOGIA_DESCONHECIDA
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.storage.interfaces import RepositorioEventos

# Sem checkpoint automático o -wal cresce indefinidamente e passa a conter eventos
# que o arquivo .db sozinho não enxerga. Ver auditoria F-03.
PAGINAS_ATE_CHECKPOINT_AUTOMATICO: int = 256

COLUNAS_EVENTO: str = (
    "id, seq, timestamp_utc, autor, papel, origem, "
    "tipo_evento, payload_json, ramo_id, parent_evento_id, trace_id, versao_ontologia"
)

# Bancos escritos antes de A-17 nao tem a coluna. Acrescenta-la mantem as linhas
# antigas com NULL, que a leitura traduz para "versao desconhecida".
COLUNA_VERSAO_ONTOLOGIA: str = "versao_ontologia"
DDL_COLUNA_VERSAO_ONTOLOGIA: str = (
    f"ALTER TABLE eventos ADD COLUMN {COLUNA_VERSAO_ONTOLOGIA} TEXT;"
)

DDL_TABELA_EVENTOS: str = """
    CREATE TABLE IF NOT EXISTS eventos (
        id TEXT PRIMARY KEY,
        seq INTEGER NOT NULL,
        timestamp_utc TEXT NOT NULL,
        autor TEXT NOT NULL,
        papel TEXT NOT NULL,
        origem TEXT NOT NULL,
        tipo_evento TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        ramo_id TEXT NOT NULL,
        parent_evento_id TEXT,
        trace_id TEXT,
        versao_ontologia TEXT
    );
"""

# A unicidade de (ramo_id, seq) e o que torna ORDER BY seq uma ordem total. Sem ela
# um fork repetido duplica posicoes e o replay deixa de ser deterministico. Ver F-06.
DDL_INDICE_SEQ_UNICO: str = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_eventos_ramo_seq_unico ON eventos (ramo_id, seq);"
)


class SQLiteEventStore(RepositorioEventos):
    """Armazenamento persistente local-first em SQLite para eventos append-only."""

    def __init__(self, caminho_banco: str | Path = ":memory:") -> None:
        self._caminho_banco: str = str(caminho_banco)
        self._lock: threading.RLock = threading.RLock()
        self._conexao: sqlite3.Connection = sqlite3.connect(
            self._caminho_banco,
            check_same_thread=False,
            isolation_level=None,
        )
        self._configurar_pragmas()
        self._configurar_schema()

    def __enter__(self) -> "SQLiteEventStore":
        """Permite uso como gerenciador de contexto, garantindo o fechamento."""
        return self

    def __exit__(self, tipo_excecao: object, valor: object, traceback: object) -> None:
        """Consolida o WAL e fecha a conexão ao sair do bloco."""
        self.fechar()

    @property
    def conexao(self) -> sqlite3.Connection:
        """Conexão compartilhada, para adaptadores que residem no mesmo arquivo."""
        return self._conexao

    @property
    def caminho_banco(self) -> str:
        """Caminho do arquivo SQLite em uso por este repositório."""
        return self._caminho_banco

    def _configurar_pragmas(self) -> None:
        """Define modo de journal, checkpoint automático e durabilidade da conexão."""
        with self._lock:
            cursor: sqlite3.Cursor = self._conexao.cursor()
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute(f"PRAGMA wal_autocheckpoint = {PAGINAS_ATE_CHECKPOINT_AUTOMATICO};")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")

    def _configurar_schema(self) -> None:
        """Inicializa tabelas e índices necessários no SQLite."""
        with self._lock:
            cursor: sqlite3.Cursor = self._conexao.cursor()
            cursor.execute(DDL_TABELA_EVENTOS)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_ramo_seq ON eventos (ramo_id, seq);")
            self._garantir_coluna_de_versao(cursor)
            self._criar_indice_unico_de_sequencia(cursor)

    def _garantir_coluna_de_versao(self, cursor: sqlite3.Cursor) -> None:
        """Acrescenta a coluna de versao da ontologia a bancos anteriores a A-17."""
        cursor.execute("PRAGMA table_info(eventos);")
        colunas = {str(linha[1]) for linha in cursor.fetchall()}
        if COLUNA_VERSAO_ONTOLOGIA in colunas:
            return
        cursor.execute(DDL_COLUNA_VERSAO_ONTOLOGIA)

    def _criar_indice_unico_de_sequencia(self, cursor: sqlite3.Cursor) -> None:
        """Cria o índice único, tolerando bancos legados que ainda têm duplicatas."""
        try:
            cursor.execute(DDL_INDICE_SEQ_UNICO)
        except sqlite3.IntegrityError as erro:
            raise ErroConflitoDeSequencia(
                "O banco possui sequencias duplicadas e nao aceita o indice unico. "
                "Rode 'graphow reparar-sequencias' antes de continuar",
                {"caminho_banco": self._caminho_banco, "detalhe": str(erro)},
            ) from erro

    def append_evento(self, evento: EventoLog) -> None:
        """Insere o evento de forma append-only no banco SQLite."""
        self.append_eventos((evento,))

    def append_eventos(self, eventos: Sequence[EventoLog]) -> None:
        """Insere o lote inteiro em uma única transação: ou todos, ou nenhum."""
        if not eventos:
            return
        with self._lock:
            self._executar_insercao_transacional(eventos)

    def _executar_insercao_transacional(self, eventos: Sequence[EventoLog]) -> None:
        """Envolve a inserção em BEGIN IMMEDIATE, revertendo qualquer falha parcial."""
        cursor: sqlite3.Cursor = self._conexao.cursor()
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            cursor.executemany(
                f"INSERT INTO eventos ({COLUNAS_EVENTO}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                [self._parametros_insercao_evento(evento) for evento in eventos],
            )
            cursor.execute("COMMIT;")
        except sqlite3.IntegrityError as erro:
            cursor.execute("ROLLBACK;")
            raise ErroConflitoDeSequencia(
                f"Posicao de sequencia ja ocupada no ramo: {erro}",
                {"ramo_id": eventos[0].ramo_id, "seq_inicial": str(eventos[0].seq)},
            ) from erro
        except sqlite3.Error as erro:
            cursor.execute("ROLLBACK;")
            raise GraphowError(
                f"Falha ao persistir eventos no SQLite: {erro}",
                {"total_eventos": str(len(eventos))},
            ) from erro

    def _parametros_insercao_evento(self, evento: EventoLog) -> tuple[Any, ...]:
        """Converte campos do evento em tupla posicional para SQL."""
        return (
            evento.id,
            evento.seq,
            evento.timestamp_utc,
            evento.autor,
            evento.papel.value,
            evento.origem.value,
            evento.tipo_evento.value,
            evento.serializar_payload_json(),
            evento.ramo_id,
            evento.parent_evento_id,
            evento.trace_id,
            evento.versao_ontologia,
        )

    def ler_eventos(self, ramo_id: str = "main") -> list[EventoLog]:
        """Lê todos os eventos de um ramo em ordem crescente de sequência."""
        return self._consultar_eventos(
            f"SELECT {COLUNAS_EVENTO} FROM eventos WHERE ramo_id = ? ORDER BY seq ASC;",
            (ramo_id,),
        )

    def ler_eventos_ate_seq(self, ramo_id: str, seq_limite: int) -> list[EventoLog]:
        """Lê eventos de um ramo até o limite superior de sequência inclusive."""
        return self._consultar_eventos(
            f"SELECT {COLUNAS_EVENTO} FROM eventos WHERE ramo_id = ? AND seq <= ? ORDER BY seq ASC;",
            (ramo_id, seq_limite),
        )

    def ler_eventos_desde_seq(self, ramo_id: str, seq_exclusivo: int) -> list[EventoLog]:
        """Lê apenas os eventos posteriores à sequência informada, para atualização incremental."""
        return self._consultar_eventos(
            f"SELECT {COLUNAS_EVENTO} FROM eventos WHERE ramo_id = ? AND seq > ? ORDER BY seq ASC;",
            (ramo_id, seq_exclusivo),
        )

    def _consultar_eventos(self, sql: str, parametros: tuple[Any, ...]) -> list[EventoLog]:
        """Executa a consulta e desserializa cada linha em um evento imutável."""
        with self._lock:
            cursor: sqlite3.Cursor = self._conexao.cursor()
            cursor.execute(sql, parametros)
            return [self._converter_linha_para_evento(linha) for linha in cursor.fetchall()]

    def obter_ultimo_seq(self, ramo_id: str = "main") -> int:
        """Consulta o maior número de sequência no ramo especificado."""
        with self._lock:
            cursor: sqlite3.Cursor = self._conexao.cursor()
            cursor.execute("SELECT COALESCE(MAX(seq), 0) FROM eventos WHERE ramo_id = ?;", (ramo_id,))
            resultado = cursor.fetchone()
            if resultado is None or resultado[0] is None:
                return 0
            return int(resultado[0])

    def listar_ramos(self) -> list[str]:
        """Retorna a lista distinta de todos os ramos existentes."""
        with self._lock:
            cursor: sqlite3.Cursor = self._conexao.cursor()
            cursor.execute("SELECT DISTINCT ramo_id FROM eventos ORDER BY ramo_id ASC;")
            return [str(linha[0]) for linha in cursor.fetchall()]

    def obter_evento_por_id(self, id_evento: str) -> EventoLog | None:
        """Localiza e reconstrói um evento pelo ID."""
        encontrados = self._consultar_eventos(
            f"SELECT {COLUNAS_EVENTO} FROM eventos WHERE id = ?;", (id_evento,)
        )
        return encontrados[0] if encontrados else None

    def _converter_linha_para_evento(self, linha: tuple[Any, ...]) -> EventoLog:
        """Desserializa registro relacional em EventoLog imutável."""
        payload_dict: dict[str, Any] = json.loads(linha[7])
        return EventoLog(
            id=str(linha[0]),
            seq=int(linha[1]),
            timestamp_utc=str(linha[2]),
            autor=str(linha[3]),
            papel=PapelAutor(str(linha[4])),
            origem=OrigemEvento(str(linha[5])),
            tipo_evento=TipoEvento(str(linha[6])),
            payload=payload_dict,
            ramo_id=str(linha[8]),
            parent_evento_id=str(linha[9]) if linha[9] is not None else None,
            trace_id=str(linha[10]) if linha[10] is not None else None,
            versao_ontologia=str(linha[11]) if linha[11] is not None else VERSAO_ONTOLOGIA_DESCONHECIDA,
        )

    def consolidar_wal(self) -> None:
        """Move todo o conteúdo do WAL para o arquivo principal do banco."""
        with self._lock:
            try:
                self._conexao.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except sqlite3.OperationalError as erro:
                raise GraphowError(
                    f"Falha ao consolidar o WAL do banco de eventos: {erro}",
                    {"caminho_banco": self._caminho_banco},
                ) from erro

    def fechar(self) -> None:
        """Consolida o WAL e fecha a conexão, para não deixar eventos fora do .db."""
        with self._lock:
            self.consolidar_wal()
            self._conexao.close()
