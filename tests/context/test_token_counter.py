"""Testes unitários para ContadorTokens."""

from graphow.context.token_counter import ContadorTokens


def test_contador_tokens_fluxo_nominal() -> None:
    """Testa contagem estimada de tokens em texto padrão."""
    texto = "Este é um texto de 35 caracteres..."
    tokens = ContadorTokens.estimar_texto(texto)
    assert tokens > 0
    assert tokens == 9
    assert ContadorTokens.cabe_no_orcamento(texto, 10) is True
    assert ContadorTokens.cabe_no_orcamento(texto, 5) is False


def test_contador_tokens_string_vazia_edge_case() -> None:
    """Caso de borda: texto vazio retorna 0 tokens."""
    assert ContadorTokens.estimar_texto("") == 0
    assert ContadorTokens.estimar_objeto(None) == 0


def test_contador_tokens_objeto_complexo_edge_case() -> None:
    """Caso de borda: contagem em dicionário estruturado profundo."""
    dados = {"a": [1, 2, 3], "b": {"chave": "valor longo com muitas palavras"}}
    tokens = ContadorTokens.estimar_objeto(dados)
    assert tokens > 10
