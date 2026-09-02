"""Testes unitários para os adaptadores de escrita em console."""

import io

from graphow.api.console import EscritorConsoleEmMemoria, EscritorConsolePadrao


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
