"""Controlador de Server-Sent Events para transmissão de eventos em tempo real para a UI."""

from collections.abc import Iterator
import queue
import threading
import time

from graphow.api.sse_transport import SSETransport
from graphow.core.events import EventoLog


class SSEWebController:
    """Gerencia assinantes conectados e distribui eventos formatados para o Canvas via SSE."""

    def __init__(self) -> None:
        self._assinantes: list[queue.Queue[EventoLog]] = []
        self._lock: threading.Lock = threading.Lock()

    def registrar_assinante(self) -> queue.Queue[EventoLog]:
        """Registra um novo ouvinte de eventos em tempo real."""
        fila: queue.Queue[EventoLog] = queue.Queue(maxsize=500)
        with self._lock:
            self._assinantes.append(fila)
        return fila

    def remover_assinante(self, fila: queue.Queue[EventoLog]) -> None:
        """Remove o ouvinte após desconexão do cliente HTTP."""
        with self._lock:
            if fila in self._assinantes:
                self._assinantes.remove(fila)

    def despachar_evento(self, evento: EventoLog) -> int:
        """Envia o evento para todas as filas ativas registradas."""
        with self._lock:
            copia_assinantes = list(self._assinantes)
        enviados = 0
        for fila in copia_assinantes:
            try:
                fila.put_nowait(evento)
                enviados += 1
            except queue.Full:
                self.remover_assinante(fila)
        return enviados

    def gerar_stream_para_fila(self, fila: queue.Queue[EventoLog], timeout_segundos: float = 1.0) -> Iterator[str]:
        """Gera iterador contínuo de mensagens SSE com batimento cardíaco (ping/keep-alive)."""
        yield "event: open\ndata: {\"status\": \"conectado\"}\n\n"
        while True:
            try:
                evento = fila.get(timeout=timeout_segundos)
                yield SSETransport.formatar_evento_sse(evento)
            except queue.Empty:
                yield f": ping - {time.time()}\n\n"
