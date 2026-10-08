"""Pares de tipos das arestas do escopo governado, apartados para o SchemaGate caber no limite do arquivo."""

from collections.abc import Mapping, Set

from graphow.core.types import TipoAresta, TipoNo

# O veredito de escopo é uma Evidence que deriva da raiz que julga, e a raiz de
# uma cadeia de `motivada_por` é Decision, Evidence, Task ou Question. Evidence ->
# Task já existia em `deriva_de`; os três pares abaixo completam as outras raízes.
PARES_DE_DERIVA_DO_VEREDITO_DE_ESCOPO: Set[tuple[TipoNo, TipoNo]] = frozenset({
    (TipoNo.EVIDENCE, TipoNo.DECISION),
    (TipoNo.EVIDENCE, TipoNo.EVIDENCE),
    (TipoNo.EVIDENCE, TipoNo.QUESTION),
})

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
