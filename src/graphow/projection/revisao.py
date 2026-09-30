"""A revisão de uma tarefa lida do grafo: os vereditos que ela recebeu e o que vigora entre eles.

O veredito do revisor é uma Evidence com a propriedade `veredito` que deriva do
Artifact entregue e da Task. A medição da orquestração contava esses vereditos
por conta própria, e a posse de tarefa passou a precisar do mesmo dado para
decidir se uma tarefa aprovada pode ser fechada por outro executor. As duas
pontas leem daqui, para uma não achar veredito onde a outra não acha.
"""

from collections.abc import Iterable

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import CAMPO_VEREDITO, ler_texto
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def artefatos_da_tarefa(view: GrafoView, id_task: str) -> frozenset[str]:
    """Os Artifacts que derivam da Task: o que o executor entregou para revisão."""
    return frozenset(
        aresta.origem_id
        for aresta in view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE)
        if _eh_do_tipo(view, aresta.origem_id, TipoNo.ARTIFACT)
    )


def vereditos_sobre(view: GrafoView, alvos: Iterable[str]) -> tuple[NoGrafo, ...]:
    """As Evidence com veredito que derivam de algum dos alvos, em ordem de identificador."""
    candidatas = {
        aresta.origem_id
        for id_alvo in alvos
        for aresta in view.obter_arestas_entrada(id_alvo, TipoAresta.DERIVA_DE)
    }
    nos = (view.obter_no(id_no) for id_no in sorted(candidatas))
    return tuple(no for no in nos if no is not None and no.tipo == TipoNo.EVIDENCE and ler_texto(no.propriedades, CAMPO_VEREDITO))


def veredito_vigente(view: GrafoView, id_task: str) -> str:
    """O veredito mais recente sobre a Task ou os Artifacts dela; vazio quando ninguém revisou.

    Uma tarefa pode ser reprovada e depois aprovada, ou o contrário, e só o
    último julgamento diz o que vale agora. Mais recente é a última escrita no
    nó pela ordem do log, não o relógio: o revisor que troca o veredito de uma
    Evidence existente também emite um julgamento novo.
    """
    vereditos = vereditos_sobre(view, {id_task} | artefatos_da_tarefa(view, id_task))
    if not vereditos:
        return ""
    ultimo = max(vereditos, key=lambda no: (no.ordem.seq_atualizacao, no.ordem.seq_criacao, no.id))
    return ler_texto(ultimo.propriedades, CAMPO_VEREDITO)


def _eh_do_tipo(view: GrafoView, id_no: str, tipo: TipoNo) -> bool:
    """O nó existe e é do tipo pedido."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == tipo
