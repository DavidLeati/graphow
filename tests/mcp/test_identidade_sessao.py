"""Testes unitários para a identidade fixada por sessão MCP e sua política."""

import pytest

from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.types import PapelAutor
from graphow.mcp.identidade_sessao import (
    FERRAMENTAS_EXCLUSIVAS_DO_HUMANO,
    IdentidadeSessaoMCP,
    PoliticaIdentidadeMCP,
    ResultadoAutorizacao,
)


def test_cria_identidade_valida_nominal() -> None:
    """Autor e papel válidos produzem uma identidade congelada."""
    identidade = IdentidadeSessaoMCP.criar("agente-alpha", "executor")
    assert identidade.autor == "agente-alpha"
    assert identidade.papel == PapelAutor.EXECUTOR
    assert identidade.eh_humano is False


def test_normaliza_papel_com_espacos_e_caixa_nominal() -> None:
    """O papel é normalizado antes da conversão para o enum."""
    identidade = IdentidadeSessaoMCP.criar("  david  ", "  HUMANO ")
    assert identidade.autor == "david"
    assert identidade.eh_humano is True


def test_recusa_papel_inexistente_edge_case() -> None:
    """Caso de borda: papel fora da ontologia é recusado com erro de domínio."""
    with pytest.raises(ErroPermissaoPapel) as capturado:
        IdentidadeSessaoMCP.criar("agente", "administrador")
    assert "invalido" in capturado.value.mensagem


def test_recusa_papel_sistema_em_sessao_edge_case() -> None:
    """Caso de borda: 'sistema' é reservado à telemetria e não abre sessão MCP."""
    with pytest.raises(ErroPermissaoPapel):
        IdentidadeSessaoMCP.criar("telemetria", "sistema")


def test_recusa_autor_vazio_edge_case() -> None:
    """Caso de borda: sessão sem autor identificável é recusada."""
    with pytest.raises(ErroPermissaoPapel):
        IdentidadeSessaoMCP.criar("   ", "executor")


def test_politica_autoriza_ferramenta_comum_para_agente_nominal() -> None:
    """Ferramentas fora da lista restrita são liberadas para qualquer papel."""
    politica = PoliticaIdentidadeMCP()
    identidade = IdentidadeSessaoMCP.criar("agente", "planejador")
    assert politica.autorizar("ler_vista", identidade).autorizado is True
    assert politica.autorizar("criar_tarefa", identidade).autorizado is True


def test_politica_barra_ferramentas_restritas_para_agente_edge_case() -> None:
    """Caso de borda: toda ferramenta restrita é negada a uma sessão não humana."""
    politica = PoliticaIdentidadeMCP()
    identidade = IdentidadeSessaoMCP.criar("agente", "executor")
    for nome_ferramenta in FERRAMENTAS_EXCLUSIVAS_DO_HUMANO:
        veredito = politica.autorizar(nome_ferramenta, identidade)
        assert veredito.autorizado is False, nome_ferramenta
        assert "sessao humana" in veredito.motivo


def test_politica_libera_ferramentas_restritas_para_humano_edge_case() -> None:
    """Caso de borda: a mesma ferramenta é liberada sob identidade humana."""
    politica = PoliticaIdentidadeMCP()
    identidade = IdentidadeSessaoMCP.criar("david", "humano")
    for nome_ferramenta in FERRAMENTAS_EXCLUSIVAS_DO_HUMANO:
        assert politica.autorizar(nome_ferramenta, identidade).autorizado is True


def test_resultado_autorizacao_expoe_construtores_nomeados() -> None:
    """Os construtores nomeados descrevem o veredito sem ambiguidade."""
    assert ResultadoAutorizacao.permitido().autorizado is True
    negado = ResultadoAutorizacao.negado("motivo qualquer")
    assert negado.autorizado is False
    assert negado.motivo == "motivo qualquer"
