"""Adaptador que liga o motor reativo ao gancho pós-commit do kernel."""

from collections.abc import Sequence
import threading

from graphow.core.events import EventoLog
from graphow.kernel.observadores import ObservadorCommit
from graphow.reactive.engine import MotorReativo


class ObservadorReativo(ObservadorCommit):
    """Encaminha os eventos commitados ao motor reativo, sem recursão dupla.

    O motor já controla a própria cascata: quando ele submete um patch, o kernel
    notifica de novo. A guarda de reentrância mantém a contagem de profundidade
    sob responsabilidade exclusiva do motor.
    """

    def __init__(self, motor: MotorReativo) -> None:
        self._motor: MotorReativo = motor
        self._em_processamento: threading.local = threading.local()

    @property
    def nome(self) -> str:
        """Nome identificador do observador."""
        return "MotorReativo"

    def notificar(self, eventos: Sequence[EventoLog]) -> None:
        """Processa cada evento do lote, ignorando chamadas reentrantes."""
        if getattr(self._em_processamento, "ativo", False):
            return
        self._em_processamento.ativo = True
        try:
            self._processar_lote(eventos)
        finally:
            self._em_processamento.ativo = False

    def _processar_lote(self, eventos: Sequence[EventoLog]) -> None:
        """Aciona o motor para cada evento recém-persistido do lote."""
        for evento in eventos:
            self._motor.processar_evento(evento)
