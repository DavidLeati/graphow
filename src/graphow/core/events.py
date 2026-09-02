"""Definições de eventos de log transacionais append-only do Graphow."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any
import uuid

from graphow.core.ontologia import VERSAO_ONTOLOGIA
from graphow.core.types import OrigemEvento, PapelAutor


# Campos do payload de no_atualizado. Ficam aqui porque o conversor os escreve e
# o acumulador os le: duplicar a string nos dois lados e como a deriva comeca.
CAMPO_ROTULO: str = "rotulo"
CAMPO_PROPRIEDADES: str = "propriedades"
CAMPO_PROPRIEDADES_REMOVIDAS: str = "propriedades_removidas"


class TipoEvento(str, Enum):
    """Tipos de eventos registráveis no log append-only."""

    NO_CRIADO = "no_criado"
    NO_ATUALIZADO = "no_atualizado"
    NO_REMOVIDO = "no_removido"
    ARESTA_CRIADA = "aresta_criada"
    ARESTA_REMOVIDA = "aresta_removida"
    EXECUCAO_SOLICITADA = "execucao_solicitada"
    EXECUCAO_INICIADA = "execucao_iniciada"
    EXECUCAO_CONCLUIDA = "execucao_concluida"
    RAMO_CRIADO = "ramo_criado"


@dataclass(frozen=True)
class DadosCriacaoEvento:
    """DTO imutável para criação de novos eventos no log."""

    seq: int
    autor: str
    papel: PapelAutor
    tipo_evento: TipoEvento
    payload: Mapping[str, Any] = field(default_factory=dict)
    origem: OrigemEvento = OrigemEvento.HUMANO
    ramo_id: str = "main"
    parent_evento_id: str | None = None
    trace_id: str | None = None
    versao_ontologia: str = VERSAO_ONTOLOGIA


@dataclass(frozen=True)
class EventoLog:
    """Evento imutável de log append-only para fonte de verdade determinística."""

    id: str
    seq: int
    timestamp_utc: str
    autor: str
    papel: PapelAutor
    origem: OrigemEvento
    tipo_evento: TipoEvento
    payload: Mapping[str, Any] = field(default_factory=dict)
    ramo_id: str = "main"
    parent_evento_id: str | None = None
    trace_id: str | None = None
    # Qual vocabulario estava em vigor quando o fato foi escrito. Sem isso, um
    # log relido depois de a ontologia mudar projeta errado em silencio (A-17).
    versao_ontologia: str = VERSAO_ONTOLOGIA

    @classmethod
    def criar(cls, dados: DadosCriacaoEvento) -> "EventoLog":
        """Fábrica com geração automática de UUID e timestamp ISO 8601 UTC via DTO."""
        novo_id: str = str(uuid.uuid4())
        momento_atual: str = datetime.now(timezone.utc).isoformat()
        return cls(
            id=novo_id,
            seq=dados.seq,
            timestamp_utc=momento_atual,
            autor=dados.autor,
            papel=dados.papel,
            origem=dados.origem,
            tipo_evento=dados.tipo_evento,
            payload=dados.payload,
            ramo_id=dados.ramo_id,
            parent_evento_id=dados.parent_evento_id,
            trace_id=dados.trace_id,
            versao_ontologia=dados.versao_ontologia,
        )

    def serializar_payload_json(self) -> str:
        """Serializa o payload do evento em JSON ordenado determinístico."""
        return json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
