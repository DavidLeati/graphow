"""Notificação pós-commit dos eventos aceitos pelos quatro portões.

Sem este gancho, o endpoint SSE e o motor reativo existem, são testados e nunca
recebem nada em produção: o canal fica conectado transportando apenas pings.
Ver auditoria F-05.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
import threading

from graphow.core.events import EventoLog


class ObservadorCommit(ABC):
    """Contrato de quem quer saber dos eventos assim que eles viram história."""

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome identificador do observador, usado em diagnóstico."""
        raise NotImplementedError

    @abstractmethod
    def notificar(self, eventos: Sequence[EventoLog]) -> None:
        """Recebe o lote de eventos recém-persistido, já validado e ordenado."""
        raise NotImplementedError


class DespachanteObservadores:
    """Mantém os observadores registrados e os notifica em ordem de registro."""

    def __init__(self) -> None:
        self._observadores: list[ObservadorCommit] = []
        self._lock: threading.RLock = threading.RLock()

    def registrar(self, observador: ObservadorCommit) -> None:
        """Adiciona um observador ao fim da cadeia de notificação."""
        with self._lock:
            self._observadores.append(observador)

    @property
    def nomes_registrados(self) -> tuple[str, ...]:
        """Nomes dos observadores ativos, em ordem de registro."""
        with self._lock:
            return tuple(observador.nome for observador in self._observadores)

    def notificar(self, eventos: Sequence[EventoLog]) -> None:
        """Entrega o lote a cada observador, isolando a falha de um dos demais."""
        if not eventos:
            return
        with self._lock:
            observadores = tuple(self._observadores)
        for observador in observadores:
            observador.notificar(eventos)
