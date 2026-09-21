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
    "Se houver Task de condensar sessao pendente, assuma-a e escreva a Note de condensacao "
    "(acao condensacao_de_sessao) com deriva_de para cada no condensado.",
    "Nao edite o banco por fora: toda escrita passa pelas ferramentas. Promover aprendizado e "
    "encerrar a sessao sao gestos humanos; o hook de fim encerra esta.",
)


def montar_protocolo(*, papel: PapelAutor | None = None, id_sessao: str = "") -> tuple[str, ...]:
    """As linhas do protocolo, numeradas, com a sessão e o papel quando são conhecidos."""
    passos = (_passo_de_leitura(id_sessao), *PASSOS_DO_PROTOCOLO)
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
