"""Registro das reações que o kernel recusou, para que nenhuma morra calada.

O motor descartava a recusa sem deixar rastro. A reação de decisão substituída
assinava como planejador, o RoleGate a negava em `deriva_de`, e a suíte seguia
verde porque o teste conferia a emissão da proposta, nunca a aceitação dela.
Uma reação recusada em silêncio é indistinguível de uma reação que não existe.
Ver defeito V-01.
"""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass

LIMITE_DE_RECUSAS_RETIDAS: int = 64


@dataclass(frozen=True)
class ReacaoRecusada:
    """O que o kernel recusou, e por quê, ao avaliar um comportamento reativo."""

    comportamento: str
    id_evento_gatilho: str
    mensagem: str
    modo_de_falha: str | None = None

    def descrever(self) -> str:
        """Linha legível para diagnóstico, com o modo MAST quando houver."""
        sufixo = f" [{self.modo_de_falha}]" if self.modo_de_falha else ""
        return f"{self.comportamento} sobre {self.id_evento_gatilho}: {self.mensagem}{sufixo}"


class RegistroDeReacoes(ABC):
    """Destino das recusas observadas pelo motor reativo."""

    @abstractmethod
    def registrar(self, recusa: ReacaoRecusada) -> None:
        """Guarda a recusa para inspeção posterior."""
        raise NotImplementedError

    @abstractmethod
    def listar(self) -> tuple[ReacaoRecusada, ...]:
        """Recusas retidas, da mais antiga para a mais recente."""
        raise NotImplementedError


class RegistroEmMemoria(RegistroDeReacoes):
    """Retém as últimas recusas em memória, com teto para não crescer sem fim."""

    def __init__(self, limite: int = LIMITE_DE_RECUSAS_RETIDAS) -> None:
        self._recusas: deque[ReacaoRecusada] = deque(maxlen=limite)

    def registrar(self, recusa: ReacaoRecusada) -> None:
        """Acrescenta a recusa, descartando a mais antiga ao estourar o teto."""
        self._recusas.append(recusa)

    def listar(self) -> tuple[ReacaoRecusada, ...]:
        """Instantâneo imutável das recusas retidas, em ordem de chegada."""
        return tuple(self._recusas)
