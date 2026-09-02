"""Geração do catálogo de documentação a partir do próprio código-fonte.

A documentação mantida à mão diverge do código em silêncio: a auditoria de
2026-08-26 encontrou três contagens diferentes de ferramentas MCP e duas
promessas que o código contradizia. Aqui o catálogo é derivado do AST, e um
teste em `tests/qualidade/` falha se o que está em `docs/` sair de sincronia.
"""

from pathlib import Path

from graphow.documentacao.extrator import ExtratorCatalogo
from graphow.documentacao.leitura_fonte import LeitorCodigoFonte, LeitorCodigoFonteEmDisco
from graphow.documentacao.modelo import CatalogoRepositorio
from graphow.documentacao.publicacao import (
    DocumentoGerado,
    EscritorDocumentacao,
    EscritorDocumentacaoEmDisco,
    GeradorDocumentacao,
    ResultadoPublicacao,
)
from graphow.documentacao.setores import DEFINICOES_DE_SETOR, MontadorCatalogo

__all__ = [
    "DEFINICOES_DE_SETOR",
    "CatalogoRepositorio",
    "DocumentoGerado",
    "EscritorDocumentacao",
    "EscritorDocumentacaoEmDisco",
    "ExtratorCatalogo",
    "GeradorDocumentacao",
    "LeitorCodigoFonte",
    "LeitorCodigoFonteEmDisco",
    "MontadorCatalogo",
    "MontadorDocumentacaoDoRepositorio",
    "ResultadoPublicacao",
]


class MontadorDocumentacaoDoRepositorio:
    """Compõe leitura, extração e renderização para um repositório em disco."""

    def __init__(self, raiz_codigo: Path, raiz_documentacao: Path) -> None:
        self._montador: MontadorCatalogo = MontadorCatalogo(LeitorCodigoFonteEmDisco(raiz_codigo))
        self._gerador: GeradorDocumentacao = GeradorDocumentacao(
            EscritorDocumentacaoEmDisco(raiz_documentacao)
        )

    def montar_catalogo(self) -> CatalogoRepositorio:
        """Consulta o código e devolve o catálogo, sem escrever nada."""
        return self._montador.montar()

    def montar_documentos(self) -> tuple[DocumentoGerado, ...]:
        """Renderiza os documentos em memória, para comparação de deriva."""
        return self._gerador.montar_documentos(self.montar_catalogo())

    def publicar(self) -> ResultadoPublicacao:
        """Comando: grava o índice e os dossiês em `docs/`."""
        return self._gerador.publicar(self.montar_catalogo())
