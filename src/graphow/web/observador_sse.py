"""Adaptador que publica no canal SSE os eventos aceitos pelo kernel."""

from collections.abc import Sequence

from graphow.core.events import EventoLog
from graphow.kernel.observadores import ObservadorCommit
from graphow.web.sse_controller import SSEWebController


class ObservadorSSE(ObservadorCommit):
    """Entrega ao canal de tempo real cada evento que os portões aprovaram."""

    def __init__(self, controlador: SSEWebController) -> None:
        self._controlador: SSEWebController = controlador

    @property
    def nome(self) -> str:
        """Nome identificador do observador."""
        return "CanalSSE"

    def notificar(self, eventos: Sequence[EventoLog]) -> None:
        """Publica o lote para todos os assinantes conectados."""
        for evento in eventos:
            self._controlador.despachar_evento(evento)
