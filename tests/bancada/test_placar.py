"""`graphow bancada placar`: as execuções contra a linha de base, com a variação de cada número."""

import argparse
import json
from pathlib import Path

import pytest

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.placar import formatar_placar, ler_execucoes, ler_linha_de_base
from graphow.bancada.projetos import Bancada, ErroDaBancada
from graphow.sessoes.sessao_claude import ExecutorDeSessao

from tests.bancada.test_auditar import STREAM_DO_AUDITOR
from tests.sessoes.apoio import ambiente_de_teste, comando_do_falso


def _execucao(saida: Path, nome: str, metricas: dict[str, object], placar: dict[str, object] | None = None) -> Path:
    """Uma execução gravada à mão: `execucao.json` e, se houver placar, `auditoria.json`."""
    arquitetura, projeto = nome.split("-", 1)[0], nome.split("-", 1)[1].rsplit("-", 2)[0]
    pasta = saida / nome
    pasta.mkdir(parents=True)
    registro = {"arquitetura": arquitetura, "projeto": projeto, "erro": "", "metricas": metricas}
    (pasta / "execucao.json").write_text(json.dumps(registro), encoding="utf-8")
    if placar is not None:
        (pasta / "auditoria.json").write_text(json.dumps({"erro": "", "placar": placar}), encoding="utf-8")
    return pasta


def _placar(saida: Path) -> list[str]:
    """As linhas que `graphow bancada placar --saida` imprime."""
    console = EscritorConsoleEmMemoria()
    argumentos = construir_parser().parse_args(["bancada", "placar", "--saida", str(saida)])
    assert executar_bancada(argumentos, console) == 0
    return console.linhas


def test_execucao_auditada_sai_com_os_numeros_e_a_variacao_contra_cada_base_nominal(tmp_path: Path) -> None:
    """Custo, tokens e minutos do execucao.json, placar do auditoria.json; variação contra graphow e enxuta."""
    placar = {"criterios": {"atende": 13, "parcial": 1, "nao_atende": 0}, "sondas_ok": 7, "sondas_defeito": 1, "bloqueantes": 1}
    metricas = {"custo_usd": 5.11, "tokens": 6_300_000, "minutos": 21.0, "commits": 11}
    _execucao(tmp_path, "enxuta-estoque-loja-20261011-153000", metricas, placar)

    linhas = _placar(tmp_path)

    assert "| enxuta-estoque-loja-20261011-153000 | estoque-loja | 5,11 | 6,3 M | 21,0 min | 11 | 13/1/0 | 7/8 | 1 |" in linhas
    assert "| base graphow-0.4.4 | estoque-loja | 7,30 | 11,4 M | 24,9 min | 7 | 9/3/0 | 0/8 | 3 |" in linhas
    assert "| enxuta-estoque-loja-20261011-153000 | graphow-0.4.4 | -30% | -45% | -16% | +57% | +44% | +7 (base 0) | -67% |" in linhas
    assert "| enxuta-estoque-loja-20261011-153000 | enxuta | +2% | +2% | +5% | +0% | -7% | +17% | +1 (base 0) |" in linhas
    assert not [linha for linha in linhas if "agenda-salas" in linha]


def test_agenda_do_graphow_compara_sem_o_acabamento_e_sem_auditoria_fica_em_aberto_edge_case(tmp_path: Path) -> None:
    """Caso de borda: na agenda vale o comparável (US$ 7,57); a execução não auditada mostra '-' e a observação."""
    _execucao(tmp_path, "enxuta-agenda-salas-20261011-153000", {"custo_usd": 4.5, "tokens": 6_000_000, "minutos": 22.0, "commits": 9})

    linhas = _placar(tmp_path)

    assert "| base graphow-0.4.4 | agenda-salas | 7,57 | 10,5 M | 20,1 min | 0 | 17/2/0 | 2/8 | 2 |" in linhas
    assert any(linha.startswith("| enxuta-agenda-salas-20261011-153000 | agenda-salas | 4,50 | 6,0 M | 22,0 min | 9 | - | - | - |") for linha in linhas)
    assert any("sem auditoria" in linha for linha in linhas)
    assert any("sem o Goal de acabamento" in linha for linha in linhas)


def test_saida_que_e_uma_execucao_so_tambem_serve_edge_case(tmp_path: Path) -> None:
    """Caso de borda: `--saida` apontando para a pasta de uma execução."""
    pasta = _execucao(tmp_path, "enxuta-api-tarefas-20261011-153000", {"custo_usd": 6.0, "tokens": 9_000_000, "minutos": 25.0, "commits": 10})

    execucoes = ler_execucoes(pasta)

    assert [(execucao.arquitetura, execucao.projeto) for execucao in execucoes] == [("enxuta", "api-tarefas")]


def test_saida_sem_execucao_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: pasta vazia não vira tabela vazia."""
    with pytest.raises(ErroDaBancada):
        ler_execucoes(tmp_path)


def test_linha_de_base_tem_as_seis_referencias_nominal() -> None:
    """Duas arquiteturas, três projetos; o comparável só na agenda do graphow."""
    base = ler_linha_de_base(Bancada().linha_de_base)

    assert len(base) == 6
    assert base[("graphow-0.4.4", "agenda-salas")].numeros.custo_usd == 7.57
    assert base[("enxuta", "agenda-salas")].numeros.custo_usd == 4.78
    assert formatar_placar((), base)[:2] == (
        "| Execucao | Projeto | US$ | Tokens | Min | Commits | Criterios | Sondas ok | Bloqueantes |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |",
    )


def _argumentos(*partes: str) -> argparse.Namespace:
    """`graphow bancada ...` analisado, com transcrições numa pasta que não existe."""
    return construir_parser().parse_args(["bancada", *partes, "--transcricoes", "nao-existe"])


def test_rodar_auditar_e_placar_de_ponta_a_ponta_nominal(tmp_path: Path) -> None:
    """As três ações em sequência, com o falso no lugar das duas sessões."""
    rodar = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r1", GRAPHOW_TESTE_COMMIT="chamado-142"))
    assert executar_bancada(
        _argumentos("rodar", "--arquitetura", "enxuta", "--projeto", "estoque-loja", "--saida", str(tmp_path / "saida")),
        EscritorConsoleEmMemoria(),
        sessoes=rodar,
    ) == 0
    execucao = next((tmp_path / "saida").iterdir())
    auditor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r2", GRAPHOW_TESTE_STREAM=str(STREAM_DO_AUDITOR)))
    assert executar_bancada(_argumentos("auditar", "--execucao", str(execucao)), EscritorConsoleEmMemoria(), sessoes=auditor) == 0

    linhas = _placar(tmp_path / "saida")

    assert any(linha.startswith(f"| {execucao.name} | estoque-loja | 5,03 | 6,2 M |") and "| 1 | 14/0/0 | 6/8 | 0 |" in linha for linha in linhas)
    assert f"| {execucao.name} | enxuta | +0% | +1% |" in "\n".join(linhas)
