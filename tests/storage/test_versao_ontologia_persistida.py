"""A versão da ontologia sobrevive à ida e volta do banco, inclusive em bancos antigos.

Ver achado A-17.
"""

from pathlib import Path
import sqlite3

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.ontologia import VERSAO_ONTOLOGIA, VERSAO_ONTOLOGIA_DESCONHECIDA
from graphow.core.types import PapelAutor
from graphow.storage.sqlite_store import SQLiteEventStore

DDL_TABELA_ANTIGA: str = """
    CREATE TABLE eventos (
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
        trace_id TEXT
    );
"""


def _evento(seq: int) -> EventoLog:
    """Evento mínimo de criação de nó."""
    return EventoLog.criar(
        DadosCriacaoEvento(
            seq=seq,
            autor="david",
            papel=PapelAutor.HUMANO,
            tipo_evento=TipoEvento.NO_CRIADO,
            payload={"id": f"n{seq}", "tipo": "Note", "rotulo": "Nota"},
        )
    )


def test_versao_sobrevive_a_ida_e_volta_do_banco_nominal(tmp_path: Path) -> None:
    """O que foi escrito com esta ontologia volta declarando esta ontologia."""
    caminho = tmp_path / "graphow.db"
    with SQLiteEventStore(str(caminho)) as store:
        store.append_evento(_evento(1))

    with SQLiteEventStore(str(caminho)) as store:
        lidos = store.ler_eventos("main")

    assert [e.versao_ontologia for e in lidos] == [VERSAO_ONTOLOGIA]


def test_banco_anterior_a_coluna_e_migrado_e_lido_edge_case(tmp_path: Path) -> None:
    """Caso de borda: linha escrita antes da coluna não pode virar erro nem mentira."""
    caminho = tmp_path / "antigo.db"
    conexao = sqlite3.connect(str(caminho))
    conexao.execute(DDL_TABELA_ANTIGA)
    conexao.execute(
        "INSERT INTO eventos VALUES ('e1', 1, '2026-01-01T00:00:00+00:00', 'david', "
        "'humano', 'humano', 'no_criado', '{}', 'main', NULL, NULL);"
    )
    conexao.commit()
    conexao.close()

    with SQLiteEventStore(str(caminho)) as store:
        antigos = store.ler_eventos("main")
        store.append_evento(_evento(2))
        todos = store.ler_eventos("main")

    assert antigos[0].versao_ontologia == VERSAO_ONTOLOGIA_DESCONHECIDA
    assert [e.versao_ontologia for e in todos] == [VERSAO_ONTOLOGIA_DESCONHECIDA, VERSAO_ONTOLOGIA]
