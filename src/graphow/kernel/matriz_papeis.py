"""Matriz de propriedade por papel: quem cria, edita e remove cada peça do grafo.

A garantia de que só o humano encerra uma escalação valia para o nome de uma
ferramenta MCP, não para o kernel: um executor trocava o status da Question por
`propor_patch` e destravava a própria tarefa. A camada de arestas nem sequer era
avaliada. Esta tabela é o dono declarado de cada operação, e o RoleGate a aplica
no portão, onde nenhum caminho alternativo escapa.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from graphow.core.governanca import PROPRIEDADE_GOVERNANCA_DO_PROJETO, Gesto
from graphow.core.types import PapelAutor, StatusQuestion, StatusSessao, StatusTask, TipoAresta, TipoNo

# O Governanca guarda a política que decide o que os agentes podem fazer: um
# agente que a escrevesse desligaria todos os portões. Só o humano a cria,
# edita e remove, em qualquer projeto, inclusive sob autonomia ilimitada.
TIPOS_EXCLUSIVOS_DO_HUMANO: frozenset[TipoNo] = frozenset({TipoNo.CONSTRAINT, TipoNo.GOVERNANCA})
TIPOS_EDITAVEIS_PELO_SISTEMA: frozenset[TipoNo] = frozenset({TipoNo.RUN, TipoNo.SESSAO})

# Apagar a dúvida é a forma mais direta de encerrá-la sem resposta. Constraint já
# era intocável; Question passa a ser, porque é o único canal do agente ao humano.
TIPOS_CUJA_REMOCAO_EXIGE_HUMANO: frozenset[TipoNo] = frozenset(
    {TipoNo.CONSTRAINT, TipoNo.QUESTION, TipoNo.APRENDIZADO}
)

# Um Aprendizado é substituído ou contradito, nunca apagado em silêncio: a
# remoção fica com o humano, como Question e Constraint. E o alcance dele é a
# promoção: um agente que escrevesse `alcance` promoveria o próprio aprendizado.
PROPRIEDADES_DE_APRENDIZADO_RESERVADAS_AO_HUMANO: frozenset[str] = frozenset({"alcance"})

# Fechar a dúvida é prerrogativa de quem foi consultado. O agente escreve só
# 'aberta': reabrir uma pergunta não anula garantia alguma. É lista branca, e
# não a lista dos status que fecham, porque o InvariantGate só trava a Task
# enquanto o status é exatamente 'aberta': um 'resolvida' inventado passava
# pela lista negra e destravava a tarefa do mesmo jeito.
STATUS_DE_QUESTION_ESCRITOS_POR_AGENTES: frozenset[str] = frozenset({StatusQuestion.ABERTA.value})

# O nível de autonomia amplia o que os agentes criam no projeto, e a propriedade
# `governanca` é a política que decide quem faz cada gesto nele. Quem as escreve
# é o humano, sem árbitro nem exceção: é o meta-portão, porque um agente que
# escrevesse a política se daria todos os gestos que ela governa. Na criação de
# um Projeto o agente só declara o nível estrito e não declara `governanca`.
PROPRIEDADES_DE_PROJETO_RESERVADAS_AO_HUMANO: frozenset[str] = frozenset(
    {"nivel_autonomia", PROPRIEDADE_GOVERNANCA_DO_PROJETO}
)

# O árbitro encerra uma dúvida só com um destes status, os que a ontologia
# declara. Um status inventado destravaria a Task sem ser resposta nem descarte.
STATUS_DE_QUESTION_ESCRITOS_PELO_ARBITRO: frozenset[str] = frozenset(
    {StatusQuestion.RESPONDIDA.value, StatusQuestion.DESCARTADA.value}
)

# Escrever este status num Goal o fecha, e escrever o da Sessao a encerra: são
# os gestos `fechar_goal` e `encerrar_sessao` da política de governança.
STATUS_QUE_FECHA_GOAL: str = StatusTask.CONCLUIDO.value
STATUS_QUE_ENCERRA_SESSAO: str = StatusSessao.CONCLUIDA.value

# O gesto `constraint` entrega ao árbitro o único tipo que TIPOS_EXCLUSIVOS_DO_HUMANO
# deixa a um agente. O Governanca nunca sai da lista: a política não se escreve sozinha.
TIPOS_LIBERADOS_POR_GESTO: Mapping[TipoNo, Gesto] = {TipoNo.CONSTRAINT: Gesto.CONSTRAINT}

# O veredito de uma Evidence é o julgamento que libera o fechamento da Task: só
# quem julga o escreve, e só o veredito de quem julga conta para o fechar. Sem
# isso o executor criava a própria aprovação, ou trocava a do revisor.
PAPEIS_QUE_JULGAM: frozenset[PapelAutor] = frozenset({PapelAutor.REVISOR, PapelAutor.HUMANO, PapelAutor.ARBITRO})
# O aceite pelo teto de correções é do condutor (planejador), do humano ou do
# árbitro: o executor que fecha a Task não decide aceitar a própria entrega.
PAPEIS_QUE_ACEITAM_A_ENTREGA: frozenset[PapelAutor] = frozenset(
    {PapelAutor.PLANEJADOR, PapelAutor.HUMANO, PapelAutor.ARBITRO}
)



def papel_julga(papel: str) -> bool:
    """O papel gravado na proveniência de um nó é de quem julga, e seu veredito conta."""
    return papel in {julgador.value for julgador in PAPEIS_QUE_JULGAM}


def papel_aceita_a_entrega(papel: str) -> bool:
    """O papel gravado na proveniência de um nó é de quem pode aceitar a entrega pelo teto."""
    return papel in {aceitador.value for aceitador in PAPEIS_QUE_ACEITAM_A_ENTREGA}


# Cópia deliberada de mcp/identidade_sessao.SEPARADOR_DO_SUFIXO_DE_CONEXAO: o
# kernel não importa o servidor MCP, que importa o kernel. Um teste confere que
# as duas constantes não se afastam.
SEPARADOR_DO_SUFIXO_DE_CONEXAO: str = "#"


def autor_sem_sufixo_de_conexao(autor: str) -> str:
    """O autor sem o sufixo `#xxxx` que a conexão acrescenta para ter posse própria."""
    cabeca, separador, _ = autor.rpartition(SEPARADOR_DO_SUFIXO_DE_CONEXAO)
    return cabeca if separador else autor


def eh_autoria_propria(autor_da_proposta: str, aberta_por: object) -> bool:
    """Diz se quem propõe é quem abriu a dúvida, comparando sem o sufixo da conexão.

    O árbitro que encerrasse a Question que ele mesmo abriu seria juiz em causa
    própria. O sufixo muda a cada conexão; o nome declarado é o que fica.
    """
    if not isinstance(aberta_por, str) or not aberta_por:
        return False
    return autor_sem_sufixo_de_conexao(autor_da_proposta) == autor_sem_sufixo_de_conexao(aberta_por)

SO_HUMANO: frozenset[PapelAutor] = frozenset({PapelAutor.HUMANO})
HUMANO_E_PLANEJADOR: frozenset[PapelAutor] = SO_HUMANO | {PapelAutor.PLANEJADOR}
HUMANO_E_TRABALHO: frozenset[PapelAutor] = SO_HUMANO | {PapelAutor.EXECUTOR, PapelAutor.REVISOR}
# Justificar é ligar a Evidence à Decision que ela sustenta. Quem registra os
# dois lados justifica: o planejador decide sobre o trecho que leu, e o árbitro
# liga a Evidence que leu à Decision que a resposta dele sustenta.
QUEM_JUSTIFICA: frozenset[PapelAutor] = HUMANO_E_TRABALHO | {PapelAutor.PLANEJADOR, PapelAutor.ARBITRO}
TODOS_OS_PAPEIS_DE_AGENTE: frozenset[PapelAutor] = frozenset(
    {PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.ARBITRO}
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
    TipoAresta.JUSTIFICA: DonosDeAresta(adicao=QUEM_JUSTIFICA, remocao=QUEM_JUSTIFICA),
    TipoAresta.CONTRADIZ: DonosDeAresta(adicao=HUMANO_E_TRABALHO, remocao=HUMANO_E_TRABALHO),
    TipoAresta.SUBSTITUI: DonosDeAresta(adicao=HUMANO_E_PLANEJADOR, remocao=HUMANO_E_PLANEJADOR),
    TipoAresta.ESCOPA: DonosDeAresta(adicao=SO_HUMANO, remocao=SO_HUMANO),
    TipoAresta.DERIVA_DE: DonosDeAresta(adicao=HUMANO_E_TRABALHO, remocao=HUMANO_E_TRABALHO),
    # Promover um aprendizado a um Projeto ou Setor é dar a ele alcance sobre o
    # trabalho de todos. Só o humano, no início: abrir ao planejador é decisão
    # a tomar com o número do braço "entre projetos" de `graphow avaliar`.
    TipoAresta.VALE_PARA: DonosDeAresta(adicao=SO_HUMANO, remocao=SO_HUMANO),
    # Dizer em que trabalho uma decisão vale é estruturar o trabalho, como
    # decompor. Aberta ao executor, ela deixava quem executa tirar da própria
    # tarefa a decisão que a governa, ou pendurar a sua no Goal inteiro. O
    # executor devolve a decisão que tomou; o planejador julga se ela governa.
    TipoAresta.ORIENTA: DonosDeAresta(adicao=HUMANO_E_PLANEJADOR, remocao=HUMANO_E_PLANEJADOR),
}

# Arestas cujo dono, além da tabela por papel, é decidido por um gesto da
# política de governança: reter ao humano ou entregar ao árbitro. A tabela segue
# valendo; o gesto só acrescenta quem pode, nunca tira.
PARES_DO_GESTO_PROMOVER_APRENDIZADO: frozenset[tuple[TipoNo, TipoNo]] = frozenset(
    {(TipoNo.APRENDIZADO, TipoNo.SETOR), (TipoNo.APRENDIZADO, TipoNo.PROJETO)}
)


def gesto_da_aresta(
    tipo: TipoAresta,
    par: tuple[TipoNo, TipoNo] | None,
    eh_remocao: bool,
) -> Gesto | None:
    """O gesto de governança que decide a operação sobre a aresta, ou None se a tabela decide sozinha.

    Retirar `bloqueia` é responder a dúvida; `escopa` é a camada de Constraint;
    `vale_para` de um Aprendizado a um Setor ou Projeto é promovê-lo.
    """
    if tipo == TipoAresta.BLOQUEIA:
        return Gesto.RESPONDER_QUESTAO if eh_remocao else None
    if tipo == TipoAresta.ESCOPA:
        return Gesto.CONSTRAINT
    if tipo == TipoAresta.VALE_PARA and par in PARES_DO_GESTO_PROMOVER_APRENDIZADO:
        return Gesto.PROMOVER_APRENDIZADO
    return None


# O dono pode depender do que a aresta liga. Consolidar memória é escrever um
# Aprendizado que substitui vários; quem registra Aprendizado (executor e
# revisor, donos de `deriva_de`) pode dizê-lo, e o planejador já detinha
# `substitui`. O substituído só sai da vista quando o humano promove o novo
# (context/memoria.py): substituir é propor, promover é aceitar. Remover a
# substituição segue com humano e planejador, como nas outras.
DONOS_POR_PAR_DE_ARESTA: Mapping[tuple[TipoAresta, TipoNo, TipoNo], DonosDeAresta] = {
    (TipoAresta.SUBSTITUI, TipoNo.APRENDIZADO, TipoNo.APRENDIZADO): DonosDeAresta(
        adicao=HUMANO_E_AGENTES, remocao=HUMANO_E_PLANEJADOR
    ),
}


# Um projeto cuja política tem `estrutura: ilimitado` (antes, o `nivel_autonomia`
# que o humano marcava) entrega ao agente a camada que estrutura o trabalho — inclusive `contem`, sem a qual um Setor criado nasceria
# solto e a autonomia voltaria a ser inerte. O que a marcação nunca entrega é a
# camada de governança: `escopa` amarra Constraint ao trabalho, retirar um
# `bloqueia` encerraria a escalação ao humano, e `vale_para` promoveria memória
# de agente a memória de todos.
ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA: frozenset[TipoAresta] = frozenset(
    {TipoAresta.ESCOPA, TipoAresta.VALE_PARA}
)


def obter_donos_sob_autonomia_ilimitada(
    tipo: TipoAresta, par: tuple[TipoNo, TipoNo] | None = None
) -> DonosDeAresta:
    """Donos ampliados de um tipo de aresta dentro de um projeto autônomo.

    Só a criação é ampliada. Remover segue a tabela base, para que a retirada de
    um `bloqueia` continue exigindo sessão humana em qualquer projeto.
    """
    base = obter_donos_de_aresta(tipo, par)
    if tipo in ARESTAS_NEGADAS_SOB_AUTONOMIA_ILIMITADA:
        return base
    return DonosDeAresta(adicao=base.adicao | HUMANO_E_AGENTES, remocao=base.remocao)


def obter_donos_de_aresta(tipo: TipoAresta, par: tuple[TipoNo, TipoNo] | None = None) -> DonosDeAresta:
    """Consulta os donos de um tipo de aresta, negando o que não foi declarado.

    Um tipo novo sem entrada na tabela nasce fechado a agentes: esquecer de
    declarar o dono não pode virar permissão silenciosa. Quando o par de tipos
    das pontas é conhecido e tem entrada própria, ela prevalece sobre o tipo.
    """
    if par is not None and (tipo, par[0], par[1]) in DONOS_POR_PAR_DE_ARESTA:
        return DONOS_POR_PAR_DE_ARESTA[(tipo, par[0], par[1])]
    return DONOS_POR_TIPO_DE_ARESTA.get(
        tipo, DonosDeAresta(adicao=SO_HUMANO, remocao=SO_HUMANO)
    )


def descrever_donos_de_aresta(tipo: TipoAresta) -> tuple[str, ...]:
    """Lista, em ordem estável, os papéis que podem criar o tipo de aresta."""
    return tuple(sorted(papel.value for papel in obter_donos_de_aresta(tipo).adicao))
