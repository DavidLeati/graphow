"""O executável vem de `GRAPHOW_CLAUDE` ou do PATH, e o pedido vira o comando e o ambiente certos."""

import os
from pathlib import Path

import pytest

from graphow.sessoes.executavel import ExecutavelAusente, descobrir_executavel
from graphow.sessoes.pedido import PedidoDeSessao, limpar_ambiente, montar_comando


def _pedido(tmp_path: Path, **campos: object) -> PedidoDeSessao:
    """Um pedido com prompt, pasta e stream no diretório do teste."""
    return PedidoDeSessao(prompt="faca", pasta=tmp_path, arquivo_stream=tmp_path / "s.jsonl", **campos)


def test_graphow_claude_vale_antes_do_path_nominal(tmp_path: Path) -> None:
    """Com a variável apontando para um arquivo, o PATH nem é consultado."""
    indicado = tmp_path / "meu-claude.exe"
    indicado.write_text("", encoding="utf-8")

    assert descobrir_executavel({"GRAPHOW_CLAUDE": str(indicado), "PATH": ""}) == indicado


def test_sem_variavel_vale_o_claude_do_path_nominal(tmp_path: Path) -> None:
    """Sem `GRAPHOW_CLAUDE`, o `claude` da primeira pasta do PATH que o tiver."""
    nome = "claude.exe" if os.name == "nt" else "claude"
    executavel = tmp_path / "bin" / nome
    executavel.parent.mkdir()
    executavel.write_text("", encoding="utf-8")
    executavel.chmod(0o755)

    achado = descobrir_executavel({"PATH": str(executavel.parent)})

    assert achado.parent == executavel.parent
    assert achado.name.lower() == nome


def test_variavel_que_nao_aponta_para_arquivo_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: uma pasta, ou um caminho que não existe, não é executável; a recusa diz qual."""
    with pytest.raises(ExecutavelAusente) as recusa:
        descobrir_executavel({"GRAPHOW_CLAUDE": str(tmp_path)})

    assert recusa.value.contexto["GRAPHOW_CLAUDE"] == str(tmp_path)


def test_sem_variavel_e_sem_path_recusa_dizendo_o_que_definir_edge_case() -> None:
    """Caso de borda: sem os dois, a recusa ensina a definir `GRAPHOW_CLAUDE`."""
    with pytest.raises(ExecutavelAusente) as recusa:
        descobrir_executavel({"PATH": ""})

    assert "GRAPHOW_CLAUDE" in recusa.value.contexto["dica"]


def test_comando_completo_tem_cada_opcao_no_lugar_nominal(tmp_path: Path) -> None:
    """Modelo, permissão, ferramentas, retomada, saída em stream-json e os extras no fim."""
    pedido = _pedido(
        tmp_path,
        modelo="opus",
        modo_de_permissao="bypassPermissions",
        ferramentas_permitidas=("Read", "Bash(git log:*)"),
        retomar="sessao-1",
        argumentos_extras=("--max-turns", "5"),
    )

    assert montar_comando(("claude.exe",), pedido) == (
        "claude.exe", "-p",
        "--model", "opus",
        "--permission-mode", "bypassPermissions",
        "--allowedTools", "Read,Bash(git log:*)",
        "--resume", "sessao-1",
        "--output-format", "stream-json", "--verbose",
        "--max-turns", "5",
    )


def test_comando_minimo_so_tem_o_modo_e_a_saida_edge_case(tmp_path: Path) -> None:
    """Caso de borda: opção vazia não vira argumento vazio, e o prompt nunca vai na linha de comando."""
    comando = montar_comando(("py", "falso.py"), _pedido(tmp_path))

    assert comando == ("py", "falso.py", "-p", "--output-format", "stream-json", "--verbose")
    assert "faca" not in comando


def test_ambiente_perde_a_sessao_mae_e_ganha_o_banco_nominal(tmp_path: Path) -> None:
    """`CLAUDE*`, `AI_AGENT` e `BAGGAGE` saem, sem distinguir caixa; o banco pedido entra."""
    ambiente = {
        "PATH": "/bin",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_ENTRYPOINT": "desktop",
        "claude_config_dir": "x",
        "AI_AGENT": "claude",
        "BAGGAGE": "sessao=1",
        "ANTHROPIC_MODEL": "opus",
        "GRAPHOW_DB": "C:/banco-real.db",
    }

    limpo = limpar_ambiente(ambiente, _pedido(tmp_path, banco_graphow=tmp_path / "descartavel.db"))

    assert limpo == {"PATH": "/bin", "ANTHROPIC_MODEL": "opus", "GRAPHOW_DB": str(tmp_path / "descartavel.db")}
    assert "CLAUDECODE" in ambiente


def test_sem_banco_pedido_o_ambiente_fica_com_o_dele_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o pedido sem banco não inventa um nem apaga o que veio."""
    limpo = limpar_ambiente({"GRAPHOW_DB": "C:/outro.db"}, _pedido(tmp_path))

    assert limpo == {"GRAPHOW_DB": "C:/outro.db"}
