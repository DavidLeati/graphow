"""Testes unitários para o diagnóstico e o reparo de sequências duplicadas."""

from pathlib import Path
import sqlite3

from graphow.storage.instantaneos import DDL_TABELA_INSTANTANEOS
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


def _montar_banco_com_fork_por_ponteiro(caminho: Path) -> None:
    """Estado saudável de hoje: o fork aponta para o seq 41 do main e numera os próprios eventos depois dele."""
    conexao = sqlite3.connect(str(caminho), isolation_level=None)
    conexao.execute(DDL_MINIMO)
    conexao.execute("CREATE TABLE ramos (ramo_id TEXT PRIMARY KEY, ramo_base TEXT NOT NULL, seq_corte INTEGER NOT NULL);")
    conexao.execute("INSERT INTO ramos VALUES ('exp', 'main', 41);")
    for posicao in range(1, 51):
        _inserir(conexao, f"main-{posicao}", posicao, "main", None)
    for posicao in range(42, 46):
        _inserir(conexao, f"exp-{posicao}", posicao, "exp", None)
    conexao.close()


def test_fork_por_ponteiro_saudavel_nao_pede_reparo_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o reparo numerava o ramo derivado a partir de 1 e o reescrevia antes do corte."""
    caminho = tmp_path / "graphow.db"
    _montar_banco_com_fork_por_ponteiro(caminho)

    diagnostico = AnalisadorSequencias(AcessoSequenciasSQLite(caminho)).diagnosticar("exp")

    assert diagnostico.precisa_reparo is False


def test_reparo_de_fork_por_ponteiro_numera_depois_do_corte_edge_case(tmp_path: Path) -> None:
    """Caso de borda: uma lacuna no ramo derivado se fecha a partir de seq_corte + 1, não de 1."""
    caminho = tmp_path / "graphow.db"
    _montar_banco_com_fork_por_ponteiro(caminho)
    conexao = sqlite3.connect(str(caminho), isolation_level=None)
    conexao.execute("UPDATE eventos SET seq = 60 WHERE id = 'exp-45';")
    conexao.close()
    acesso = AcessoSequenciasSQLite(caminho)

    ReparadorSequencias(acesso).reparar(AnalisadorSequencias(acesso).diagnosticar("exp"))

    assert [registro.seq for registro in acesso.listar_registros("exp")] == [42, 43, 44, 45]


def test_reparo_apaga_os_instantaneos_da_projecao_edge_case(tmp_path: Path) -> None:
    """Os instantâneos foram dobrados sobre o log de antes do reparo e não podem sobreviver a ele."""
    caminho = tmp_path / "banco.db"
    _montar_banco_com_fork_duplicado(caminho)
    conexao = sqlite3.connect(str(caminho), isolation_level=None)
    conexao.execute(DDL_TABELA_INSTANTANEOS)
    conexao.execute("INSERT INTO instantaneos VALUES ('experimento', 3, 'fork-a-3', 'x', '{}');")
    acesso = AcessoSequenciasSQLite(caminho)

    ReparadorSequencias(acesso).reparar(AnalisadorSequencias(acesso).diagnosticar("experimento"))

    assert conexao.execute("SELECT COUNT(*) FROM instantaneos;").fetchone() == (0,)
    conexao.close()
