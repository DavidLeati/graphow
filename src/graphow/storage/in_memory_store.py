"""Implementação em memória do repositório de eventos append-only."""

from collections import defaultdict
from collections.abc import Sequence
import threading

from graphow.core.events import EventoLog
from graphow.core.exceptions import ErroConflitoDeSequencia
from graphow.storage.interfaces import RepositorioEventos


class InMemoryEventStore(RepositorioEventos):
    """Armazenamento em memória thread-safe para testes e prototipação ultrarrápida."""

    def __init__(self) -> None:
        self._eventos_por_ramo: dict[str, list[EventoLog]] = defaultdict(list)
        self._eventos_por_id: dict[str, EventoLog] = {}
        self._sequencias_ocupadas: dict[str, set[int]] = defaultdict(set)
        self._lock: threading.RLock = threading.RLock()

    def append_evento(self, evento: EventoLog) -> None:
        """Adiciona um novo evento no log em memória com garantia de ordem."""
        self.append_eventos((evento,))

    def append_eventos(self, eventos: Sequence[EventoLog]) -> None:
        """Adiciona o lote inteiro ou nenhum, espelhando a atomicidade do SQLite."""
        if not eventos:
            return
        with self._lock:
            self._recusar_sequencias_ocupadas(eventos)
            for evento in eventos:
                self._registrar(evento)

    def _recusar_sequencias_ocupadas(self, eventos: Sequence[EventoLog]) -> None:
        """Valida o lote inteiro antes de gravar, para não deixar escrita parcial."""
        pretendidas: set[tuple[str, int]] = set()
        for evento in eventos:
            chave = (evento.ramo_id, evento.seq)
            ja_persistida = evento.seq in self._sequencias_ocupadas[evento.ramo_id]
            if ja_persistida or chave in pretendidas:
                raise ErroConflitoDeSequencia(
                    "Posicao de sequencia ja ocupada no ramo",
                    {"ramo_id": evento.ramo_id, "seq": str(evento.seq)},
                )
            pretendidas.add(chave)

    def _registrar(self, evento: EventoLog) -> None:
        """Grava o evento nos três índices internos do repositório."""
        self._eventos_por_ramo[evento.ramo_id].append(evento)
        self._eventos_por_id[evento.id] = evento
        self._sequencias_ocupadas[evento.ramo_id].add(evento.seq)

    def ler_eventos(self, ramo_id: str = "main") -> list[EventoLog]:
        """Retorna cópia da lista de eventos de um ramo ordenada por sequência."""
        with self._lock:
            return sorted(self._eventos_por_ramo.get(ramo_id, []), key=lambda evento: evento.seq)

    def ler_eventos_ate_seq(self, ramo_id: str, seq_limite: int) -> list[EventoLog]:
        """Lê eventos de um ramo filtrados até a sequência limite."""
        return [evento for evento in self.ler_eventos(ramo_id) if evento.seq <= seq_limite]

    def ler_eventos_desde_seq(self, ramo_id: str, seq_exclusivo: int) -> list[EventoLog]:
        """Lê apenas os eventos posteriores à sequência informada."""
        return [evento for evento in self.ler_eventos(ramo_id) if evento.seq > seq_exclusivo]

    def obter_ultimo_seq(self, ramo_id: str = "main") -> int:
        """Retorna a sequência do último evento persistido no ramo."""
        with self._lock:
            sequencias = self._sequencias_ocupadas.get(ramo_id)
            return max(sequencias) if sequencias else 0

    def listar_ramos(self) -> list[str]:
        """Lista identificadores de todos os ramos criados."""
        with self._lock:
            return sorted(self._eventos_por_ramo.keys())

    def obter_evento_por_id(self, id_evento: str) -> EventoLog | None:
        """Localiza um evento pelo identificador único."""
        with self._lock:
            return self._eventos_por_id.get(id_evento)
