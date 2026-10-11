"""A telemetria das sessões do orquestrador: fora do grafo, no mesmo banco, com o custo acumulado contado uma vez."""

from pathlib import Path
import sqlite3

from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria, SessaoRegistrada, totalizar

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
