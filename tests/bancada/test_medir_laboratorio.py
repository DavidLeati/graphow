"""`graphow bancada medir-laboratorio`: a linha de base medida de novo dos logs, com cada número conferido."""

import os
from pathlib import Path

import pytest

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.projetos import Bancada, ErroDaBancada
from graphow.bancada.semente import GitDaBancada, criar_repositorio

from tests.bancada.apoio_laboratorio import desdobrar_recorte


def _medir(laboratorio: Path, projetos: Path) -> tuple[int, list[str]]:
    """O código de saída e as linhas de `graphow bancada medir-laboratorio`."""
    console = EscritorConsoleEmMemoria()
    argumentos = construir_parser().parse_args(
        ["bancada", "medir-laboratorio", "--laboratorio", str(laboratorio), "--transcricoes", str(projetos)]
    )
    return executar_bancada(argumentos, console), console.linhas


def test_medir_laboratorio_reproduz_a_linha_de_base_dos_logs_nominal(tmp_path: Path) -> None:
    """Dos logs e das transcrições recortados, os seis custos, tokens e minutos e a soma que o relatório usou."""
    laboratorio, projetos = desdobrar_recorte(tmp_path)

    codigo, linhas = _medir(laboratorio, projetos)

    assert codigo == 0, linhas
    assert "| graphow-0.4.4 agenda-salas | 10,65 | 15.325.496 | 28,8 min | - | 18,58 | 1 | sim |" in linhas
    assert "| graphow-0.4.4 agenda-salas sem acabamento | 7,57 | 10.494.822 | 20,1 min | - | 7,93 | 1 | sim |" in linhas
    assert "| graphow-0.4.4 estoque-loja | 7,30 | 11.400.193 | 24,9 min | - | 7,73 | 1 | sim |" in linhas
    assert "| graphow-0.4.4 api-tarefas | 8,77 | 12.215.261 | 21,8 min | - | 9,09 | 1 | sim |" in linhas
    assert "| enxuta agenda-salas | 4,78 | 6.715.363 | 24,0 min | - | 4,78 | 0 | sim |" in linhas
    assert "| enxuta estoque-loja | 5,03 | 6.160.643 | 20,0 min | - | 5,03 | 0 | sim |" in linhas
    assert "| enxuta api-tarefas | 6,24 | 9.478.262 | 27,2 min | - | 6,24 | 0 | sim |" in linhas
    assert linhas[-1] == "7 conferencias, 0 divergencias"
    assert sum("commits sem conferir: repositorio ausente" in linha for linha in linhas) == 6


def test_commits_do_repositorio_que_nao_batem_saem_como_divergencia_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o repositório da enxuta no estoque tem 2 commits no ramo, e a linha de base grava 11."""
    laboratorio, projetos = desdobrar_recorte(tmp_path)
    repositorio = laboratorio / "b" / "estoque-loja"
    criar_repositorio(Bancada().projeto("estoque-loja"), repositorio)
    identidade = {nome: "Teste" for nome in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME")}
    git = GitDaBancada(repositorio, {**os.environ, **identidade, "GIT_AUTHOR_EMAIL": "t@t.invalid", "GIT_COMMITTER_EMAIL": "t@t.invalid"})
    git.rodar("checkout", "-q", "-b", "chamado-142")
    for passo in ("um", "dois"):
        git.rodar("commit", "-q", "--allow-empty", "-m", passo)

    codigo, linhas = _medir(laboratorio, projetos)

    assert codigo == 1
    assert "| enxuta estoque-loja | 5,03 | 6.160.643 | 20,0 min | 2 | 5,03 | 0 | NAO |" in linhas
    assert "- enxuta estoque-loja: commits medido 2 contra 11 na linha de base" in linhas
    assert linhas[-1] == "7 conferencias, 1 divergencias"


def test_pasta_que_nao_e_o_laboratorio_recusa_com_o_caminho_do_log_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem os logs não há o que conferir, e a recusa diz qual log faltou."""
    with pytest.raises(ErroDaBancada) as recusa:
        _medir(tmp_path / "nao-e-o-laboratorio", tmp_path)

    assert recusa.value.contexto["log"].endswith("agenda-salas.jsonl")
