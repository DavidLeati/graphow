"""Controlador de Server-Sent Events para transmissão de eventos em tempo real para a UI."""

from collections import OrderedDict
from collections.abc import Iterator
import json
import queue
import threading
import time

from graphow.api.sse_transport import SSETransport
from graphow.core.events import EventoLog

LIMITE_DE_IDS_LEMBRADOS: int = 2000
LIMITE_DE_EVENTOS_EM_FILA: int = 500
NOME_EVENTO_ABERTURA: str = "conexao_aberta"
NOME_EVENTO_DESCARTE: str = "assinante_descartado"
MOTIVO_DO_DESCARTE: str = "fila cheia: o cliente não acompanhou o ritmo do log"


def montar_mensagem_de_abertura() -> str:
    """Primeiro bloco do stream, que confirma ao cliente a assinatura aberta.

    O nome não pode ser `open`, `error` ou `message`: o campo `event:` do SSE
    define o tipo despachado no navegador, e esses três colidem com os eventos
    que o próprio `EventSource` emite. Chamar este bloco de `open` fazia o
    `onopen` do cliente rodar duas vezes por conexão — uma pela conexão de fato,
    outra por esta mensagem — e a ressincronização acontecia em dobro.
    """
    corpo = json.dumps({"status": "conectado"}, ensure_ascii=False)
    return f"event: {NOME_EVENTO_ABERTURA}\ndata: {corpo}\n\n"


def montar_mensagem_de_descarte() -> str:
    """Bloco SSE final que diz ao cliente por que o stream terminou.

    O nome deste evento é contrato com `static/js/sse_client.js`: renomear aqui
    sem renomear lá devolve o cliente ao silêncio que este bloco existe para
    quebrar. A suíte amarra os dois lados.
    """
    corpo = json.dumps({"motivo": MOTIVO_DO_DESCARTE}, ensure_ascii=False)
    return f"event: {NOME_EVENTO_DESCARTE}\ndata: {corpo}\n\n"


class SSEWebController:
    """Gerencia assinantes conectados e distribui eventos formatados para o Canvas via SSE."""

    def __init__(self, limite_de_eventos_em_fila: int = LIMITE_DE_EVENTOS_EM_FILA) -> None:
        self._limite_de_eventos_em_fila: int = limite_de_eventos_em_fila
        self._assinantes: list[queue.Queue[EventoLog]] = []
        self._lock: threading.Lock = threading.Lock()
        self._ids_publicados: OrderedDict[str, None] = OrderedDict()

    def registrar_assinante(self) -> queue.Queue[EventoLog]:
        """Registra um novo ouvinte de eventos em tempo real."""
        fila: queue.Queue[EventoLog] = queue.Queue(maxsize=self._limite_de_eventos_em_fila)
        with self._lock:
            self._assinantes.append(fila)
        return fila

    def remover_assinante(self, fila: queue.Queue[EventoLog]) -> None:
        """Remove o ouvinte após desconexão do cliente HTTP."""
        with self._lock:
            if fila in self._assinantes:
                self._assinantes.remove(fila)

    def esta_registrado(self, fila: queue.Queue[EventoLog]) -> bool:
        """Informa se a fila ainda pertence a um assinante ativo."""
        with self._lock:
            return fila in self._assinantes

    def despachar_evento(self, evento: EventoLog) -> int:
        """Envia o evento para todas as filas ativas, uma única vez por identificador.

        O mesmo evento chega por dois caminhos: o gancho pós-commit deste processo
        e o vigia que relê o log. Publicar duas vezes faria o canvas recarregar em
        dobro e a linha do tempo mostrar o fato repetido.
        """
        if not self._registrar_como_publicado(evento.id):
            return 0
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

    def _registrar_como_publicado(self, id_evento: str) -> bool:
        """Marca o evento como publicado e devolve False se ele já havia sido."""
        with self._lock:
            if id_evento in self._ids_publicados:
                return False
            self._ids_publicados[id_evento] = None
            while len(self._ids_publicados) > LIMITE_DE_IDS_LEMBRADOS:
                self._ids_publicados.popitem(last=False)
            return True

    def gerar_stream_para_fila(self, fila: queue.Queue[EventoLog], timeout_segundos: float = 1.0) -> Iterator[str]:
        """Gera mensagens SSE com batimento cardíaco até o assinante deixar de existir.

        O laço acabava em `while True`, e um assinante descartado por lentidão
        continuava recebendo pings de uma fila que ninguém mais alimentava: para o
        navegador o stream seguia vivo, sem evento algum e sem erro, e portanto sem
        reconectar. Terminar o iterador fecha a resposta HTTP, que é o único sinal
        que faz o `EventSource` tentar de novo.

        O que ficou na fila é descartado de propósito: quem se perdeu precisa
        reler a verdade na reconexão, não replicar um lote velho.
        """
        yield montar_mensagem_de_abertura()
        while self.esta_registrado(fila):
            yield self._proxima_mensagem(fila, timeout_segundos)
        yield montar_mensagem_de_descarte()

    def _proxima_mensagem(self, fila: queue.Queue[EventoLog], timeout_segundos: float) -> str:
        """Aguarda o próximo evento do assinante, ou devolve o batimento cardíaco."""
        try:
            return SSETransport.formatar_evento_sse(fila.get(timeout=timeout_segundos))
        except queue.Empty:
            return f": ping - {time.time()}\n\n"
