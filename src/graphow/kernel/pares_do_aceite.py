"""Pares de tipos das arestas do aceite no centro (ontologia 1.7.0), apartados para o SchemaGate caber no limite do arquivo.

O Critério nasce produzido pela Sessao e escopa o Goal, como a Constraint
`criterio_aceite` que ele substitui. O Achado nasce produzido pela Sessao,
deriva da verificação que o achou e fere o critério ou a decisão que ele toca.
A fatia de correção deriva do achado que corrige, e o commit dos testes de
aceite deriva de cada critério que eles provam.
"""

from collections.abc import Mapping, Set

from graphow.core.types import TipoAresta, TipoNo

PARES_DO_ACEITE: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]] = {
    TipoAresta.PRODUZ: frozenset({(TipoNo.SESSAO, TipoNo.CRITERIO), (TipoNo.SESSAO, TipoNo.ACHADO)}),
    TipoAresta.ESCOPA: frozenset({(TipoNo.CRITERIO, TipoNo.GOAL)}),
    TipoAresta.FERE: frozenset({(TipoNo.ACHADO, TipoNo.CRITERIO), (TipoNo.ACHADO, TipoNo.DECISION)}),
    TipoAresta.DERIVA_DE: frozenset({
        (TipoNo.ACHADO, TipoNo.EVIDENCE),
        (TipoNo.TASK, TipoNo.ACHADO),
        (TipoNo.ARTIFACT, TipoNo.CRITERIO),
    }),
}


def juntar_pares(
    base: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]],
    extras: Mapping[TipoAresta, Set[tuple[TipoNo, TipoNo]]],
) -> dict[TipoAresta, frozenset[tuple[TipoNo, TipoNo]]]:
    """A tabela de pares com os extras somados aos pares de cada tipo de aresta."""
    tipos = (*base, *(tipo for tipo in extras if tipo not in base))
    return {tipo: frozenset(base.get(tipo, frozenset())) | frozenset(extras.get(tipo, frozenset())) for tipo in tipos}
