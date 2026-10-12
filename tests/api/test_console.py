"""Testes unitários para os adaptadores de escrita em console."""

import io
import os
from pathlib import Path
import subprocess
import sys

from graphow.api.console import EscritorConsoleEmMemoria, EscritorConsolePadrao, saida_em_utf8

RAIZ: Path = Path(__file__).resolve().parents[2]


class FluxoComCodificacaoLimitada(io.StringIO):
    """Fluxo que declara uma codificação incapaz de representar todo o Unicode."""

    @property
    def encoding(self) -> str:
        """Codificação anunciada ao escritor, como faz um console Windows legado."""
        return "cp1252"


def test_escreve_linha_simples_nominal() -> None:
    """Texto ASCII atravessa o escritor sem alteração."""
    fluxo = io.StringIO()
    EscritorConsolePadrao(fluxo).escrever_linha("Servidor iniciado na porta 8000")
    assert fluxo.getvalue() == "Servidor iniciado na porta 8000\n"


def test_nao_falha_com_caractere_fora_da_codificacao_edge_case() -> None:
    """Caso de borda: emoji em console cp1252 é substituído, nunca derruba o comando."""
    fluxo = FluxoComCodificacaoLimitada()
    EscritorConsolePadrao(fluxo).escrever_linha("\U0001f310 Servidor Web iniciado")
    conteudo = fluxo.getvalue()
    assert conteudo.endswith("Servidor Web iniciado\n")
    assert "\U0001f310" not in conteudo


def test_preserva_acentuacao_quando_a_codificacao_suporta_edge_case() -> None:
    """Caso de borda: cp1252 representa acentos do português e eles devem sobreviver."""
    fluxo = FluxoComCodificacaoLimitada()
    EscritorConsolePadrao(fluxo).escrever_linha("Migração concluída com sucesso")
    assert fluxo.getvalue() == "Migração concluída com sucesso\n"


def test_escritor_em_memoria_acumula_linhas_imutaveis_edge_case() -> None:
    """Caso de borda: o escritor de teste expõe uma cópia imutável do que foi emitido."""
    escritor = EscritorConsoleEmMemoria()
    escritor.escrever_linha("primeira")
    escritor.escrever_linha("segunda")
    assert escritor.linhas == ("primeira", "segunda")
    assert isinstance(escritor.linhas, tuple)


class ConsoleDeVerdade(io.TextIOWrapper):
    """Um fluxo que se diz terminal."""

    def isatty(self) -> bool:
        """O console interativo."""
        return True


def test_cano_em_cp1252_passa_a_sair_em_utf8_nominal() -> None:
    """O cano que o Windows abre em cp1252 sai em UTF-8: "operações" chega inteiro a quem lê."""
    bruto = io.BytesIO()
    cano = io.TextIOWrapper(bruto, encoding="cp1252", newline="\n")

    saida_em_utf8([cano])
    EscritorConsolePadrao(cano).escrever_linha("time de operações")

    assert bruto.getvalue().decode("utf-8") == "time de operações\n"


def test_console_de_verdade_fica_como_esta_edge_case() -> None:
    """Caso de borda: o terminal interativo não é reconfigurado; o Windows já escreve nele em Unicode."""
    console = ConsoleDeVerdade(io.BytesIO(), encoding="cp1252")

    saida_em_utf8([console])

    assert console.encoding == "cp1252"


def test_graphow_por_cano_imprime_acento_em_utf8_nominal(tmp_path: Path) -> None:
    """O `graphow` de verdade, com a saída num cano e sem PYTHONUTF8: o acento chega em UTF-8, sem substituição."""
    ambiente = {nome: valor for nome, valor in os.environ.items() if nome not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    ambiente.update({"PYTHONPATH": str(RAIZ / "src"), "GRAPHOW_DB": str(tmp_path / "graphow.db")})

    feito = subprocess.run(
        [sys.executable, "-m", "graphow.api.cli", "orquestrar", "--status", "--goal", "goal-operações"],
        capture_output=True, env=ambiente, cwd=tmp_path, check=False,
    )

    texto = feito.stdout.decode("utf-8")
    assert "goal-operações" in texto and "\ufffd" not in texto, (feito.stdout, feito.stderr)
