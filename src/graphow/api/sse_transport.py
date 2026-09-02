"""Transporte de eventos para visualizadores de Canvas via SSE / AG-UI Protocol."""

from collections.abc import Iterator, Sequence
import json
from typing import Any

from graphow.core.events import EventoLog


class SSETransport:
    """Formatador e gerador de stream de eventos Server-Sent Events compatível com AG-UI."""

    @staticmethod
    def formatar_evento_sse(evento: EventoLog) -> str:
        """Formata um EventoLog no padrão Server-Sent Events."""
        corpo_data: dict[str, Any] = {
            "id": evento.id,
            "seq": evento.seq,
            "timestamp": evento.timestamp_utc,
            "autor": evento.autor,
            "papel": evento.papel.value,
            "origem": evento.origem.value,
            "tipo_evento": evento.tipo_evento.value,
            "ramo_id": evento.ramo_id,
            "payload": dict(evento.payload),
            "trace_id": evento.trace_id,
            "versao_ontologia": evento.versao_ontologia,
        }
        json_data = json.dumps(corpo_data, sort_keys=True, ensure_ascii=False)
        return f"event: {evento.tipo_evento.value}\nid: {evento.id}\ndata: {json_data}\n\n"

    @classmethod
    def gerar_stream_ag_ui(cls, eventos: Sequence[EventoLog]) -> Iterator[str]:
        """Gera iterador de mensagens SSE a partir de uma sequência de eventos."""
        for evento in eventos:
            yield cls.formatar_evento_sse(evento)
