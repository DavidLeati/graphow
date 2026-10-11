"""`graphow orquestrar` pela linha de comando: o executável de `GRAPHOW_CLAUDE`, o banco pedido e o status."""

import os
from pathlib import Path
import stat
import sys

import pytest

from graphow.api.cli_execucao import ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos

from tests.orquestrador.apoio_laco import CLAUDE_ROTEIRIZADO, montar_bancada, roteiro_completo


def _executavel(pasta: Path) -> Path:
    """O falso roteirizado como executável, para `GRAPHOW_CLAUDE` apontar para ele."""
    pasta.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        caminho = pasta / "claude.cmd"
        caminho.write_text(f'@"{sys.executable}" "{CLAUDE_ROTEIRIZADO}" %*\r\n', encoding="utf-8")
        return caminho
    caminho = pasta / "claude"
    caminho.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{CLAUDE_ROTEIRIZADO}" "$@"\n', encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)
    return caminho


def _rodar(argumentos: list[str], dados: Path) -> tuple[int, list[str]]:
    """`graphow ...` pelo executor da linha de comando, com o diretório de dados no temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(dados)}, dados)
    codigo = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente)).executar(construir_parser().parse_args(argumentos))
    return codigo, console.linhas


def test_orquestrar_da_spec_fecha_o_goal_e_o_status_mostra_o_custo_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Da spec ao Goal fechado pela CLI, com o estado do Goal ao lado do banco e o status relido depois."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    banco = tmp_path / "dados" / "graphow.db"

    codigo, linhas = _rodar(
        ["--db", str(banco), "orquestrar", "--spec", str(bancada.spec), "--repo", str(bancada.repositorio), "--modo", "autonomo"],
        tmp_path / "dados",
    )
    codigo_do_status, status = _rodar(["--db", str(banco), "orquestrar", "--goal", "goal-soma", "--status"], tmp_path / "dados")

    assert codigo == 0, linhas
    assert "Parada: fechado" in linhas
    assert (tmp_path / "dados" / "orquestrar" / "goal-soma" / "sessoes").is_dir()
    assert codigo_do_status == 0
    assert status[1].startswith("Goal goal-soma: Soma de dois numeros [fechado]")
    assert any(linha.startswith("Sessoes: 6 invocacao(oes)") and "US$ 2.30" in linha for linha in status)


def test_status_de_goal_que_nao_existe_sai_com_1_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o status de um Goal desconhecido diz que não achou e sai com 1."""
    codigo, linhas = _rodar(["--db", str(tmp_path / "g.db"), "orquestrar", "--goal", "goal-x", "--status"], tmp_path)

    assert codigo == 1
    assert "ERRO: Goal 'goal-x' nao encontrado" in linhas


def test_spec_ou_goal_e_obrigatorio_edge_case() -> None:
    """Caso de borda: --spec e --goal são exclusivos, e um deles é obrigatório."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["orquestrar", "--status"])
