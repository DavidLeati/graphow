"""Testes unitários para o StaticAssetsProvider e segurança de path traversal."""

from graphow.web.static_assets_provider import StaticAssetsProvider


def test_obter_asset_fluxo_nominal() -> None:
    """Valida leitura de arquivo HTML existente com status 200 e tipo MIME adequado."""
    provider = StaticAssetsProvider()
    recurso = provider.obter_recurso("index.html")
    assert recurso.status_code == 200
    assert "text/html" in recurso.tipo_conteudo
    assert b"Graphow" in recurso.conteudo


def test_obter_asset_rota_raiz_default_index() -> None:
    """Valida que rota vazia '/' carrega o index.html."""
    provider = StaticAssetsProvider()
    recurso = provider.obter_recurso("/")
    assert recurso.status_code == 200
    assert "text/html" in recurso.tipo_conteudo


def test_asset_inexistente_retorna_404_edge_case() -> None:
    """Valida retorno de 404 para arquivos inexistentes."""
    provider = StaticAssetsProvider()
    recurso = provider.obter_recurso("arquivo_fantasma.js")
    assert recurso.status_code == 404
    assert b"404" in recurso.conteudo


def test_prevencao_path_traversal_retorna_403_edge_case() -> None:
    """Valida bloqueio e retorno 403 para tentativas de Directory Traversal."""
    provider = StaticAssetsProvider()
    recurso = provider.obter_recurso("../../pyproject.toml")
    assert recurso.status_code == 403
    assert b"403" in recurso.conteudo
