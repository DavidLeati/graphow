"""A seção de propostas fora do Goal, só na vista do humano.

A proposta é a terceira saída da descoberta: o que não atende a critério nenhum
fica à espera de decisão, e quem decide é o humano. O planejador não a vê, para
ela não virar Task por osmose; por isso a seção mora numa política própria do
papel humano, e não nas seções universais. Cai cedo sob orçamento: é pendência
de quem decide, não o que o trabalho precisa para andar.
"""

from graphow.context.politicas import AmbienteDoRecorte, PoliticaPlanejador
from graphow.context.secoes import (
    MARCA_DE_CONTEUDO_NAO_CONFIAVEL,
    PrioridadeRetencao,
    SecaoContexto,
    em_uma_linha,
)
from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.projection.propostas import PropostaForaDoGoal, listar_propostas_abertas, propostas_do_goal

TITULO_DA_SECAO_DE_PROPOSTAS: str = "Propostas Fora Do Goal"
ORDEM_DE_EXIBICAO_DAS_PROPOSTAS: int = 8
TIPOS_COM_SECAO_DE_PROPOSTAS: frozenset[TipoNo] = frozenset({TipoNo.PROJETO, TipoNo.GOAL})


def montar_secao_de_propostas(alvo: NoGrafo, ambiente: AmbienteDoRecorte) -> SecaoContexto:
    """As propostas abertas do Projeto, ou as que nasceram de uma Task do Goal; vazia para outro alvo."""
    propostas = _propostas_do_alvo(alvo, ambiente)
    return SecaoContexto(
        titulo=TITULO_DA_SECAO_DE_PROPOSTAS,
        linhas=tuple(_descrever(proposta) for proposta in propostas),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DAS_PROPOSTAS,
        prioridade_retencao=PrioridadeRetencao.CONTEXTO,
        ids_incluidos=tuple(proposta.id for proposta in propostas),
    )


class PoliticaHumano(PoliticaPlanejador):
    """Humano: lê como o planejador e, no Projeto e no Goal, vê também as propostas à espera dele."""

    def _secoes_do_papel(self, alvo: NoGrafo, ambiente: AmbienteDoRecorte) -> tuple[SecaoContexto, ...]:
        """As seções do planejador e, quando o alvo comporta, a das propostas fora do Goal."""
        secoes = super()._secoes_do_papel(alvo, ambiente)
        if alvo.tipo not in TIPOS_COM_SECAO_DE_PROPOSTAS:
            return secoes
        return (*secoes, montar_secao_de_propostas(alvo, ambiente))


def _propostas_do_alvo(alvo: NoGrafo, ambiente: AmbienteDoRecorte) -> tuple[PropostaForaDoGoal, ...]:
    """No Projeto, todas as abertas dele; no Goal, as que partem do trabalho dele."""
    if alvo.tipo == TipoNo.PROJETO:
        return listar_propostas_abertas(ambiente.view, alvo.id)
    if alvo.tipo == TipoNo.GOAL:
        return propostas_do_goal(ambiente.view, alvo.id)
    return ()


def _descrever(proposta: PropostaForaDoGoal) -> str:
    """Uma linha: id, o texto, a origem e a sessão, com a marca de conteúdo de agente."""
    marca = f" {MARCA_DE_CONTEUDO_NAO_CONFIAVEL}" if proposta.papel not in ("", "humano") else ""
    origem = f" origem: {', '.join(em_uma_linha(item) for item in proposta.origens)};" if proposta.origens else ""
    sessao = f" sessao: {em_uma_linha(proposta.sessao_id)}" if proposta.sessao_id else ""
    detalhe = f" ({(origem + sessao).strip().rstrip(';')})" if origem or sessao else ""
    log = f" (log #{proposta.seq_criacao})" if proposta.seq_criacao > 0 else ""
    return f"- [{em_uma_linha(proposta.id)}]{marca} {em_uma_linha(proposta.rotulo)}{detalhe}{log}"
