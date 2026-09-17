"""Acervo de notas como projeção do grafo: uma nota em Markdown por aprendizado promovido.

Mesmo princípio de `docs-gerar`: o grafo é a fonte, o acervo é leitura,
regenerável do zero, e `--conferir` acusa qualquer deriva. Cada nota diz a
afirmação, de onde ela veio (derivado das arestas `deriva_de`) e como aplicá-la;
os links entre notas saem de `substitui` e `contradiz`.
"""

from pathlib import Path

from graphow.notas.extracao import extrair_notas
from graphow.notas.modelo import NotaDeAprendizado, OrigemDaNota
from graphow.notas.publicacao import (
    DocumentoDeNota,
    EscritorDeAcervo,
    EscritorDeAcervoEmDisco,
    EscritorDeAcervoEmMemoria,
    GeradorDeAcervo,
    ResultadoDoAcervo,
)
from graphow.notas.renderizador import renderizar_indice, renderizar_nota
from graphow.projection.graph_view import GrafoView

__all__ = [
    "DocumentoDeNota",
    "EscritorDeAcervo",
    "EscritorDeAcervoEmDisco",
    "EscritorDeAcervoEmMemoria",
    "GeradorDeAcervo",
    "MontadorAcervoDeNotas",
    "NotaDeAprendizado",
    "OrigemDaNota",
    "ResultadoDoAcervo",
    "extrair_notas",
    "renderizar_indice",
    "renderizar_nota",
]


class MontadorAcervoDeNotas:
    """Compõe extração, renderização e publicação para um diretório em disco."""

    def __init__(self, view: GrafoView, raiz: Path) -> None:
        self._view: GrafoView = view
        self._gerador: GeradorDeAcervo = GeradorDeAcervo(EscritorDeAcervoEmDisco(raiz))

    def montar_documentos(self) -> tuple[DocumentoDeNota, ...]:
        """Consulta pura: o que o grafo produziria agora, sem gravar."""
        return self._gerador.montar_documentos(extrair_notas(self._view))

    def publicar(self) -> ResultadoDoAcervo:
        """Comando: grava o acervo inteiro e remove o que sobrou."""
        return self._gerador.publicar(extrair_notas(self._view))

    def conferir(self) -> tuple[str, ...]:
        """Consulta pura: os arquivos que divergem do que o grafo produziria."""
        return self._gerador.conferir(extrair_notas(self._view))
