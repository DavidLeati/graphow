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

from graphow.harness.ambiente_padrao import gerar_slug
from graphow.kernel.papel_do_orquestrador import CAMPO_APROVACAO_DO_PLANO as CAMPO_DA_APROVACAO

AUTOR_DO_ORQUESTRADOR: str = "graphow-orquestrar"

MODO_SUPERVISIONADO: str = "supervisionado"
MODO_AUTONOMO: str = "autonomo"
MODOS: tuple[str, ...] = (MODO_SUPERVISIONADO, MODO_AUTONOMO)

# No Goal.
CAMPO_SPEC: str = "spec"
CAMPO_ORQUESTRACAO: str = "orquestracao"
CAMPO_PLANO: str = "plano"
# A saída do planejador já conferida, gravada antes do commit do documento e do
# plano: a retomada a reaproveita em vez de pagar outra sessão.
CAMPO_PLANO_PROPOSTO: str = "plano_proposto"
CAMPO_CICLOS: str = "ciclos_de_correcao"
CAMPO_PENDENCIAS: str = "pendencias"
CAMPO_INTEGRADO_EM: str = "integrado_em"
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
CAMPO_MODELO: str = "modelo"
CAMPO_ORDEM: str = "ordem"
CAMPO_TENTATIVAS: str = "tentativas"
CAMPO_FALHAS: str = "falhas"
CAMPO_ULTIMO_ERRO: str = "ultimo_erro"
CAMPO_PATCH: str = "patch_da_tentativa"
CAMPO_PENDENCIA: str = "pendencia"
CAMPO_COMMIT: str = "commit"
# Na fatia de correção: a Evidence de verificação de onde ela nasceu. Nome próprio,
# e não o `corrige` do escopo governado: o laço não depende das regras dele.
CAMPO_CORRIGE: str = "corrige_verificacao"
CAMPO_CRITERIO_PRONTO: str = "criterio_pronto"

# Na Question e na Evidence.
CAMPO_PERGUNTA: str = "pergunta"
CAMPO_RESPOSTA: str = "resposta"
CAMPO_ABERTA_POR: str = "aberta_por"
CAMPO_VEREDITO: str = "veredito"
CAMPO_CICLO: str = "ciclo"
ACAO_DA_VERIFICACAO: str = "verificacao_do_goal"
ACAO_DA_TENTATIVA: str = "tentativa_que_falhou"

VEREDITO_LIMPO: str = "aprovado"
VEREDITO_COM_BLOQUEANTE: str = "rejeitado"

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
    """A Sessao do orquestrador que produz o que ele grava do Goal."""
    return f"orq-sessao-{id_goal}"


def id_do_criterio(slug: str, codigo: str) -> str:
    """A Constraint de um critério de aceite criado pelo plano."""
    return f"crit-{slug}-{codigo.lower()}"


def id_da_decisao(slug: str, codigo: str) -> str:
    """A Decision de uma decisão registrada pelo plano."""
    return f"dec-{slug}-{codigo.lower()}"


def id_da_fatia(slug: str, codigo: str) -> str:
    """A Task de uma fatia do plano ou de uma correção."""
    return f"task-{slug}-{codigo.lower().replace('.', '-')}"
