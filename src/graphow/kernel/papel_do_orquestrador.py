"""O papel `orquestrador`: o laço em código que grava o livro-razão do Goal que ele conduz.

Os agentes deixaram de escrever no grafo. O planejador, o executor e o
verificador devolvem JSON validado por schema, e é o `graphow orquestrar` quem
grava o Goal, as fatias, os commits e as verificações. Ele é o único escritor
do Goal e é código testável, então o RoleGate não lhe aplica a matriz que
policiava agentes concorrentes: posse de Task, gestos da política de
governança (fechar o Goal, aprovar o que o laço decidiu) e o veredito de
revisor por Task, que a verificação do Goal substitui.

Ficam com o humano as reservas que o laço nunca precisa, e o contrato as recusa
explicitamente: a `Governanca` e a política ou a autonomia do Projeto, o
alcance de um Aprendizado (promover), o plano aprovado e as respostas de desvio
do Goal (`aprovar_plano` e `responder_desvio`), e encerrar uma Question, que é
responder ao que o executor perguntou. O orquestrador também não remove nada:
o livro-razão dele só cresce. Nenhum servidor MCP abre sessão com este papel
(mcp/identidade_sessao.py), e é por isso que ele pode ser largo.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import (
    PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO,
    PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO,
)
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao

PORTAO: str = "RoleGate"
SEGMENTOS_DO_ELEMENTO: int = 2
SEGMENTOS_DA_PROPRIEDADE: int = 4
CAMPO_STATUS: str = "status"

TIPOS_CRIADOS_PELO_ORQUESTRADOR: frozenset[TipoNo] = frozenset(
    {
        TipoNo.PROJETO,
        TipoNo.SETOR,
        TipoNo.SESSAO,
        TipoNo.GOAL,
        TipoNo.TASK,
        TipoNo.DECISION,
        TipoNo.CONSTRAINT,
        TipoNo.QUESTION,
        TipoNo.ARTIFACT,
        TipoNo.EVIDENCE,
        TipoNo.NOTE,
    }
)

# O que cada tipo guarda que só o humano escreve, nem na criação nem depois.
PROPRIEDADES_RESERVADAS_POR_TIPO: Mapping[TipoNo, frozenset[str]] = {
    TipoNo.PROJETO: PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO,
    TipoNo.GOAL: frozenset({CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO}),
    TipoNo.APRENDIZADO: PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO,
}

# Promover memória é do humano; a aresta que a promove fica fora do laço.
ARESTAS_NEGADAS_AO_ORQUESTRADOR: frozenset[TipoAresta] = frozenset({TipoAresta.VALE_PARA})


def validar_escrita_do_orquestrador(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Aprova o lote do orquestrador, salvo a primeira operação que toca uma reserva do humano."""
    for item in proposta.operacoes:
        segmentos = tuple(segmento for segmento in item.path.split("/") if segmento)
        motivo = _motivo_da_recusa(segmentos, item, estado)
        if motivo:
            return _recusar(motivo, item)
    return ResultadoValidacao.sucesso()


def _motivo_da_recusa(segmentos: Sequence[str], item: ItemPatch, estado: GrafoEstado) -> str:
    """Por que a operação fica fora do contrato do orquestrador; vazio quando ela cabe nele."""
    if len(segmentos) < SEGMENTOS_DO_ELEMENTO:
        return ""
    if item.op == OperacaoPatch.REMOVE and len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return "o orquestrador nao remove nos nem arestas: o livro-razao dele so cresce"
    if segmentos[0] == "arestas":
        return _motivo_na_aresta(item)
    if len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return _motivo_na_criacao(item.value)
    no = estado.nos.get(segmentos[1])
    if no is None:
        return ""
    if no.tipo == TipoNo.GOVERNANCA:
        return "a Governanca e do humano"
    return _motivo_na_propriedade(no.tipo, segmentos, item)


def _motivo_na_aresta(item: ItemPatch) -> str:
    """A aresta que promove memória é do humano."""
    valor = item.value if isinstance(item.value, dict) else {}
    if valor.get("tipo") in {tipo.value for tipo in ARESTAS_NEGADAS_AO_ORQUESTRADOR}:
        return f"a aresta '{valor.get('tipo')}' promove memoria, e promover e do humano"
    return ""


def _motivo_na_criacao(valor: Any) -> str:
    """O nó que o laço cria é de um tipo dele e nasce sem o que só o humano escreve."""
    if not isinstance(valor, dict):
        return ""
    try:
        tipo = TipoNo(valor.get("tipo"))
    except ValueError:
        return ""
    if tipo not in TIPOS_CRIADOS_PELO_ORQUESTRADOR:
        return f"o orquestrador nao cria no do tipo '{tipo.value}'"
    propriedades = valor.get("propriedades") if isinstance(valor.get("propriedades"), dict) else {}
    reservadas = PROPRIEDADES_RESERVADAS_POR_TIPO.get(tipo, frozenset()) & set(propriedades)
    if reservadas:
        return f"'{', '.join(sorted(reservadas))}' num {tipo.value} e do humano"
    status = str(propriedades.get(CAMPO_STATUS, StatusQuestion.ABERTA.value))
    if tipo == TipoNo.QUESTION and status != StatusQuestion.ABERTA.value:
        return "a Question nasce aberta: responder e do humano"
    return ""


def _motivo_na_propriedade(tipo: TipoNo, segmentos: Sequence[str], item: ItemPatch) -> str:
    """A propriedade reservada do tipo, ou o status que encerra a dúvida."""
    if len(segmentos) != SEGMENTOS_DA_PROPRIEDADE:
        return ""
    chave = segmentos[-1]
    if chave in PROPRIEDADES_RESERVADAS_POR_TIPO.get(tipo, frozenset()):
        return f"'{chave}' num {tipo.value} e do humano"
    encerra = item.op == OperacaoPatch.REMOVE or str(item.value) != StatusQuestion.ABERTA.value
    if tipo == TipoNo.QUESTION and chave == CAMPO_STATUS and encerra:
        return "encerrar a Question e responder ao executor, e responder e do humano"
    return ""


def _recusar(motivo: str, item: ItemPatch) -> ResultadoValidacao:
    """A recusa com o caminho da operação, para o laço registrar o defeito dele."""
    return ResultadoValidacao.falha(
        f"Papel 'orquestrador': {motivo}",
        PORTAO,
        {"path": item.path},
        modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
    )
