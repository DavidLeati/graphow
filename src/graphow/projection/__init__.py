"""Módulo de projeção determinística em memória e consultas imutáveis (CQRS)."""

from graphow.projection.graph_view import GrafoView
from graphow.projection.reducer import GrafoReducer

__all__ = ["GrafoReducer", "GrafoView"]
