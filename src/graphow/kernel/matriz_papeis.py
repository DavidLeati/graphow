"""Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo.

A garantia de que só o humano encerra uma escalação valia para o nome de uma
ferramenta MCP, não para o kernel: um executor trocava o status da Question por
`propor_patch` e destravava a própria tarefa. A camada de arestas nem sequer era
avaliada. Esta tabela é o dono declarado de cada operação, e o RoleGate a aplica
no portão, onde nenhum caminho alternativo escapa. Ver achados A-01 a A-03.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from graphow.core.types import PapelAutor, StatusQuestion, TipoAresta, TipoNo

TIPOS_EXCLUSIVOS_DO_HUMANO: frozenset[TipoNo] = frozenset({TipoNo.CONSTRAINT})
TIPOS_EDITAVEIS_PELO_SISTEMA: frozenset[TipoNo] = frozenset({TipoNo.RUN, TipoNo.SESSAO})

# Apagar a dúvida é a forma mais direta de encerrá-la sem resposta. Constraint já
# era intocável; Question passa a ser, porque é o único canal do agente ao humano.
TIPOS_CUJA_REMOCAO_EXIGE_HUMANO: frozenset[TipoNo] = frozenset(
    {TipoNo.CONSTRAINT, TipoNo.QUESTION}
)

# Fechar a dúvida é prerrogativa de quem foi consultado. 'aberta' segue livre:
# reabrir uma pergunta não anula garantia alguma.
STATUS_DE_QUESTION_RESERVADOS_AO_HUMANO: frozenset[str] = frozenset(
    {StatusQuestion.RESPONDIDA.value, StatusQuestion.DESCARTADA.value}
)

SO_HUMANO: frozenset[PapelAutor] = frozenset({PapelAutor.HUMANO})
HUMANO_E_PLANEJADOR: frozenset[PapelAutor] = SO_HUMANO | {PapelAutor.PLANEJADOR}
HUMANO_E_TRABALHO: frozenset[PapelAutor] = SO_HUMANO | {PapelAutor.EXECUTOR, PapelAutor.REVISOR}
TODOS_OS_PAPEIS_DE_AGENTE: frozenset[PapelAutor] = frozenset(
    {PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR}
)
HUMANO_E_AGENTES: frozenset[PapelAutor] = SO_HUMANO | TODOS_OS_PAPEIS_DE_AGENTE


@dataclass(frozen=True)
class DonosDeAresta:
    """Papéis autorizados a criar e a remover um tipo de aresta.

    Criar e remover são poderes distintos: qualquer agente pode abrir uma
    escalação com `bloqueia`, e só o humano pode retirá-la.
    """

    adicao: frozenset[PapelAutor]
    remocao: frozenset[PapelAutor]

    def autoriza(self, papel: PapelAutor, eh_remocao: bool) -> bool:
        """Consulta pura: informa se o papel pode executar a operação pedida."""
        return papel in (self.remocao if eh_remocao else self.adicao)


# A camada que estrutura o trabalho — contenção, escopo de restrição e a retirada
# de um bloqueio — pertence ao humano. A camada que registra o trabalho feito
# pertence a quem o faz.
DONOS_POR_TIPO_DE_ARESTA: Mapping[TipoAresta, DonosDeAresta] = {
    # O harness cria a Sessao em que roda e precisa pendurá-la no Setor que o
    # humano já abriu; nenhum papel de agente alcança `sistema`.
    TipoAresta.CONTEM: DonosDeAresta(
        adicao=SO_HUMANO | {PapelAutor.SISTEMA}, remocao=SO_HUMANO
    ),
    TipoAresta.PRODUZ: DonosDeAresta(
        adicao=HUMANO_E_AGENTES | {PapelAutor.SISTEMA}, remocao=SO_HUMANO
    ),
    TipoAresta.OCORREU_EM: DonosDeAresta(
        adicao=SO_HUMANO | {PapelAutor.SISTEMA}, remocao=SO_HUMANO | {PapelAutor.SISTEMA}
    ),
    TipoAresta.DECOMPOE: DonosDeAresta(adicao=HUMANO_E_PLANEJADOR, remocao=HUMANO_E_PLANEJADOR),
    TipoAresta.DEPENDE_DE: DonosDeAresta(adicao=HUMANO_E_PLANEJADOR, remocao=HUMANO_E_PLANEJADOR),
    TipoAresta.BLOQUEIA: DonosDeAresta(adicao=HUMANO_E_AGENTES, remocao=SO_HUMANO),
    TipoAresta.JUSTIFICA: DonosDeAresta(adicao=HUMANO_E_TRABALHO, remocao=HUMANO_E_TRABALHO),
    TipoAresta.CONTRADIZ: DonosDeAresta(adicao=HUMANO_E_TRABALHO, remocao=HUMANO_E_TRABALHO),
    TipoAresta.SUBSTITUI: DonosDeAresta(adicao=HUMANO_E_PLANEJADOR, remocao=HUMANO_E_PLANEJADOR),
    TipoAresta.ESCOPA: DonosDeAresta(adicao=SO_HUMANO, remocao=SO_HUMANO),
    TipoAresta.DERIVA_DE: DonosDeAresta(adicao=HUMANO_E_TRABALHO, remocao=HUMANO_E_TRABALHO),
}


# Um projeto que o humano marcou como autônomo entrega ao agente a camada que
# estrutura o trabalho — inclusive `contem`, sem a qual um Setor criado nasceria
# solto e a autonomia voltaria a ser inerte. O que a marcação nunca entrega é a
# camada de governança: `escopa` amarra Constraint ao trabalho, e retirar um
# `bloqueia` encerraria a escalação ao humano. Ver achados A-03 e A-05.
ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA: frozenset[TipoAresta] = frozenset({TipoAresta.ESCOPA})


def obter_donos_sob_autonomia_ilimitada(tipo: TipoAresta) -> DonosDeAresta:
    """Donos ampliados de um tipo de aresta dentro de um projeto autônomo.

    Só a criação é ampliada. Remover segue a tabela base, para que a retirada de
    um `bloqueia` continue exigindo sessão humana em qualquer projeto.
    """
    base = obter_donos_de_aresta(tipo)
    if tipo in ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA:
        return base
    return DonosDeAresta(adicao=base.adicao | HUMANO_E_AGENTES, remocao=base.remocao)


def obter_donos_de_aresta(tipo: TipoAresta) -> DonosDeAresta:
    """Consulta o par de donos de um tipo de aresta, negando o que não foi declarado.

    Um tipo novo sem entrada na tabela nasce fechado a agentes: esquecer de
    declarar o dono não pode virar permissão silenciosa.
    """
    return DONOS_POR_TIPO_DE_ARESTA.get(
        tipo, DonosDeAresta(adicao=SO_HUMANO, remocao=SO_HUMANO)
    )


def descrever_donos_de_aresta(tipo: TipoAresta) -> tuple[str, ...]:
    """Lista, em ordem estável, os papéis que podem criar o tipo de aresta."""
    return tuple(sorted(papel.value for papel in obter_donos_de_aresta(tipo).adicao))
