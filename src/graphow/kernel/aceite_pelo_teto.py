"""O aceite pelo teto de correções, que libera o fechamento sem veredito aprovado.

Depois da segunda reprovação, quando nenhum critério não atendido é bloqueante,
o condutor aceita a entrega com uma Decision de ação `aceite_apos_reprovacao`.
O kernel não deixa o executor se declarar aceito nem deixa o aceite virar um
veredito falso do revisor: a Decision precisa orientar a Task, ter sido criada
por quem pode aceitar (planejador, humano ou árbitro, pela proveniência do nó)
e ser justificada pela Evidence do veredito vigente da Task, o julgamento que
ela aceita.
"""

from graphow.core.orquestracao import ACAO_ACEITE_APOS_REPROVACAO, CAMPO_ACAO, ler_texto
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import papel_aceita_a_entrega
from graphow.projection.graph_view import GrafoView
from graphow.projection.revisao import evidencia_do_veredito_vigente


def aceite_libera_o_fechamento(view: GrafoView, id_task: str) -> bool:
    """Alguma Decision de aceite legítima orienta a Task e justifica-se pelo veredito vigente dela."""
    julgamento = evidencia_do_veredito_vigente(view, id_task)
    if julgamento is None:
        return False
    return any(
        _eh_aceite_legitimo(view, aresta.origem_id) and _justificada_por(view, aresta.origem_id, julgamento.id)
        for aresta in view.obter_arestas_entrada(id_task, TipoAresta.ORIENTA)
    )


def _eh_aceite_legitimo(view: GrafoView, id_decisao: str) -> bool:
    """O nó é uma Decision de aceite pelo teto, criada por papel que pode aceitar."""
    no = view.obter_no(id_decisao)
    if no is None or no.tipo != TipoNo.DECISION:
        return False
    return ler_texto(no.propriedades, CAMPO_ACAO) == ACAO_ACEITE_APOS_REPROVACAO and papel_aceita_a_entrega(no.proveniencia.papel)


def _justificada_por(view: GrafoView, id_decisao: str, id_veredito: str) -> bool:
    """A Evidence do veredito vigente tem aresta `justifica` para a Decision."""
    return any(aresta.origem_id == id_veredito for aresta in view.obter_arestas_entrada(id_decisao, TipoAresta.JUSTIFICA))
