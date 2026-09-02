"""Conversão de operações JSON Patch RFC 6902 em eventos formais do log."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.events import (
    CAMPO_PROPRIEDADES,
    CAMPO_PROPRIEDADES_REMOVIDAS,
    CAMPO_ROTULO,
    DadosCriacaoEvento,
    EventoLog,
    TipoEvento,
)
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch

SEGMENTO_NOS: str = "nos"
SEGMENTO_ARESTAS: str = "arestas"
SEGMENTO_PROPRIEDADES: str = "propriedades"
SEGMENTOS_DE_UMA_PROPRIEDADE: int = 4


@dataclass(frozen=True)
class ContextoConversaoEvento:
    """DTO imutável para conversão de uma operação de patch em evento."""

    segmentos: Sequence[str]
    item: ItemPatch
    proposta: PropostaPatch
    seq: int

    @property
    def origem(self) -> OrigemEvento:
        """Origem declarada na proposta ou, na ausência dela, derivada do papel.

        Derivar sempre do papel carimbava "harness" em todo patch do motor
        reativo, e `COMPORTAMENTO` nunca chegava a ser usado. Ver achado A-10.
        """
        if self.proposta.origem is not None:
            return self.proposta.origem
        if self.proposta.papel == PapelAutor.HUMANO:
            return OrigemEvento.HUMANO
        return OrigemEvento.HARNESS


class ConversorPatchParaEventos:
    """Traduz uma proposta aprovada na sequência de eventos que a representa."""

    def converter(self, proposta: PropostaPatch, seq_base: int) -> tuple[EventoLog, ...]:
        """Numera e converte cada operação da proposta a partir da sequência base."""
        eventos: list[EventoLog] = []
        for item in proposta.operacoes:
            evento = self._converter_item(item, proposta, seq_base + len(eventos) + 1)
            if evento is not None:
                eventos.append(evento)
        return tuple(eventos)

    def _converter_item(self, item: ItemPatch, proposta: PropostaPatch, seq: int) -> EventoLog | None:
        """Converte uma operação individual, ignorando caminhos fora da ontologia."""
        segmentos = tuple(segmento for segmento in item.path.split("/") if segmento)
        if not segmentos:
            return None
        contexto = ContextoConversaoEvento(segmentos=segmentos, item=item, proposta=proposta, seq=seq)
        if segmentos[0] == SEGMENTO_NOS:
            return self._evento_de_no(contexto)
        if segmentos[0] == SEGMENTO_ARESTAS:
            return self._evento_de_aresta(contexto)
        return None

    def _evento_de_no(self, contexto: ContextoConversaoEvento) -> EventoLog | None:
        """Gera o evento correspondente a uma mutação em nó."""
        id_no = contexto.segmentos[1]
        eh_operacao_sobre_o_no_inteiro = len(contexto.segmentos) == 2
        if eh_operacao_sobre_o_no_inteiro and contexto.item.op == OperacaoPatch.ADD:
            return self._montar(contexto, TipoEvento.NO_CRIADO, contexto.item.value)
        if eh_operacao_sobre_o_no_inteiro and contexto.item.op == OperacaoPatch.REMOVE:
            return self._montar(contexto, TipoEvento.NO_REMOVIDO, {"id": id_no})
        return self._montar(contexto, TipoEvento.NO_ATUALIZADO, self._payload_de_atualizacao(contexto))

    def _payload_de_atualizacao(self, contexto: ContextoConversaoEvento) -> dict[str, Any]:
        """Monta o payload de atualização de rótulo ou de propriedade isolada."""
        id_no = contexto.segmentos[1]
        campo = contexto.segmentos[-1]
        if campo == CAMPO_ROTULO:
            return {"id": id_no, CAMPO_ROTULO: contexto.item.value}
        if self._remove_uma_propriedade(contexto):
            return {"id": id_no, CAMPO_PROPRIEDADES_REMOVIDAS: [campo]}
        return {"id": id_no, CAMPO_PROPRIEDADES: {campo: contexto.item.value}}

    def _remove_uma_propriedade(self, contexto: ContextoConversaoEvento) -> bool:
        """Indica se a operação apaga uma propriedade nomeada de um nó.

        A intenção precisa viajar no evento. Inferi-la do valor nulo confundiria
        apagar a chave com gravá-la como nula — e nulo é um valor que alguém pode
        legitimamente querer escrever.
        """
        if contexto.item.op != OperacaoPatch.REMOVE:
            return False
        if len(contexto.segmentos) != SEGMENTOS_DE_UMA_PROPRIEDADE:
            return False
        return contexto.segmentos[2] == SEGMENTO_PROPRIEDADES

    def _evento_de_aresta(self, contexto: ContextoConversaoEvento) -> EventoLog | None:
        """Gera o evento correspondente a uma mutação em aresta."""
        if contexto.item.op == OperacaoPatch.ADD:
            return self._montar(contexto, TipoEvento.ARESTA_CRIADA, contexto.item.value)
        if contexto.item.op == OperacaoPatch.REMOVE:
            return self._montar(contexto, TipoEvento.ARESTA_REMOVIDA, {"id": contexto.segmentos[1]})
        return None

    def _montar(
        self,
        contexto: ContextoConversaoEvento,
        tipo_evento: TipoEvento,
        payload: Mapping[str, Any] | None,
    ) -> EventoLog:
        """Constrói o evento imutável com os metadados de autoria da proposta."""
        dados = DadosCriacaoEvento(
            seq=contexto.seq,
            autor=contexto.proposta.autor,
            papel=contexto.proposta.papel,
            tipo_evento=tipo_evento,
            payload=dict(payload or {}),
            origem=contexto.origem,
            ramo_id=contexto.proposta.ramo_id,
            trace_id=contexto.proposta.trace_id,
        )
        return EventoLog.criar(dados)
