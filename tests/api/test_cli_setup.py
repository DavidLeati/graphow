"""Testes do subcomando `graphow setup`: instala, confere e diz o que segue manual."""

import json
from pathlib import Path

from graphow.api.cli_execucao import CODIGO_SUCESSO, ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos

EXECUTAVEL: str = "C:/venv/Scripts/graphow.exe"


def _executar(argumentos: list[str], diretorio: Path) -> tuple[int, EscritorConsoleEmMemoria]:
    """Roda o setup com o diretório de dados e o do Claude Code em pastas temporárias."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(diretorio)}, diretorio)
    executor = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente))
    base = ["setup", "--claude-dir", str(diretorio / "claude"), "--executavel", EXECUTAVEL, "--autor", "david"]
    return executor.executar(construir_parser().parse_args(base + argumentos)), console


def test_setup_instala_e_imprime_o_bloco_sem_tocar_o_settings_nominal(tmp_path: Path) -> None:
    """Sem --escrever-settings, o settings.json não nasce; o bloco e o claude mcp add vão para a tela."""
    codigo, console = _executar([], tmp_path)

    assert codigo == CODIGO_SUCESSO
    assert (tmp_path / "claude" / "agents" / "graphow-condutor.md").is_file()
    assert not (tmp_path / "claude" / "settings.json").exists()
    texto = "\n".join(console.linhas)
    assert '"SubagentStop"' in texto
    assert f'claude mcp add --scope user graphow -- "{EXECUTAVEL}" mcp --papel humano --autor david' in texto
    assert "governanca" in texto


def test_setup_com_escrever_settings_mescla_hooks_nominal(tmp_path: Path) -> None:
    """A opção grava os hooks com o caminho do executável no settings.json do diretório dado."""
    codigo, _ = _executar(["--escrever-settings"], tmp_path)

    gravado = json.loads((tmp_path / "claude" / "settings.json").read_text(encoding="utf-8"))
    assert codigo == CODIGO_SUCESSO
    assert gravado["hooks"]["SessionStart"][0]["hooks"][0]["command"] == EXECUTAVEL


def test_conferir_sai_com_1_antes_e_0_depois_da_instalacao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a conferência não grava nada e o código de saída diz se a cópia envelheceu."""
    codigo_antes, console = _executar(["--conferir"], tmp_path)
    assert codigo_antes == 1
    assert any(linha.startswith("Desatualizado:") for linha in console.linhas)
    assert not (tmp_path / "claude").exists()

    _executar([], tmp_path)
    codigo_depois, _ = _executar(["--conferir"], tmp_path)

    assert codigo_depois == CODIGO_SUCESSO
