"""Como o orquestrador guarda um Goal no livro-razão: ids, propriedades e a configuração do laço.

O estado do laço não fica na memória do processo: está nos nós que o
orquestrador grava (o Goal, as fatias como Task, as dúvidas como Question, os
commits como Artifact, as verificações como Evidence) e no git da área. Rodar
de novo relê tudo daqui e segue de onde parou. Os nomes ficam num lugar só
para a escrita (orquestrador/livro_razao.py) e a leitura
(orquestrador/leitura_do_goal.py) não divergirem.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.harness.ambiente_padrao import gerar_slug
from graphow.kernel.papel_do_orquestrador import CAMPO_APROVACAO_DO_PLANO as CAMPO_DA_APROVACAO
from graphow.kernel.papel_do_orquestrador import sessao_do_goal

AUTOR_DO_ORQUESTRADOR: str = "graphow-orquestrar"

MODO_SUPERVISIONADO: str = "supervisionado"
MODO_AUTONOMO: str = "autonomo"
MODOS: tuple[str, ...] = (MODO_SUPERVISIONADO, MODO_AUTONOMO)

# No Goal.
CAMPO_SPEC: str = "spec"
CAMPO_ORQUESTRACAO: str = a.CAMPO_CONDUCAO
CAMPO_PLANO: str = a.CAMPO_PLANO
# A saída do planejador já conferida, gravada antes do commit do documento e do
# plano: a retomada a reaproveita em vez de pagar outra sessão.
CAMPO_PLANO_PROPOSTO: str = "plano_proposto"
CAMPO_CICLOS: str = "ciclos_de_correcao"
# Os testes de aceite: o commit, o comando que roda só eles, os arquivos que o
# executor não toca e o aceite de cada critério. E a saída conferida do autor
# de aceite, gravada antes do commit para a retomada não pagar outra sessão.
CAMPO_ACEITE: str = "aceite"
CAMPO_ACEITE_PROPOSTO: str = "aceite_proposto"
CAMPO_PENDENCIAS: str = "pendencias"
CAMPO_INTEGRADO_EM: str = "integrado_em"
# A ponta da branch do Goal como o orquestrador a viu no git: o commit e o commit
# do código (o último que mudou algo além do documento do Goal). O kernel só
# deixa o Goal fechar com a verificação final feita nesse commit do código.
CAMPO_PONTA_DO_RAMO: str = a.CAMPO_PONTA_DO_RAMO
CAMPO_COMMIT_DO_CODIGO: str = a.CAMPO_COMMIT_DO_CODIGO
# O portão do plano do orquestrador: quem aprovou, com que papel e em que commit
# do documento do Goal. Só o humano o escreve (`--aprovar-plano`); o contrato do
# papel orquestrador o recusa (kernel/papel_do_orquestrador.py).
CAMPO_APROVACAO_DO_PLANO: str = CAMPO_DA_APROVACAO
CAMPO_STATUS: str = "status"

# Na Task de cada fatia.
CAMPO_FATIA: str = "fatia"
CAMPO_OBJETIVO: str = "objetivo"
CAMPO_CRITERIOS: str = "criterios"
CAMPO_ARQUIVOS_ALVO: str = "arquivos_alvo"
# O marco da fatia: as fatias de um marco rodam antes das do seguinte, e o
# verificador olha o marco quando todas elas fecham.
CAMPO_MARCO: str = a.CAMPO_MARCO
CAMPO_MODELO: str = "modelo"
# A fatia de risco: o planejador a marca (julgamento de domínio, mudança que
# atravessa partes), e só nela uma sessão de revisão julga o diff antes do commit.
CAMPO_RISCO: str = "risco"
CAMPO_MOTIVO_DO_RISCO: str = "motivo_do_risco"
CAMPO_ORDEM: str = "ordem"
CAMPO_TENTATIVAS: str = "tentativas"
CAMPO_FALHAS: str = "falhas"
CAMPO_ULTIMO_ERRO: str = "ultimo_erro"
CAMPO_PATCH: str = "patch_da_tentativa"
CAMPO_PENDENCIA: str = "pendencia"
CAMPO_COMMIT: str = a.CAMPO_COMMIT
# Na fatia de correção: a Evidence de verificação de onde ela nasceu. Nome próprio,
# e não o `corrige` do escopo governado: o laço não depende das regras dele.
CAMPO_CORRIGE: str = "corrige_verificacao"
# Na fatia de correção: o Achado bloqueante que ela corrige (a Task deriva dele).
CAMPO_ACHADO: str = "achado"
# A fatia de correção junta os bloqueantes do mesmo arquivo (ou do mesmo critério): os ids de todos eles.
CAMPO_ACHADOS: str = "achados"
# Os ciclos de correção que cada marco tem antes de o laço seguir sem ele (ou, na final, parar).
MAXIMO_DE_CICLOS_DE_CORRECAO: int = 2


def achados_da_correcao(propriedades: Mapping[str, Any]) -> tuple[str, ...]:
    """Os Achados que a fatia de correção corrige: a lista, ou o único da fatia de antes do agrupamento."""
    lista = propriedades.get(CAMPO_ACHADOS)
    if isinstance(lista, list) and lista:
        return tuple(str(item) for item in lista)
    unico = str(propriedades.get(CAMPO_ACHADO) or "")
    return (unico,) if unico else ()


def id_da_revisao(id_task: str, tentativa: int) -> str:
    """O id da Evidence da revisão de risco de uma tentativa da fatia."""
    return f"rev-{id_task}-t{tentativa}"
CAMPO_CRITERIO_PRONTO: str = "criterio_pronto"

# Na Question e na Evidence.
CAMPO_PERGUNTA: str = "pergunta"
CAMPO_RESPOSTA: str = "resposta"
CAMPO_ABERTA_POR: str = "aberta_por"
CAMPO_VEREDITO: str = a.CAMPO_VEREDITO
CAMPO_CICLO: str = "ciclo"
CAMPO_NUMERO: str = a.CAMPO_NUMERO
CAMPO_FINAL: str = a.CAMPO_FINAL
CAMPO_PARECERES: str = a.CAMPO_PARECERES
ACAO_DA_VERIFICACAO: str = a.ACAO_DA_VERIFICACAO
ACAO_DA_TENTATIVA: str = "tentativa_que_falhou"

VEREDITO_LIMPO: str = a.VEREDITO_LIMPO
VEREDITO_COM_BLOQUEANTE: str = a.VEREDITO_COM_BLOQUEANTE

STATUS_PENDENTE: str = "pendente"
STATUS_EM_ANDAMENTO: str = "em_andamento"
STATUS_CONCLUIDO: str = "concluido"
STATUS_BLOQUEADO: str = "bloqueado"


@dataclass(frozen=True)
class ConfiguracaoDoGoal:
    """O que o laço precisa saber de onde e como trabalhar, gravado no Goal na primeira chamada."""

    modo: str
    repositorio: str
    area: str
    ramo: str
    base: str
    slug: str
    orcamento_usd: float

    def em_json(self) -> dict[str, Any]:
        """A configuração como propriedade do Goal."""
        return asdict(self)

    @classmethod
    def de_json(cls, dados: Mapping[str, Any]) -> "ConfiguracaoDoGoal":
        """A configuração lida do Goal."""
        return cls(
            modo=str(dados["modo"]), repositorio=str(dados["repositorio"]), area=str(dados["area"]),
            ramo=str(dados["ramo"]), base=str(dados["base"]), slug=str(dados["slug"]),
            orcamento_usd=float(dados["orcamento_usd"]),
        )


def slug_de(texto: str) -> str:
    """Identificador estável, minúsculo, sem acento nem espaço."""
    return gerar_slug(texto)


def id_do_goal(slug: str) -> str:
    """O Goal que o orquestrador cria a partir de uma spec."""
    return f"goal-{slug}"


def id_do_projeto(slug_do_repositorio: str) -> str:
    """O Projeto dos Goals orquestrados de um repositório."""
    return f"orq-{slug_do_repositorio}"


def id_do_setor(slug_do_repositorio: str) -> str:
    """O Setor dos Goals orquestrados de um repositório."""
    return f"orq-{slug_do_repositorio}-goals"


def id_da_sessao(id_goal: str) -> str:
    """A Sessao do orquestrador que produz o que ele grava do Goal (o contrato do papel a reconhece por este nome)."""
    return sessao_do_goal(id_goal)


def id_do_criterio(slug: str, codigo: str) -> str:
    """O Criterio de um critério de aceite criado pelo plano (na fase 1, uma Constraint com o mesmo id)."""
    return f"crit-{slug}-{codigo.lower()}"


def id_da_decisao(slug: str, codigo: str) -> str:
    """A Decision de uma decisão registrada pelo plano."""
    return f"dec-{slug}-{codigo.lower()}"


def id_do_aceite(id_goal: str) -> str:
    """O que o trailer `Graphow-Task` do commit dos testes de aceite diz, e o sufixo do Artifact dele."""
    return f"aceite-{id_goal}"


def id_da_verificacao(id_goal: str, numero: int) -> str:
    """A Evidence da verificação de número dado do Goal."""
    return f"ver-{id_goal}-{numero}"


def id_do_achado(id_goal: str, numero: int, indice: int) -> str:
    """O Achado de índice dado da verificação de número dado."""
    return f"achado-{id_goal}-v{numero}-{indice}"


def id_da_fatia(slug: str, codigo: str) -> str:
    """A Task de uma fatia do plano ou de uma correção."""
    return f"task-{slug}-{codigo.lower().replace('.', '-')}"
