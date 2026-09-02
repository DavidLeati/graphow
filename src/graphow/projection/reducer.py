"""Redutor determinístico de eventos append-only para estado de grafo em memória."""

from collections.abc import Sequence

from graphow.core.events import EventoLog
from graphow.core.models import GrafoEstado
from graphow.projection.acumulador import AcumuladorProjecao


class GrafoReducer:
    """Funções puras para projetar eventos ordenados em instâncias imutáveis de GrafoEstado."""

    @staticmethod
    def reconstruir(eventos: Sequence[EventoLog]) -> GrafoEstado:
        """Reconstrói o estado integral do grafo a partir de uma sequência de eventos."""
        return GrafoReducer.aplicar_eventos(GrafoEstado(), eventos)

    @staticmethod
    def aplicar_eventos(estado_base: GrafoEstado, eventos: Sequence[EventoLog]) -> GrafoEstado:
        """Dobra a sequência sobre o estado base em uma passada, sem cópias intermediárias.

        O estado recebido não é modificado: o acumulador trabalha sobre cópias e o
        resultado é congelado uma única vez ao final.
        """
        if not eventos:
            return estado_base
        acumulador = AcumuladorProjecao(estado_base)
        acumulador.aplicar_todos(eventos)
        return acumulador.congelar()

    @staticmethod
    def reduzir(estado: GrafoEstado, evento: EventoLog) -> GrafoEstado:
        """Aplica um único evento de forma pura sobre o estado atual."""
        return GrafoReducer.aplicar_eventos(estado, (evento,))
