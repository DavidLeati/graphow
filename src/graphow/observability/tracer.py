"""Spans GenAI do Graphow: coleta em memória e forma serializável.

`TracerOTel` era uma lista em memória que nenhum módulo chamava e que não
exportava nada — o README prometia suporte nativo a OpenTelemetry sobre isso.
Agora o kernel é o chamador (`kernel/telemetria.py`), a lista tem teto, e
`serializar_span` produz o formato que um coletor consegue ler. Não há SDK do
OpenTelemetry aqui: o que existe é a convenção de atributos GenAI e um
exportador de arquivo. Ver achado A-13.
"""

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any
import uuid

LIMITE_DE_SPANS_RETIDOS: int = 512


@dataclass(frozen=True)
class DadosSpanDTO:
    """DTO imutável para criação de novos spans de telemetria OTel."""

    nome_operacao: str
    atributos: Mapping[str, Any] = field(default_factory=dict)
    sucesso: bool = True
    parent_span_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class SpanGenAI:
    """Span imutável de telemetria aderente às convenções GenAI OpenTelemetry."""

    trace_id: str
    span_id: str
    nome_operacao: str
    parent_span_id: str | None
    inicio_utc: str
    fim_utc: str
    atributos: Mapping[str, Any] = field(default_factory=dict)
    sucesso: bool = True
    mensagem_erro: str | None = None


def criar_span(dados: DadosSpanDTO) -> SpanGenAI:
    """Materializa o span com identificadores e marca temporal próprios."""
    agora = datetime.now(timezone.utc).isoformat()
    return SpanGenAI(
        trace_id=dados.trace_id or str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        nome_operacao=dados.nome_operacao,
        parent_span_id=dados.parent_span_id,
        inicio_utc=agora,
        fim_utc=agora,
        atributos=dict(dados.atributos),
        sucesso=dados.sucesso,
    )


def serializar_span(span: SpanGenAI) -> dict[str, Any]:
    """Forma serializável do span, com os nomes de campo do modelo OTLP."""
    return {
        "traceId": span.trace_id,
        "spanId": span.span_id,
        "parentSpanId": span.parent_span_id,
        "name": span.nome_operacao,
        "startTime": span.inicio_utc,
        "endTime": span.fim_utc,
        "status": "OK" if span.sucesso else "ERROR",
        "attributes": dict(span.atributos),
    }


class Tracer(ABC):
    """Destino dos spans emitidos pelo kernel."""

    @abstractmethod
    def registrar_span(self, dados: DadosSpanDTO) -> SpanGenAI | None:
        """Recebe o span descrito e o encaminha ao destino concreto."""
        raise NotImplementedError


class TracerNulo(Tracer):
    """Destino padrão: não materializa span algum, para não custar nada."""

    def registrar_span(self, dados: DadosSpanDTO) -> SpanGenAI | None:
        """Descarta a descrição sem alocar o span."""
        return None


class TracerOTel(Tracer):
    """Coletor em memória dos spans de execução de agentes e ferramentas."""

    def __init__(self, limite: int = LIMITE_DE_SPANS_RETIDOS) -> None:
        self._spans: deque[SpanGenAI] = deque(maxlen=limite)
        self._lock: threading.RLock = threading.RLock()

    def registrar_span(self, dados: DadosSpanDTO) -> SpanGenAI:
        """Cria e armazena um novo span OTel a partir do DTO."""
        span = criar_span(dados)
        with self._lock:
            self._spans.append(span)
        return span

    def obter_spans_por_trace(self, trace_id: str) -> list[SpanGenAI]:
        """Recupera todos os spans associados a um determinado trace_id."""
        with self._lock:
            return [s for s in self._spans if s.trace_id == trace_id]

    def listar_todos_spans(self) -> list[SpanGenAI]:
        """Retorna cópia de todos os spans retidos, do mais antigo ao mais novo."""
        with self._lock:
            return list(self._spans)
