"""Pares de tipos das arestas do escopo governado, apartados para o SchemaGate caber no limite do arquivo."""

from collections.abc import Mapping, Set

from graphow.core.types import TipoAresta, TipoNo

PARES_DE_ARESTAS_DO_ESCOPO: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]] = {
    # De que decisão, achado, trabalho ou dúvida a Task nasceu; a Decision que
    # nasce de outra decisão ou de um achado liga a cadeia pelo mesmo vínculo.
    TipoAresta.MOTIVADA_POR: frozenset({
        (TipoNo.TASK, TipoNo.DECISION),
        (TipoNo.TASK, TipoNo.EVIDENCE),
        (TipoNo.TASK, TipoNo.TASK),
        (TipoNo.TASK, TipoNo.QUESTION),
        (TipoNo.DECISION, TipoNo.DECISION),
        (TipoNo.DECISION, TipoNo.EVIDENCE),
        (TipoNo.DECISION, TipoNo.TASK),
        (TipoNo.DECISION, TipoNo.QUESTION),
    }),
    # A Task que acompanha a reprovação que o árbitro aceitou.
    TipoAresta.ACOMPANHA: frozenset({(TipoNo.TASK, TipoNo.EVIDENCE)}),
    # A Task que integra a entrega de outra no ramo base.
    TipoAresta.INTEGRA: frozenset({(TipoNo.TASK, TipoNo.TASK)}),
    # A Task que desfaz uma decisão já substituída ou revogada.
    TipoAresta.DESFAZ: frozenset({(TipoNo.TASK, TipoNo.DECISION)}),
}
