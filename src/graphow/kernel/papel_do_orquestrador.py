"""O papel `orquestrador`: o laço em código que grava o livro-razão do Goal que ele conduz.

Os agentes deixaram de escrever no grafo. O planejador, o executor e o
verificador devolvem JSON validado por schema, e é o `graphow orquestrar` quem
grava o Goal, as fatias, os commits e as verificações. Ele é o único escritor
do Goal e é código testável, então o RoleGate não lhe aplica a matriz que
policiava agentes concorrentes: posse de Task, gestos da política de
governança (fechar o Goal, aprovar o que o laço decidiu) e o veredito de
revisor por Task, que a verificação do Goal substitui.

O alcance é o Goal que o lote conduz, que o lote declara (`goal_conduzido`):
o Goal, a Sessao do orquestrador para ele (`orq-sessao-<id do Goal>`), o que
essa Sessao produz e a contenção dela (o Setor e o Projeto acima). Toda
escrita e toda aresta do lote ficam aí dentro: um lote do Goal A não escreve
no Goal B, não liga um nó dele a uma Decision do humano nem a uma Task de
outro Goal, e não cria aresta que o laço não usa. O Goal precisa ser conduzido
(ter a configuração do laço), ou nascer ou ser adotado no próprio lote: adotar
o Goal do gerente é gravar nele a spec e essa configuração. Dentro do alcance,
ele edita só os nós que criou e o Goal que conduz; a Decision e a Constraint
do humano, o Setor e o Projeto dele ficam como estão. É por o lote estar preso
ao Goal conduzido que a isenção do escopo governado (kernel/invariant_gate.py)
vale só para esse Goal.

Ficam com o humano as reservas que o laço nunca precisa, e o contrato as recusa
explicitamente: a `Governanca` e a política ou a autonomia do Projeto, o
alcance de um Aprendizado (promover), o plano aprovado e as respostas de desvio
do Goal (`aprovar_plano` e `responder_desvio`), a aprovação do plano do próprio
orquestrador (`aprovacao_do_plano`, o portão do humano), e encerrar uma Question, que é
responder ao que o executor perguntou. O orquestrador também não remove nada:
o livro-razão dele só cresce. Nenhum servidor MCP abre sessão com este papel
(mcp/identidade_sessao.py), e é por isso que ele pode ser largo.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
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
# As arestas que o livro-razão do Goal usa; nenhuma outra (substitui, motivada_por...) é do laço.
ARESTAS_DO_ORQUESTRADOR: frozenset[TipoAresta] = frozenset(
    {
        TipoAresta.PRODUZ, TipoAresta.CONTEM, TipoAresta.ESCOPA, TipoAresta.ORIENTA, TipoAresta.DECOMPOE,
        TipoAresta.DEPENDE_DE, TipoAresta.DERIVA_DE, TipoAresta.BLOQUEIA,
    }
)
PREFIXO_DA_SESSAO_DO_GOAL: str = "orq-sessao-"


def sessao_do_goal(id_goal: str) -> str:
    """A Sessao do orquestrador que produz o que ele grava do Goal."""
    return f"{PREFIXO_DA_SESSAO_DO_GOAL}{id_goal}"


@dataclass(frozen=True)
class _Lote:
    """O estado de antes, o Goal que o lote conduz e o alcance dele, com o que o próprio lote cria e liga."""

    estado: GrafoEstado
    goal: str
    criados: frozenset[str]
    produzidos: frozenset[str]
    contencao: frozenset[str]
    conduzido: bool

    @property
    def sessao(self) -> str:
        """A Sessao do orquestrador para o Goal do lote."""
        return sessao_do_goal(self.goal)

    def e_do_orquestrador(self, id_no: str) -> bool:
        """O nó nasce neste lote ou foi criado pelo orquestrador."""
        no = self.estado.nos.get(id_no)
        return id_no in self.criados or (no is not None and no.proveniencia.papel == PapelAutor.ORQUESTRADOR.value)

    def dentro(self, id_no: str) -> bool:
        """O nó é o Goal do lote, a Sessao dele, algo que ela produz ou a contenção dela."""
        return id_no in (self.goal, self.sessao) or id_no in self.produzidos or id_no in self.contencao


def validar_escrita_do_orquestrador(proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Aprova o lote do orquestrador, salvo a primeira operação fora do Goal que ele conduz ou numa reserva do humano."""
    if not proposta.goal_conduzido:
        return _recusar_lote("o lote do orquestrador diz o Goal que conduz (goal_conduzido)")
    lote = _montar_lote(proposta, estado, proposta.goal_conduzido)
    if not lote.conduzido:
        return _recusar_lote(
            f"o Goal '{lote.goal}' nao e conduzido pelo orquestrador: o lote nao o cria, nao o adota e ele nao tem 'orquestracao'"
        )
    for item in proposta.operacoes:
        segmentos = tuple(segmento for segmento in item.path.split("/") if segmento)
        motivo = _motivo_da_recusa(segmentos, item, lote)
        if motivo:
            return _recusar(motivo, item)
    return ResultadoValidacao.sucesso()


def _montar_lote(proposta: PropostaPatch, estado: GrafoEstado, goal: str) -> _Lote:
    """O lote com o alcance do Goal: o que a Sessao dele produz e a contenção acima dela, contando as arestas novas."""
    criados = frozenset(
        item.path.split("/")[2] for item in proposta.operacoes
        if item.op == OperacaoPatch.ADD and item.path.startswith("/nos/") and item.path.count("/") == SEGMENTOS_DO_ELEMENTO
    )
    arestas = [*((a.tipo.value, a.origem_id, a.destino_id) for a in estado.arestas.values()), *_arestas_novas(proposta)]
    sessao = sessao_do_goal(goal)
    produzidos = frozenset(destino for tipo, origem, destino in arestas if tipo == TipoAresta.PRODUZ.value and origem == sessao)
    goal_existente = estado.nos.get(goal)
    adota = any(item.path == f"/nos/{goal}/propriedades/{CAMPO_DA_CONDUCAO}" for item in proposta.operacoes)
    conduzido = goal in criados or adota or (goal_existente is not None and CAMPO_DA_CONDUCAO in goal_existente.propriedades)
    return _Lote(estado, goal, criados, produzidos, _acima(sessao, arestas), conduzido)


def _arestas_novas(proposta: PropostaPatch) -> Iterable[tuple[str, str, str]]:
    """As arestas que o lote cria, como (tipo, origem, destino)."""
    for item in proposta.operacoes:
        valor = item.value if isinstance(item.value, dict) else {}
        if item.op == OperacaoPatch.ADD and item.path.startswith("/arestas/") and valor:
            yield str(valor.get("tipo", "")), str(valor.get("origem_id", "")), str(valor.get("destino_id", ""))


def _acima(sessao: str, arestas: Sequence[tuple[str, str, str]]) -> frozenset[str]:
    """O que contém a Sessao, subindo pelas arestas `contem`: o Setor e o Projeto dela."""
    pais: dict[str, set[str]] = defaultdict(set)
    for tipo, origem, destino in arestas:
        if tipo == TipoAresta.CONTEM.value:
            pais[destino].add(origem)
    vistos: set[str] = set()
    fila = list(pais[sessao])
    while fila:
        atual = fila.pop()
        if atual not in vistos:
            vistos.add(atual)
            fila.extend(pais[atual])
    return frozenset(vistos)


def _motivo_da_recusa(segmentos: Sequence[str], item: ItemPatch, lote: _Lote) -> str:
    """Por que a operação fica fora do contrato do orquestrador; vazio quando ela cabe nele."""
    if len(segmentos) < SEGMENTOS_DO_ELEMENTO:
        return ""
    if item.op == OperacaoPatch.REMOVE and len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return "o orquestrador nao remove nos nem arestas: o livro-razao dele so cresce"
    if segmentos[0] == "arestas":
        return _motivo_na_aresta(segmentos, item, lote)
    if len(segmentos) == SEGMENTOS_DO_ELEMENTO:
        return _motivo_fora_do_goal(segmentos[1], lote, "nasce") or _motivo_na_criacao(item.value)
    no = lote.estado.nos.get(segmentos[1])
    if no is None:
        return ""
    if no.tipo == TipoNo.GOVERNANCA:
        return "a Governanca e do humano"
    return (
        _motivo_fora_do_goal(no.id, lote, "esta")
        or _motivo_de_alcance(no, segmentos, lote)
        or _motivo_na_propriedade(no.tipo, segmentos, item)
    )


def _motivo_fora_do_goal(id_no: str, lote: _Lote, verbo: str) -> str:
    """O nó que fica fora do Goal que o lote conduz: nem o Goal, nem a Sessao dele, nem o que ela produz ou a contém."""
    if lote.dentro(id_no):
        return ""
    return f"'{id_no}' {verbo} fora do Goal que o lote conduz ({lote.goal}): so o Goal, a Sessao {lote.sessao}, o que ela produz e a contencao dela"


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


def _motivo_na_aresta(segmentos: Sequence[str], item: ItemPatch, lote: _Lote) -> str:
    """A aresta nova é das que o laço usa, com as duas pontas no Goal do lote; a que já existe não se edita."""
    if item.op != OperacaoPatch.ADD or len(segmentos) != SEGMENTOS_DO_ELEMENTO:
        return "o orquestrador nao edita aresta: ela nasce inteira e fica como nasceu"
    valor = item.value if isinstance(item.value, dict) else {}
    tipo, origem, destino = str(valor.get("tipo", "")), str(valor.get("origem_id", "")), str(valor.get("destino_id", ""))
    if tipo in {negada.value for negada in ARESTAS_NEGADAS_AO_ORQUESTRADOR}:
        return f"a aresta '{tipo}' promove memoria, e promover e do humano"
    if tipo not in {usada.value for usada in ARESTAS_DO_ORQUESTRADOR}:
        return f"o orquestrador nao cria aresta '{tipo}': o livro-razao do Goal nao a usa"
    fora = next((ponta for ponta in (origem, destino) if not lote.dentro(ponta)), "")
    if fora:
        return f"a aresta {tipo} liga {origem} a {destino}, e '{fora}' esta fora do Goal que o lote conduz ({lote.goal})"
    if tipo == TipoAresta.PRODUZ.value and origem != lote.sessao:
        return f"no Goal {lote.goal}, so a Sessao {lote.sessao} produz"
    if tipo == TipoAresta.CONTEM.value and destino not in (lote.contencao | {lote.sessao}):
        return f"a aresta contem liga so a contencao da Sessao {lote.sessao}"
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


def _recusar_lote(motivo: str) -> ResultadoValidacao:
    """A recusa do lote inteiro, antes de olhar as operações."""
    return ResultadoValidacao.falha(f"Papel 'orquestrador': {motivo}", PORTAO, modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL)


def _recusar(motivo: str, item: ItemPatch) -> ResultadoValidacao:
    """A recusa com o caminho da operação, para o laço registrar o defeito dele."""
    return ResultadoValidacao.falha(
        f"Papel 'orquestrador': {motivo}",
        PORTAO,
        {"path": item.path},
        modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
    )
