"""Módulo de API, Transporte SSE / AG-UI e CLI do Graphow.

Este pacote não reexporta a CLI: importá-la aqui faz `python -m graphow.api.cli`
carregar o módulo duas vezes e emitir RuntimeWarning do runpy.
"""

from graphow.api.console import EscritorConsole, EscritorConsolePadrao
from graphow.api.sse_transport import SSETransport

__all__ = ["EscritorConsole", "EscritorConsolePadrao", "SSETransport"]
