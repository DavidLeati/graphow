"""O protocolo da memória dito ao agente: o mesmo texto no hook de início e no aperto de mão do MCP.

Dezessete sessões do harness nasceram e morreram com um Run cada. Os hooks
abriam e fechavam a Sessao, as ferramentas estavam no servidor, e ninguém dizia
ao agente o que fazer com elas: a skill só carrega quando ele a julga
pertinente, e o CLAUDE.md de cada projeto não fala de memória. Este é o texto
que chega sem depender de ninguém lembrar. O hook de início o imprime, e o
ambiente injeta a saída no contexto do agente; o servidor MCP o declara em
`instructions`, que o cliente mostra ao agente junto das ferramentas. Uma
fonte só, para as duas superfícies dizerem a mesma coisa. O texto é ASCII
porque atravessa canos cuja codificação ninguém controla.
"""

from collections.abc import Mapping

from graphow.context.governanca_vigente import (
    SEMPRE_HUMANOS,
    esta_toda_com_o_humano,
    gestos_com_o_arbitro,
    gestos_com_o_humano,
    nome_do_preset,
)
from graphow.core.governanca import PoliticaGovernanca, politica_padrao
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.role_gate import RoleGate

TITULO_DO_PROTOCOLO: str = "Protocolo de memoria do graphow"
NOME_DO_SERVIDOR_MCP: str = "graphow"

# Os tipos de trabalho que o agente registra enquanto trabalha, na ordem em que
# a linha do papel os cita. Run e Sessao sao do harness; Projeto, Setor, Goal e
# Constraint sao do humano.
TIPOS_DE_REGISTRO: tuple[TipoNo, ...] = (
    TipoNo.EVIDENCE,
    TipoNo.DECISION,
    TipoNo.NOTE,
    TipoNo.ARTIFACT,
    TipoNo.TASK,
    TipoNo.QUESTION,
)

# O que o portão exige a mais de um papel, dito antes da primeira recusa.
EXIGENCIAS_DO_PAPEL: Mapping[PapelAutor, str] = {
    PapelAutor.PLANEJADOR: (
        "Sua Evidence e leitura de codigo: nasce com `arquivo`, `linhas` ('120-135') e o `trecho` literal "
        "dessas linhas, ou o InvariantGate recusa com evidencia_sem_localizacao."
    ),
}

PASSOS_DO_PROTOCOLO: tuple[str, ...] = (
    "Durante o trabalho, registre no grafo o que descobriu e decidiu, produzido pela sessao "
    "(aresta produz vinda dela): Evidence para fato observado (saida de teste, log, leitura), "
    "Decision para escolha com motivo, Note para o resto; Task por `criar_tarefa`, os demais por `propor_patch`.",
    "Duvida que trava o trabalho vira `abrir_questao`; espere a pessoa em `aguardar_resposta`.",
    "Antes de terminar, destile o que vale alem desta sessao com `registrar_aprendizado` "
    "(afirmacao, como_aplicar, origens = ids dos nos de onde saiu).",
    "Se houver Task de condensar sessao ou de consolidar aprendizados pendente, assuma-a: a condensacao "
    "e uma Note (acao condensacao_de_sessao) com deriva_de para cada no condensado; a consolidacao e um "
    "`registrar_aprendizado` por tema, com substitui = os ids absorvidos e origens = as origens deles.",
)

# O último passo do protocolo depende da governança do projeto: em governança
# máxima ele é o texto de sempre; fora dela diz o que está com o árbitro.
PASSO_DO_BANCO: str = "Nao edite o banco por fora: toda escrita passa pelas ferramentas."
GESTOS_HUMANOS_NA_GOVERNANCA_MAXIMA: str = "Promover aprendizado e encerrar a sessao sao gestos humanos"
FECHO_DO_PASSO_DE_GOVERNANCA: str = "o hook de fim encerra esta."


def montar_protocolo(
    *,
    papel: PapelAutor | None = None,
    id_sessao: str = "",
    politica: PoliticaGovernanca | None = None,
) -> tuple[str, ...]:
    """As linhas do protocolo, numeradas, com a sessão, o papel e a governança quando são conhecidos.

    Sem política vale a governança máxima, o texto de antes da política ser configurável.
    """
    passos = (_passo_de_leitura(id_sessao), *PASSOS_DO_PROTOCOLO, _passo_de_governanca(politica or politica_padrao()))
    return (
        f"{TITULO_DO_PROTOCOLO} (ferramentas MCP `{NOME_DO_SERVIDOR_MCP}`):",
        *(f"{numero}. {passo}" for numero, passo in enumerate(passos, start=1)),
        *_linha_do_papel(papel),
    )


def _passo_de_leitura(id_sessao: str) -> str:
    """O primeiro passo cita a sessão quando o hook a conhece; o MCP não a conhece."""
    alvo = f"na sessao {id_sessao}" if id_sessao else "na sessao"
    return (
        f"Comece por `ler_vista` {alvo} ou na Task assumida e leia 'Aprendizados Aplicaveis' "
        "antes de decidir de novo o que ja foi decidido."
    )


def _passo_de_governanca(politica: PoliticaGovernanca) -> str:
    """O passo do banco e dos gestos de governança, derivado da política efetiva do projeto.

    Em governança máxima fica o texto que sempre disse que promover aprendizado e
    encerrar a sessão são do humano. Fora dela, lista numa linha o que está com o
    árbitro e o que segue humano, para o agente não tentar o gesto que a política
    lhe nega nem pedir ao humano o que o árbitro decide.
    """
    if esta_toda_com_o_humano(politica):
        return f"{PASSO_DO_BANCO} {GESTOS_HUMANOS_NA_GOVERNANCA_MAXIMA}; {FECHO_DO_PASSO_DE_GOVERNANCA}"
    com_arbitro = ", ".join(gesto.value for gesto in gestos_com_o_arbitro(politica)) or "nenhum"
    humanos = ", ".join((SEMPRE_HUMANOS, *(gesto.value for gesto in gestos_com_o_humano(politica))))
    return (
        f"{PASSO_DO_BANCO} Governanca {nome_do_preset(politica)}: gestos com o arbitro: {com_arbitro}. "
        f"Seguem humanos: {humanos}; {FECHO_DO_PASSO_DE_GOVERNANCA}"
    )


def _linha_do_papel(papel: PapelAutor | None) -> tuple[str, ...]:
    """O que o papel cria, lido do RoleGate, para o agente não propor o que o portão recusa."""
    if papel is None or papel == PapelAutor.HUMANO:
        return ()
    permitidos = RoleGate.NOS_CRIACAO_PERMITIDOS.get(papel, frozenset())
    tipos = ", ".join(tipo.value for tipo in TIPOS_DE_REGISTRO if tipo in permitidos)
    if TipoNo.APRENDIZADO in permitidos:
        aprendizado = "registra Aprendizado"
    else:
        aprendizado = "nao registra Aprendizado: peca ao executor ou ao revisor"
    exigencia = f" {EXIGENCIAS_DO_PAPEL[papel]}" if papel in EXIGENCIAS_DO_PAPEL else ""
    return (f"Seu papel nesta conexao e `{papel.value}`: cria {tipos}; {aprendizado}.{exigencia}",)
