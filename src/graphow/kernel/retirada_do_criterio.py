"""O Criterio sai da conta do fechamento só pelo pedido do humano que o retira: `retirar_criterio` dele, ou `recusar_plano` do Goal.

A retirada é a propriedade `retirado` do Criterio, que o orquestrador grava
quando atende o pedido, com o id da Decision do pedido. A revisão da rodada 3
mostrou que bastava citar qualquer Decision do humano (a que o gerente gravou
sobre o banco de dados, por exemplo) para o critério sair da conta. Aqui a
Decision citada tem de ser um pedido do humano ao laço, deste Goal, e: o
`retirar_criterio` com este critério como alvo, ou o `recusar_plano`, que
tira do plano o critério que o plano novo não traz.
"""

from collections.abc import Callable, Mapping

from graphow.core import aceite as a
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoNo

PEDIDOS_QUE_RETIRAM: frozenset[str] = frozenset({a.ACAO_RETIRAR_CRITERIO, a.ACAO_RECUSAR_PLANO})
CAMPO_DECISAO_DA_RETIRADA: str = "decisao"


def pedido_que_retira(decisao: NoGrafo | None, *, id_goal: str, codigo: str) -> bool:
    """A Decision é o pedido do humano que tira este critério da conta deste Goal."""
    if decisao is None or decisao.tipo != TipoNo.DECISION or decisao.proveniencia.papel != PapelAutor.HUMANO.value:
        return False
    propriedades = decisao.propriedades
    acao = propriedades.get(a.CAMPO_ACAO_DO_HUMANO)
    if acao not in PEDIDOS_QUE_RETIRAM or propriedades.get(a.CAMPO_GOAL_DO_PEDIDO) != id_goal:
        return False
    return acao == a.ACAO_RECUSAR_PLANO or propriedades.get(a.CAMPO_ALVO_DO_PEDIDO) == codigo


def retirada_valida(retirada: object, obter: Callable[[str], NoGrafo | None], *, id_goal: str, codigo: str) -> bool:
    """A retirada gravada cita o pedido do humano que tira este critério deste Goal."""
    if not isinstance(retirada, Mapping):
        return False
    return pedido_que_retira(obter(str(retirada.get(CAMPO_DECISAO_DA_RETIRADA, ""))), id_goal=id_goal, codigo=codigo)
