"""As decisões que valem para um trabalho: as que o orientam e as que orientam quem o contém.

Uma Decision diz por `orienta` a que Task ou Goal ela se aplica. Pela vizinhança
de dois saltos, a decisão pendurada no Goal não chegava à subtarefa, e a tarefa
de correção, que nasce decomposta da tarefa rejeitada, perdia as decisões da
original justamente na vista do revisor. As restrições já sobem a hierarquia;
aqui as decisões fazem o mesmo caminho. Para um Artifact, o trabalho é a Task de
onde ele deriva.
"""

from collections.abc import Iterable

from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.context.secoes import PrioridadeRetencao, SecaoContexto, montar_secao_de_nos
from graphow.context.substituicao import montar_secao_de_decisoes
from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

# As arestas que sobem do trabalho ao que o contém: a subtarefa ao pai, a Task ao Goal.
ARESTAS_DE_HERANCA: frozenset[TipoAresta] = frozenset({TipoAresta.DECOMPOE})

# O que está perto sem governar. Separado das decisões que valem, porque uma
# decisão de outra tarefa listada como "que governa" é pior do que nenhuma.
TITULO_DO_CONTEXTO: str = "Perto Desta Tarefa, Sem Governa-la (mesma sessao ou so relacionado)"


def montar_secoes_de_decisoes(
    alvo: NoGrafo,
    proximos: Iterable[NoGrafo],
    view: GrafoView,
    *,
    ordens: tuple[int, int],
) -> tuple[SecaoContexto, SecaoContexto]:
    """As decisões que governam o alvo e, noutra seção, o que só está perto dele.

    Governar é estar ligado por `orienta` ao trabalho do alvo ou a quem o
    contém. Nascer na mesma sessão não é: a vista listava a decisão de uma
    tarefa irmã como se valesse para esta, e o revisor, que não percorre a
    sessão, trabalhava com outro conjunto de decisões.
    """
    governam = coletar_decisoes_que_orientam(alvo, view)
    ids_que_governam = {no.id for no in governam}
    contexto = {no.id: no for no in proximos if no.id not in ids_que_governam and no.id != alvo.id}
    ordem_das_que_governam, ordem_do_contexto = ordens
    return (
        montar_secao_de_decisoes(governam, view, (ordem_das_que_governam, PrioridadeRetencao.DECISOES)),
        montar_secao_de_nos(TITULO_DO_CONTEXTO, tuple(contexto.values()), (ordem_do_contexto, PrioridadeRetencao.CONTEXTO)),
    )


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
