"""Testes unitários para MaterializadorContexto."""

import pytest

from graphow.context.materializer import (
    MaterializadorContexto,
    RequisicaoVista,
    VistaMaterializada,
)
from graphow.core.exceptions import ErroEntidadeNaoEncontrada, ErroOrcamentoExcedido
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _criar_view_teste() -> GrafoView:
    """Monta ambiente para teste de materialização."""
    nos = {
        "t1": NoGrafo("t1", TipoNo.TASK, "Construir Kernel", {"status": "em_andamento"}),
        "c1": NoGrafo("c1", TipoNo.CONSTRAINT, "RFC 6902 obrigatorio", {"regra": "rfc6902"}),
        "d1": NoGrafo("d1", TipoNo.DECISION, "Usar ActiveGraph e PatchBoard"),
        "t2": NoGrafo("t2", TipoNo.TASK, "Construir Materializador"),
    }
    arestas = {
        "e1": ArestaGrafo("e1", "c1", "t1", TipoAresta.ESCOPA),
        "e2": ArestaGrafo("e2", "t1", "t2", TipoAresta.DEPENDE_DE),
    }
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def test_materializador_nominal() -> None:
    """Testa materialização de vista dentro de orçamento confortável."""
    view = _criar_view_teste()
    materializador = MaterializadorContexto()
    req = RequisicaoVista(id_alvo="t1", papel=PapelAutor.EXECUTOR, orcamento_tokens=1000)
    vista: VistaMaterializada = materializador.materializar(req, view)

    assert vista.id_alvo == "t1"
    assert vista.papel == PapelAutor.EXECUTOR
    assert vista.tokens_estimados <= 1000
    assert "RFC 6902 obrigatorio" in vista.conteudo_formatado
    assert "t1" in vista.nos_incluidos


def test_materializador_expansao_no_edge_case() -> None:
    """Caso de borda: expandir nó retorna arestas de entrada e saída detalhadas."""
    view = _criar_view_teste()
    materializador = MaterializadorContexto()
    detalhe = materializador.expandir_no("t1", view)

    assert detalhe["id"] == "t1"
    assert len(detalhe["arestas_entrada"]) == 1
    assert len(detalhe["arestas_saida"]) == 1


def test_materializador_no_inexistente_edge_case() -> None:
    """Caso de borda: requisição para nó inexistente lança ErroEntidadeNaoEncontrada."""
    view = _criar_view_teste()
    materializador = MaterializadorContexto()
    with pytest.raises(ErroEntidadeNaoEncontrada):
        materializador.materializar(RequisicaoVista("inexistente", PapelAutor.EXECUTOR, 500), view)


def test_materializador_orcamento_estrito_comprime_ou_lanca_edge_case() -> None:
    """Caso de borda: orçamento extremamente restrito aciona compressão ou erro de limite."""
    view = _criar_view_teste()
    materializador = MaterializadorContexto()
    # Orçamento razoável mas apertado
    vista_apertada = materializador.materializar(RequisicaoVista("t1", PapelAutor.EXECUTOR, 150), view)
    assert vista_apertada.tokens_estimados <= 150

    # Orçamento impossível (1 token)
    with pytest.raises(ErroOrcamentoExcedido):
        materializador.materializar(RequisicaoVista("t1", PapelAutor.EXECUTOR, 1), view)
