"""As decisões que valem para um trabalho: as que o orientam e as que orientam quem o contém.

Uma Decision diz por `orienta` a que Task ou Goal ela se aplica. Pela vizinhança
de dois saltos, a decisão pendurada no Goal não chegava à subtarefa, e a tarefa
de correção, que nasce decomposta da tarefa rejeitada, perdia as decisões da
original justamente na vista do revisor. As restrições já sobem a hierarquia;
aqui as decisões fazem o mesmo caminho. Para um Artifact, o trabalho é a Task de
onde ele deriva.

A vista listava também, numa seção "Perto Desta Tarefa, Sem Governa-la", as
decisões e evidências da mesma sessão que nada ligava ao alvo. Saiu na fase 2:
era contexto sem leitor, que a vista do agente carregava sem que governasse
nada, e o briefing do orquestrador traz por extenso o que governa a fatia.
"""

from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.context.secoes import PrioridadeRetencao, SecaoContexto
from graphow.context.substituicao import montar_secao_de_decisoes
from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

# As arestas que sobem do trabalho ao que o contém: a subtarefa ao pai, a Task ao Goal.
ARESTAS_DE_HERANCA: frozenset[TipoAresta] = frozenset({TipoAresta.DECOMPOE})

def montar_secao_das_decisoes_que_governam(alvo: NoGrafo, view: GrafoView, *, ordem: int) -> SecaoContexto:
    """As decisões que governam o alvo.

    Governar é estar ligado por `orienta` ao trabalho do alvo ou a quem o
    contém. Nascer na mesma sessão não é: a vista listava a decisão de uma
    tarefa irmã como se valesse para esta.
    """
    return montar_secao_de_decisoes(coletar_decisoes_que_orientam(alvo, view), view, (ordem, PrioridadeRetencao.DECISOES))


def coletar_decisoes_que_orientam(alvo: NoGrafo, view: GrafoView) -> tuple[NoGrafo, ...]:
    """As Decision ligadas por `orienta` ao trabalho do alvo ou a um ancestral dele, sem repetição."""
    explorador = ExploradorSubgrafo(view)
    trabalho = (alvo, *_tarefas_de_onde_deriva(alvo, view))
    alcancados = [
        ancestral
        for no in trabalho
        for ancestral in (no, *explorador.coletar_alcancaveis(_pedido_de_ancestrais(no.id)))
    ]
    decisoes = {
        decisao.id: decisao
        for no in alcancados
        for decisao in explorador.coletar_origens_diretas(no.id, TipoAresta.ORIENTA)
        if decisao.tipo == TipoNo.DECISION
    }
    return tuple(decisoes.values())


def _tarefas_de_onde_deriva(alvo: NoGrafo, view: GrafoView) -> tuple[NoGrafo, ...]:
    """As Tasks a que o alvo chega por `deriva_de`: é o trabalho de um Artifact ou de uma Evidence."""
    destinos = (view.obter_no(aresta.destino_id) for aresta in view.obter_arestas_saida(alvo.id, TipoAresta.DERIVA_DE))
    return tuple(no for no in destinos if no is not None and no.tipo == TipoNo.TASK)


def _pedido_de_ancestrais(id_no: str) -> PedidoExploracao:
    """Subir pela decomposição, sem limite prático de profundidade."""
    return PedidoExploracao(
        id_alvo=id_no,
        tipos_de_aresta=ARESTAS_DE_HERANCA,
        direcao=DirecaoTravessia.ENTRADA,
        saltos_maximos=32,
    )
