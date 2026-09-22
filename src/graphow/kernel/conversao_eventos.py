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
SEGMENTOS_DO_ELEMENTO_INTEIRO: int = 2
SEGMENTOS_DE_UMA_PROPRIEDADE: int = 4
MARCADOR_DE_ID: str = "<id>"
MARCADOR_DE_CHAVE: str = "<chave>"

# As formas que o conversor grava como a operação diz, e nada além delas. Fora
# daqui o evento dizia outra coisa: `test`, `move` e `copy` viravam escrita,
# `add` em `/arestas/<id>/...` criava a aresta com o valor inteiro, `remove` do
# rótulo gravava "None" e `replace` no nó inteiro virava uma propriedade com o
# nome do id. O SchemaGate recusa o que não está na tabela; o conversor não o
# traduz.
OPERACOES_POR_FORMA: Mapping[tuple[str, ...], frozenset[OperacaoPatch]] = {
    (SEGMENTO_NOS, MARCADOR_DE_ID): frozenset({OperacaoPatch.ADD, OperacaoPatch.REMOVE}),
    (SEGMENTO_NOS, MARCADOR_DE_ID, CAMPO_ROTULO): frozenset({OperacaoPatch.ADD, OperacaoPatch.REPLACE}),
    (SEGMENTO_NOS, MARCADOR_DE_ID, SEGMENTO_PROPRIEDADES, MARCADOR_DE_CHAVE): frozenset(
        {OperacaoPatch.ADD, OperacaoPatch.REPLACE, OperacaoPatch.REMOVE}
    ),
    (SEGMENTO_ARESTAS, MARCADOR_DE_ID): frozenset({OperacaoPatch.ADD, OperacaoPatch.REMOVE}),
}


def forma_do_caminho(segmentos: Sequence[str]) -> tuple[str, ...]:
    """O caminho com o id do elemento e a chave da propriedade trocados por marcadores."""
    if len(segmentos) < SEGMENTOS_DO_ELEMENTO_INTEIRO:
        return tuple(segmentos)
    forma = [segmentos[0], MARCADOR_DE_ID, *segmentos[SEGMENTOS_DO_ELEMENTO_INTEIRO:]]
    if len(forma) == SEGMENTOS_DE_UMA_PROPRIEDADE and forma[2] == SEGMENTO_PROPRIEDADES:
        forma[3] = MARCADOR_DE_CHAVE
    return tuple(forma)


def grava_como_diz(segmentos: Sequence[str], op: OperacaoPatch) -> bool:
    """Diz se o conversor grava a operação neste caminho como ela é, sem reinterpretá-la."""
    return op in OPERACOES_POR_FORMA.get(forma_do_caminho(segmentos), frozenset())


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
        reativo, e `COMPORTAMENTO` nunca chegava a ser usado.
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
        """Converte uma operação individual; a que o log não gravaria como ela diz fica de fora."""
        segmentos = tuple(segmento for segmento in item.path.split("/") if segmento)
        if not grava_como_diz(segmentos, item.op):
            return None
        contexto = ContextoConversaoEvento(segmentos=segmentos, item=item, proposta=proposta, seq=seq)
        if segmentos[0] == SEGMENTO_NOS:
            return self._evento_de_no(contexto)
        return self._evento_de_aresta(contexto)

    def _evento_de_no(self, contexto: ContextoConversaoEvento) -> EventoLog:
        """Gera o evento correspondente a uma mutação em nó."""
        id_no = contexto.segmentos[1]
        eh_operacao_sobre_o_no_inteiro = len(contexto.segmentos) == SEGMENTOS_DO_ELEMENTO_INTEIRO
        if eh_operacao_sobre_o_no_inteiro and contexto.item.op == OperacaoPatch.ADD:
            return self._montar(contexto, TipoEvento.NO_CRIADO, contexto.item.value)
        if eh_operacao_sobre_o_no_inteiro and contexto.item.op == OperacaoPatch.REMOVE:
            return self._montar(contexto, TipoEvento.NO_REMOVIDO, {"id": id_no})
        return self._montar(contexto, TipoEvento.NO_ATUALIZADO, self._payload_de_atualizacao(contexto))

    def _payload_de_atualizacao(self, contexto: ContextoConversaoEvento) -> dict[str, Any]:
        """Monta o payload de atualização do rótulo ou de uma propriedade nomeada.

        Decide pela forma do caminho, não pelo último segmento: uma propriedade
        chamada `rotulo` era gravada como o rótulo do nó. A remoção viaja
        declarada no evento; inferi-la do valor nulo confundiria apagar a chave
        com gravá-la como nula, e nulo é um valor que alguém pode querer escrever.
        """
        id_no = contexto.segmentos[1]
        if len(contexto.segmentos) != SEGMENTOS_DE_UMA_PROPRIEDADE:
            return {"id": id_no, CAMPO_ROTULO: contexto.item.value}
        chave = contexto.segmentos[-1]
        if contexto.item.op == OperacaoPatch.REMOVE:
            return {"id": id_no, CAMPO_PROPRIEDADES_REMOVIDAS: [chave]}
        return {"id": id_no, CAMPO_PROPRIEDADES: {chave: contexto.item.value}}

    def _evento_de_aresta(self, contexto: ContextoConversaoEvento) -> EventoLog:
        """Gera a criação ou a remoção da aresta inteira: aresta não tem campo editável."""
        if contexto.item.op == OperacaoPatch.ADD:
            return self._montar(contexto, TipoEvento.ARESTA_CRIADA, contexto.item.value)
        return self._montar(contexto, TipoEvento.ARESTA_REMOVIDA, {"id": contexto.segmentos[1]})

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
