"""Interface abstrata para comportamentos reativos desacoplados."""

from abc import ABC, abstractmethod

from graphow.core.events import EventoLog
from graphow.kernel.patch_models import PropostaPatch
from graphow.projection.graph_view import GrafoView


class ComportamentoReativo(ABC):
    """Contrato formal: escuta evento, consulta GrafoView e emite no máximo uma PropostaPatch."""

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome identificador único do comportamento."""
        raise NotImplementedError

    @abstractmethod
    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch | None:
        """Processa a mutação e decide se deve propor um patch reativo."""
        raise NotImplementedError
