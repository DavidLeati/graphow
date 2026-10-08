"""As propostas fora do Goal que o agente deixou para o humano decidir.

Uma descoberta que não atende a nenhum critério de aceite não vira Task: vira uma
Note `acao: proposta_fora_do_goal`, e o humano a fecha mudando o `status` para
`aceita` ou `descartada`. Esta projeção lê as que seguem abertas, com o Projeto
ancestral, a origem (`deriva_de`, ou a propriedade `origens` quando quem propõe é o planejador, que não é dono da aresta) e a sessão que a produziu. Nunca entra na fila
do condutor nem na vista do planejador.

O Projeto sai do rastreio do kernel, o mesmo que decide a política de governança:
uma busca própria por arestas de entrada poderia achar outro Projeto.
"""

from dataclasses import dataclass

from graphow.core.escopo import ACAO_PROPOSTA_FORA_DO_GOAL
from graphow.core.models import NoGrafo
from graphow.core.orquestracao import CAMPO_ACAO, ler_texto, ler_textos
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.projection.graph_view import GrafoView

CAMPO_STATUS_DA_PROPOSTA: str = "status"
# O planejador não é dono de `deriva_de`: o achado de onde a proposta saiu vai também nesta propriedade.
CAMPO_ORIGENS_DA_PROPOSTA: str = "origens"
STATUS_PROPOSTA_ABERTA: str = "aberta"
STATUS_PROPOSTA_ACEITA: str = "aceita"
STATUS_PROPOSTA_DESCARTADA: str = "descartada"
STATUS_DE_DECISAO_DO_HUMANO: frozenset[str] = frozenset({STATUS_PROPOSTA_ACEITA, STATUS_PROPOSTA_DESCARTADA})

ARESTAS_DE_DESCIDA_DO_GOAL: frozenset[TipoAresta] = frozenset({TipoAresta.DECOMPOE, TipoAresta.PRODUZ})
SALTOS_DA_ORIGEM_ATE_A_TASK: int = 3


@dataclass(frozen=True)
class PropostaForaDoGoal:
    """Uma proposta aberta: o que se propõe, de onde veio e em que Projeto está."""

    id: str
    rotulo: str
    status: str
    projeto_id: str | None
    origens: tuple[str, ...]
    sessao_id: str | None
    seq_criacao: int
    autor: str
    papel: str


def eh_proposta_fora_do_goal(no: NoGrafo) -> bool:
    """A Note marcada como proposta fora do Goal, qualquer que seja o status."""
    return no.tipo == TipoNo.NOTE and ler_texto(no.propriedades, CAMPO_ACAO) == ACAO_PROPOSTA_FORA_DO_GOAL


def status_da_proposta(no: NoGrafo) -> str:
    """O status da proposta; ausente conta como aberta."""
    return ler_texto(no.propriedades, CAMPO_STATUS_DA_PROPOSTA) or STATUS_PROPOSTA_ABERTA


def listar_propostas_abertas(view: GrafoView, id_projeto: str | None = None) -> tuple[PropostaForaDoGoal, ...]:
    """As propostas abertas na ordem do log, só as do Projeto quando ele é dado."""
    rastreador = RastreadorProjetoAncestral()
    propostas = (
        _descrever(no, view, rastreador.rastrear(no.id, view.estado))
        for no in sorted(view.listar_nos_por_tipo(TipoNo.NOTE), key=lambda no: (no.ordem.seq_criacao, no.id))
        if eh_proposta_fora_do_goal(no) and status_da_proposta(no) == STATUS_PROPOSTA_ABERTA
    )
    return tuple(proposta for proposta in propostas if id_projeto is None or proposta.projeto_id == id_projeto)


def propostas_do_goal(view: GrafoView, id_goal: str) -> tuple[PropostaForaDoGoal, ...]:
    """As abertas cuja origem é uma Task do Goal ou deriva de uma; sem origem, ficam só no Projeto."""
    tarefas = _tarefas_do_goal(view, id_goal)
    return tuple(
        proposta
        for proposta in listar_propostas_abertas(view)
        if any(_origem_chega_a(view, origem, tarefas) for origem in proposta.origens)
    )


def _descrever(no: NoGrafo, view: GrafoView, projeto_id: str | None) -> PropostaForaDoGoal:
    """Monta a proposta com a origem e a sessão lidas das arestas do próprio nó."""
    sessoes = [aresta.origem_id for aresta in view.obter_arestas_entrada(no.id, TipoAresta.PRODUZ)]
    origens = {aresta.destino_id for aresta in view.obter_arestas_saida(no.id, TipoAresta.DERIVA_DE)}
    origens.update(ler_textos(no.propriedades.get(CAMPO_ORIGENS_DA_PROPOSTA)))
    return PropostaForaDoGoal(
        id=no.id,
        rotulo=no.rotulo,
        status=status_da_proposta(no),
        projeto_id=projeto_id,
        origens=tuple(sorted(origens)),
        sessao_id=min(sessoes) if sessoes else None,
        seq_criacao=no.ordem.seq_criacao,
        autor=no.proveniencia.autor,
        papel=no.proveniencia.papel,
    )


def _tarefas_do_goal(view: GrafoView, id_goal: str) -> frozenset[str]:
    """As Tasks alcançáveis do Goal por `decompoe` e `produz`, resistente a ciclos."""
    vistos: set[str] = set()
    fronteira = [id_goal]
    while fronteira:
        novos = [id_no for id_no in _filhos_de_hierarquia(view, fronteira.pop()) if id_no not in vistos]
        vistos.update(novos)
        fronteira.extend(novos)
    return frozenset(vistos)


def _filhos_de_hierarquia(view: GrafoView, id_no: str) -> tuple[str, ...]:
    """Os destinos das arestas de descida (`decompoe`, `produz`) que saem do nó."""
    return tuple(
        aresta.destino_id for aresta in view.obter_arestas_saida(id_no) if aresta.tipo in ARESTAS_DE_DESCIDA_DO_GOAL
    )


def _origem_chega_a(view: GrafoView, origem: str, tarefas: frozenset[str]) -> bool:
    """A origem é uma das Tasks ou chega a uma por `deriva_de`, em poucos saltos."""
    fronteira = {origem}
    for _ in range(SALTOS_DA_ORIGEM_ATE_A_TASK):
        if fronteira & tarefas:
            return True
        fronteira = {
            aresta.destino_id
            for id_no in fronteira
            for aresta in view.obter_arestas_saida(id_no, TipoAresta.DERIVA_DE)
        }
    return bool(fronteira & tarefas)
