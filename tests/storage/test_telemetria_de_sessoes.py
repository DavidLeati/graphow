"""A telemetria das sessões do orquestrador: fora do grafo, no mesmo banco, com o custo acumulado contado uma vez."""

from pathlib import Path
import sqlite3

from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.storage.telemetria_de_sessoes import (
    ESTADO_CONCLUIDA,
    ESTADO_EM_ANDAMENTO,
    RepositorioTelemetria,
    SessaoRegistrada,
    totalizar,
)

TOKENS: dict[str, int] = {"entrada": 10, "saida": 5, "cache_leitura": 100, "cache_criacao": 20, "total": 135}


def _registro(**campos: object) -> SessaoRegistrada:
    """Uma invocação de executor com custo e tokens, sobrescrita pelos campos dados."""
    base: dict[str, object] = {
        "id_goal": "goal-a", "papel": "executor", "fatia": "task-a-F1", "session_id": "s1", "modelo": "opus",
        "inicio": "2026-10-11T10:00:00-03:00", "fim": "2026-10-11T10:01:00-03:00", "duracao_s": 60.0,
        "custo_usd": 0.5, "tokens": TOKENS, "turnos": 7, "codigo_saida": 0, "comando": ("claude", "-p"),
    }
    return SessaoRegistrada(**{**base, **campos})  # type: ignore[arg-type]


def test_registro_vai_para_a_tabela_do_mesmo_banco_e_volta_igual_nominal(tmp_path: Path) -> None:
    """No arquivo do banco de eventos, numa tabela própria, sem tocar o log."""
    store, kernel = abrir_kernel_sqlite(tmp_path / "graphow.db")
    with store:
        repositorio = RepositorioTelemetria(store.conexao)
        repositorio.registrar(_registro())
        lidos = repositorio.listar("goal-a")
        eventos = store.ler_eventos("main")
        nos = kernel.obter_view().total_nos

    assert lidos == (_registro(),)
    assert (eventos, nos) == ([], 0)
    tabelas = sqlite3.connect(tmp_path / "graphow.db").execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert ("telemetria_de_sessoes",) in tabelas


def test_sessao_retomada_conta_so_a_ultima_invocacao_nominal() -> None:
    """O `--resume` traz o acumulado: duas invocações da mesma sessão custam o da segunda."""
    repositorio = RepositorioTelemetria(sqlite3.connect(":memory:"))
    repositorio.registrar(_registro(custo_usd=0.5))
    repositorio.registrar(_registro(custo_usd=0.8, retomada=True, tokens={**TOKENS, "total": 200}))
    repositorio.registrar(_registro(session_id="s2", papel="verificador", fatia="", custo_usd=1.0))

    totais = repositorio.totais("goal-a")

    assert (totais.invocacoes, totais.sessoes) == (3, 2)
    assert round(totais.custo_usd, 2) == 1.8
    assert totais.tokens == 335
    assert totais.duracao_s == 180.0
    assert totais.custos_desconhecidos == 0


def test_invocacao_sem_resultado_fica_desconhecida_e_nao_zero_edge_case() -> None:
    """Caso de borda: a sessão que morreu sem `result` não vale zero, entra como desconhecida."""
    registros = (
        _registro(),
        _registro(session_id="", custo_usd=None, tokens=None, turnos=None, is_error=True, erro="tempo esgotado"),
    )

    totais = totalizar(registros)

    assert totais.custos_desconhecidos == 1
    assert totais.custo_usd == 0.5
    assert totais.com_erro == 1


def test_goals_nao_se_misturam_edge_case() -> None:
    """Caso de borda: o total de um Goal não leva as sessões de outro."""
    repositorio = RepositorioTelemetria(sqlite3.connect(":memory:"))
    repositorio.registrar(_registro())
    repositorio.registrar(_registro(id_goal="goal-b", session_id="s9", custo_usd=3.0))

    assert repositorio.totais("goal-a").custo_usd == 0.5
    assert [registro.id_goal for registro in repositorio.listar("goal-b")] == ["goal-b"]


def test_retomada_que_morreu_sem_custo_nao_zera_o_que_a_sessao_ja_tinha_dito_edge_case() -> None:
    """Caso de borda: a primeira invocação disse 0.5, o `--resume` morreu sem `result`; valem 0.5 e um desconhecido."""
    registros = (
        _registro(custo_usd=0.5),
        _registro(custo_usd=None, tokens=None, turnos=None, retomada=True, is_error=True, erro="sem evento result"),
    )

    totais = totalizar(registros)

    assert (totais.sessoes, totais.custo_usd, totais.custos_desconhecidos, totais.tokens) == (1, 0.5, 1, 135)


def test_linha_nasce_em_andamento_e_e_atualizada_no_fim_nominal() -> None:
    """A linha existe antes de a sessão terminar; o fim reescreve a mesma linha."""
    repositorio = RepositorioTelemetria(sqlite3.connect(":memory:"))
    aberta = _registro(session_id="", fim="", duracao_s=0.0, custo_usd=None, tokens=None, estado=ESTADO_EM_ANDAMENTO)

    id_linha = repositorio.registrar(aberta)
    durante = repositorio.totais("goal-a")
    repositorio.atualizar(id_linha, _registro())

    assert (durante.em_andamento, durante.custos_desconhecidos) == (1, 1)
    (linha,) = repositorio.listar("goal-a")
    assert (linha.id_linha, linha.estado, linha.custo_usd) == (id_linha, ESTADO_CONCLUIDA, 0.5)


def test_banco_de_antes_da_coluna_estado_ganha_a_coluna_ao_abrir_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a tabela criada pela versão anterior não tem `estado`; abrir a acrescenta, e o antigo vale concluído."""
    caminho = tmp_path / "antigo.db"
    conexao = sqlite3.connect(caminho)
    conexao.execute(
        "CREATE TABLE telemetria_de_sessoes (id INTEGER PRIMARY KEY AUTOINCREMENT, id_goal TEXT NOT NULL, "
        "papel TEXT NOT NULL, fatia TEXT NOT NULL DEFAULT '', tentativa INTEGER NOT NULL DEFAULT 1, "
        "session_id TEXT NOT NULL DEFAULT '', retomada INTEGER NOT NULL DEFAULT 0, modelo TEXT NOT NULL DEFAULT '', "
        "inicio TEXT NOT NULL DEFAULT '', fim TEXT NOT NULL DEFAULT '', duracao_s REAL NOT NULL DEFAULT 0, "
        "custo_usd REAL, tokens_json TEXT, turnos INTEGER, codigo_saida INTEGER, tempo_esgotado INTEGER NOT NULL DEFAULT 0, "
        "is_error INTEGER NOT NULL DEFAULT 0, erro TEXT NOT NULL DEFAULT '', arquivo_stream TEXT NOT NULL DEFAULT '', "
        "comando_json TEXT NOT NULL DEFAULT '[]');"
    )
    conexao.execute("INSERT INTO telemetria_de_sessoes (id_goal, papel, custo_usd) VALUES ('goal-a', 'executor', 1.25);")
    conexao.commit()
    conexao.close()

    repositorio = RepositorioTelemetria(sqlite3.connect(caminho))

    (antigo,) = repositorio.listar("goal-a")
    assert (antigo.estado, antigo.custo_usd) == (ESTADO_CONCLUIDA, 1.25)
