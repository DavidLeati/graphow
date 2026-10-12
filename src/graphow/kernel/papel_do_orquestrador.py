"""O papel `orquestrador`: o laço em código que grava o livro-razão do Goal que ele conduz.

Os agentes deixaram de escrever no grafo. O planejador, o executor e o
verificador devolvem JSON validado por schema, e é o `graphow orquestrar` quem
grava o Goal, as fatias, os commits e as verificações. Ele é o único escritor
do Goal e é código testável, então o RoleGate não lhe aplica a matriz que
policiava agentes concorrentes: posse de Task, gestos da política de
governança (fechar o Goal, aprovar o que o laço decidiu) e o veredito de
revisor por Task, que a verificação do Goal substitui.

O alcance é o Goal que ele conduz: ele edita só os nós que criou e o Goal que
traz a configuração do laço (adotar o Goal do gerente é gravar nele a spec e
essa configuração), e toda aresta nova sai ou chega num nó dele. A Decision e
a Constraint do humano, o Setor e o Projeto ficam como estão.

Ficam com o humano as reservas que o laço nunca precisa, e o contrato as recusa
explicitamente: a `Governanca` e a política ou a autonomia do Projeto, o
alcance de um Aprendizado (promover), o plano aprovado e as respostas de desvio
do Goal (`aprovar_plano` e `responder_desvio`), a aprovação do plano do próprio
orquestrador (`aprovacao_do_plano`, o portão do humano), e encerrar uma Question, que é
responder ao que o executor perguntou. O orquestrador também não remove nada:
o livro-razão dele só cresce. Nenhum servidor MCP abre sessão com este papel
(mcp/identidade_sessao.py), e é por isso que ele pode ser largo.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, StatusQuestion, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import (
    PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO,
    PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO,
)
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao

PORTAO: str = "RoleGate"
# O portão do plano do `graphow orquestrar`, no Goal: só o humano o escreve.
CAMPO_APROVACAO_DO_PLANO: str = "aprovacao_do_plano"
# O Goal conduzido pelo orquestrador traz a configuração do laço; adotá-lo é
# gravar nele só a spec e essa configuração.
CAMPO_DA_CONDUCAO: str = "orquestracao"
PROPRIEDADES_DA_ADOCAO: frozenset[str] = frozenset({"spec", CAMPO_DA_CONDUCAO})
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
    TipoNo.GOAL: frozenset({CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO, CAMPO_APROVACAO_DO_PLANO}),
    TipoNo.APRENDIZADO: PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO,
}

# Promover memória é do humano; a aresta que a promove fica fora do laço.
ARESTAS_NEGADAS_AO_ORQUESTRADOR: frozenset[TipoAresta] = frozenset({TipoAresta.VALE_PARA})


@dataclass(frozen=True)
class _Lote:
    """O estado de antes e os nós que o próprio lote cria, que são do orquestrador."""

    estado: GrafoEstado
    criados: frozenset[str]

    def e_do_orquestrador(self, id_no: str) -> bool:
        """O nó nasce neste lote ou foi criado pelo orquestrador."""
        no = self.estado.nos.get(id_no)
        return id_no in self.criados or (no is not None and no.proveniencia.papel == PapelAutor.ORQUESTRADOR.value)


def validar_escrita_do_orquestrador(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Aprova o lote do orquestrador, salvo a primeira operação fora do alcance dele ou numa reserva do humano."""
    criados = frozenset(
        item.path.split("/")[2] for item in proposta.operacoes
        if item.op == OperacaoPatch.ADD and item.path.startswith("/nos/") and item.path.count("/") == SEGMENTOS_DO_ELEMENTO
    )
    lote = _Lote(estado, criados)
    for item in proposta.operacoes:
        segmentos = tuple(segmento for segmento in item.path.split("/") if segmento)
        motivo = _motivo_da_recusa(segmentos, item, lote)
        if motivo:
            return _recusar(motivo, item)
    return ResultadoValidacao.sucesso()


def _motivo_da_recusa(segmentos: Sequence[str], item: ItemPatch, lote: _Lote) -> str:
    """Por que a operação fica fora do contrato do orquestrador; vazio quando ela cabe nele."""
    if len(segmentos) < SEGMENTOS_DO_ELEMENTO:
        return ""
    if item.op == OperacaoPatch.REMOVE and len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return "o orquestrador nao remove nos nem arestas: o livro-razao dele so cresce"
    if segmentos[0] == "arestas":
        return _motivo_na_aresta(item, lote)
    if len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return _motivo_na_criacao(item.value)
    no = lote.estado.nos.get(segmentos[1])
    if no is None:
        return ""
    if no.tipo == TipoNo.GOVERNANCA:
        return "a Governanca e do humano"
    return _motivo_de_alcance(no, segmentos, lote) or _motivo_na_propriedade(no.tipo, segmentos, item)


def _motivo_de_alcance(no: NoGrafo, segmentos: Sequence[str], lote: _Lote) -> str:
    """O orquestrador edita só o que criou e o Goal que conduz (o que tem `orquestracao`).

    Adotar o Goal que o gerente gravou é gravar nele `spec` e `orquestracao`;
    depois disso o Goal é conduzido. O rótulo e as propriedades de qualquer
    outro nó (a Decision e a Constraint do humano, o Setor, o Projeto) são de
    quem os criou.
    """
    if lote.e_do_orquestrador(no.id):
        return ""
    chave = segmentos[-1] if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE else ""
    conduzido = CAMPO_DA_CONDUCAO in no.propriedades
    if no.tipo == TipoNo.GOAL and chave and (conduzido or chave in PROPRIEDADES_DA_ADOCAO):
        return ""
    papel = no.proveniencia.papel or "outro autor"
    return f"o orquestrador so edita os nos que criou e o Goal que conduz; '{no.id}' ({no.tipo.value}) e de {papel}"


def _motivo_na_aresta(item: ItemPatch, lote: _Lote) -> str:
    """A aresta que promove memória é do humano, e a aresta nova sai ou chega num nó do orquestrador."""
    valor = item.value if isinstance(item.value, dict) else {}
    if valor.get("tipo") in {tipo.value for tipo in ARESTAS_NEGADAS_AO_ORQUESTRADOR}:
        return f"a aresta '{valor.get('tipo')}' promove memoria, e promover e do humano"
    pontas = (str(valor.get("origem_id", "")), str(valor.get("destino_id", "")))
    if item.op == OperacaoPatch.ADD and not any(lote.e_do_orquestrador(ponta) for ponta in pontas):
        return f"a aresta liga {pontas[0]} a {pontas[1]}, e nenhum dos dois e do orquestrador"
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
