"""Relógio e política de espera do long-poll MCP, isolados para permitir teste.

Um `time.sleep` escrito dentro da ferramenta tornaria o teste da espera tão
lento quanto o prazo real. O relógio é injetado; a política guarda os limites
que impedem um agente de segurar o transporte stdio indefinidamente.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Any

TEMPO_DE_ESPERA_PADRAO_SEGUNDOS: float = 30.0
INTERVALO_DE_SONDAGEM_SEGUNDOS: float = 0.5
TEMPO_MAXIMO_DE_ESPERA_SEGUNDOS: float = 300.0


class Relogio(ABC):
    """Contrato mínimo de tempo usado pelas ferramentas que esperam."""

    @abstractmethod
    def agora(self) -> float:
        """Instante monotônico corrente, em segundos."""
        raise NotImplementedError

    @abstractmethod
    def aguardar(self, segundos: float) -> None:
        """Suspende a execução pelo intervalo informado."""
        raise NotImplementedError


class RelogioMonotonico(Relogio):
    """Relógio real de produção, imune a ajustes do relógio de parede."""

    def agora(self) -> float:
        """Lê o contador monotônico do sistema."""
        return time.monotonic()

    def aguardar(self, segundos: float) -> None:
        """Dorme pelo intervalo informado."""
        time.sleep(segundos)


class RelogioSimulado(Relogio):
    """Relógio determinístico: cada espera apenas avança o contador interno."""

    def __init__(self, inicio: float = 0.0) -> None:
        self._instante: float = inicio
        self._esperas: list[float] = []

    def agora(self) -> float:
        """Instante corrente do relógio simulado."""
        return self._instante

    def aguardar(self, segundos: float) -> None:
        """Avança o relógio sem suspender o processo."""
        self._esperas.append(segundos)
        self._instante += segundos

    @property
    def esperas_registradas(self) -> tuple[float, ...]:
        """Intervalos pelos quais o código pediu para esperar."""
        return tuple(self._esperas)


@dataclass(frozen=True)
class PoliticaEspera:
    """Prazos aceitos pelo long-poll, com teto para não prender o transporte."""

    prazo_padrao_segundos: float = TEMPO_DE_ESPERA_PADRAO_SEGUNDOS
    intervalo_segundos: float = INTERVALO_DE_SONDAGEM_SEGUNDOS
    prazo_maximo_segundos: float = TEMPO_MAXIMO_DE_ESPERA_SEGUNDOS

    def prazo_valido(self, solicitado: Any) -> float:
        """Normaliza o prazo pedido pelo agente dentro dos limites da política."""
        if solicitado is None:
            return self.prazo_padrao_segundos
        return min(max(self._converter(solicitado), 0.0), self.prazo_maximo_segundos)

    def _converter(self, solicitado: Any) -> float:
        """Converte o valor recebido, caindo no padrão quando ele não é numérico."""
        try:
            return float(solicitado)
        except (TypeError, ValueError):
            return self.prazo_padrao_segundos
