"""Interfaces abstratas de contrato para persistência de eventos e locks."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from graphow.core.events import EventoLog


class RepositorioEventos(ABC):
    """Contrato abstrato de armazenamento para eventos transacionais append-only."""

    @abstractmethod
    def append_evento(self, evento: EventoLog) -> None:
        """Persiste um único evento no log."""
        raise NotImplementedError

    @abstractmethod
    def append_eventos(self, eventos: Sequence[EventoLog]) -> None:
        """Persiste um lote de eventos de forma atômica: ou todos, ou nenhum.

        Deve levantar ErroConflitoDeSequencia se algum par (ramo_id, seq) já existir,
        preservando a unicidade da ordem de replay entre escritores concorrentes.
        """
        raise NotImplementedError

    @abstractmethod
    def ler_eventos(self, ramo_id: str = "main") -> list[EventoLog]:
        """Lê todos os eventos ordenados por número de sequência para um ramo."""
        raise NotImplementedError

    @abstractmethod
    def ler_eventos_ate_seq(self, ramo_id: str, seq_limite: int) -> list[EventoLog]:
        """Lê eventos de um ramo até um número limite de sequência inclusive."""
        raise NotImplementedError

    @abstractmethod
    def ler_eventos_desde_seq(self, ramo_id: str, seq_exclusivo: int) -> list[EventoLog]:
        """Lê os eventos de um ramo posteriores à sequência informada, exclusive."""
        raise NotImplementedError

    @abstractmethod
    def obter_ultimo_seq(self, ramo_id: str = "main") -> int:
        """Retorna o número da última sequência registrada no ramo."""
        raise NotImplementedError

    @abstractmethod
    def listar_ramos(self) -> list[str]:
        """Lista todos os identificadores de ramos existentes no store."""
        raise NotImplementedError

    @abstractmethod
    def obter_evento_por_id(self, id_evento: str) -> EventoLog | None:
        """Busca um evento específico pelo seu identificador único."""
        raise NotImplementedError


class RepositorioLocks(ABC):
    """Contrato de coordenação de escrita exclusiva sobre tarefas.

    Locks são estado de coordenação efêmero, não história: ficam fora do log de
    eventos, mas precisam ser compartilhados entre processos para que o portão de
    invariantes signifique alguma coisa quando humano e agente escrevem juntos.
    """

    @abstractmethod
    def tentar_adquirir(self, id_task: str, autor: str) -> bool:
        """Adquire o lock para o autor, ou confirma que ele já é o dono."""
        raise NotImplementedError

    @abstractmethod
    def liberar(self, id_task: str, autor: str) -> bool:
        """Libera o lock, se pertencer ao autor solicitante."""
        raise NotImplementedError

    @abstractmethod
    def obter_dono(self, id_task: str) -> str | None:
        """Consulta quem detém o lock da tarefa, se houver alguém."""
        raise NotImplementedError

    @abstractmethod
    def listar_locks(self) -> dict[str, str]:
        """Devolve um instantâneo do mapa de tarefa para autor detentor."""
        raise NotImplementedError
