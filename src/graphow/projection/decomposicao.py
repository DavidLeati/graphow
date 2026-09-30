"""As tarefas de um Goal: todas as Tasks abaixo dele pela decomposição, em qualquer profundidade.

A medição da orquestração percorria a decomposição por conta própria, e a
conferência de colisões com o ramo base precisa das mesmas tarefas. As duas
leem daqui, para uma não achar tarefa onde a outra não acha.
"""

from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def tarefas_da_decomposicao(view: GrafoView, id_raiz: str) -> tuple[NoGrafo, ...]:
    """Todas as Tasks abaixo do nó por `decompoe`, correções incluídas, em ordem de identificador.

    Um nó que não é Task interrompe a descida por ele, e um ciclo não repete
    tarefa.
    """
    encontradas: dict[str, NoGrafo] = {}
    fronteira = [id_raiz]
    while fronteira:
        filhos = [a.destino_id for id_no in fronteira for a in view.obter_arestas_saida(id_no, TipoAresta.DECOMPOE)]
        novas = (view.obter_no(id_no) for id_no in dict.fromkeys(filhos) if id_no not in encontradas)
        tarefas = [no for no in novas if no is not None and no.tipo == TipoNo.TASK]
        encontradas.update({no.id: no for no in tarefas})
        fronteira = [no.id for no in tarefas]
    return tuple(sorted(encontradas.values(), key=lambda no: no.id))
