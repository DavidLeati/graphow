"""Testes unitários para o diagnóstico e o reparo de sequências duplicadas."""

from pathlib import Path
import sqlite3

from graphow.storage.reparo_sequencia import (
    AcessoSequenciasSQLite,
    AnalisadorSequencias,
    ReparadorSequencias,
)

DDL_MINIMO: str = """
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


def _inserir(conexao: sqlite3.Connection, id_evento: str, seq: int, ramo: str, parent: str | None) -> None:
    """Grava um evento cru, com payload determinado pelo evento de origem."""
    conexao.execute(
        "INSERT INTO eventos VALUES (?, ?, ?, 'david', 'humano', 'humano', 'no_criado', ?, ?, ?, NULL);",
        (id_evento, seq, f"2026-08-26T00:00:{seq:02d}", f'{{"id":"{parent or id_evento}"}}', ramo, parent),
    )


def _montar_banco_com_fork_duplicado(caminho: Path) -> None:
    """Reproduz o estado real: um fork criado duas vezes sobre o mesmo ramo."""
    conexao = sqlite3.connect(str(caminho), isolation_level=None)
    conexao.execute(DDL_MINIMO)
    for posicao in range(1, 4):
        _inserir(conexao, f"origem-{posicao}", posicao, "main", None)
    for copia in ("a", "b"):
        for posicao in range(1, 4):
            _inserir(conexao, f"fork-{copia}-{posicao}", posicao, "experimento", f"origem-{posicao}")
    conexao.close()


def test_diagnostica_ramo_integro_sem_reparo_nominal(tmp_path: Path) -> None:
    """Um ramo contíguo e sem duplicatas não demanda reparo."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    diagnostico = AnalisadorSequencias(AcessoSequenciasSQLite(caminho)).diagnosticar("main")
    assert diagnostico.total_eventos == 3
    assert diagnostico.posicoes_duplicadas == 0
    assert diagnostico.precisa_reparo is False


def test_diagnostica_copias_de_fork_repetido_nominal(tmp_path: Path) -> None:
    """As réplicas do mesmo evento de origem são identificadas para remoção."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    diagnostico = AnalisadorSequencias(AcessoSequenciasSQLite(caminho)).diagnosticar("experimento")
    assert diagnostico.total_eventos == 6
    assert diagnostico.posicoes_duplicadas == 3
    assert len(diagnostico.ids_a_remover) == 3
    assert diagnostico.precisa_reparo is True


def test_reparo_deixa_sequencia_contigua_e_unica(tmp_path: Path) -> None:
    """Após o reparo o ramo tem numeração 1..N sem repetição."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    acesso = AcessoSequenciasSQLite(caminho)
    ReparadorSequencias(acesso).reparar(AnalisadorSequencias(acesso).diagnosticar("experimento"))

    registros = acesso.listar_registros("experimento")
    sequencias = [registro.seq for registro in registros]
    assert sequencias == [1, 2, 3]
    assert len(set(sequencias)) == 3


def test_reparo_e_idempotente_edge_case(tmp_path: Path) -> None:
    """Caso de borda: reexecutar o reparo num ramo já saudável não muda nada."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    acesso = AcessoSequenciasSQLite(caminho)
    analisador = AnalisadorSequencias(acesso)
    ReparadorSequencias(acesso).reparar(analisador.diagnosticar("experimento"))

    segundo_diagnostico = analisador.diagnosticar("experimento")
    assert segundo_diagnostico.precisa_reparo is False
    ReparadorSequencias(acesso).reparar(segundo_diagnostico)
    assert [registro.seq for registro in acesso.listar_registros("experimento")] == [1, 2, 3]


def test_banco_reparado_aceita_o_indice_unico_edge_case(tmp_path: Path) -> None:
    """Caso de borda: depois do reparo o índice de unicidade pode ser criado."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    acesso = AcessoSequenciasSQLite(caminho)
    for diagnostico in AnalisadorSequencias(acesso).diagnosticar_todos_os_ramos():
        ReparadorSequencias(acesso).reparar(diagnostico)

    conexao = sqlite3.connect(str(caminho))
    conexao.execute("CREATE UNIQUE INDEX idx_teste ON eventos (ramo_id, seq);")
    conexao.close()


def test_diagnostico_de_todos_os_ramos_cobre_o_banco_inteiro(tmp_path: Path) -> None:
    """A varredura enxerga cada ramo presente no log."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    diagnosticos = AnalisadorSequencias(AcessoSequenciasSQLite(caminho)).diagnosticar_todos_os_ramos()
    assert {diagnostico.ramo_id for diagnostico in diagnosticos} == {"main", "experimento"}
