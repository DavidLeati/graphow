"""A conferência dos pedidos do humano contra o Goal como ele está, antes de gravá-los.

O pedido que não vale não vira Decision: o Achado que não existe ou já se
encerrou não se descarta, o marco ganha ciclo só em número positivo, o Goal
fechado não se cancela, o plano que já começou a rodar não se recusa (o que
o humano tem então é cancelar) e só se refaz o aceite de um critério do plano.
"""

from collections.abc import Sequence
from dataclasses import replace

from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.pedidos_do_humano import (
    PEDIDO_CANCELAR,
    PEDIDO_DESCARTAR_ACHADO,
    PEDIDO_MAIS_CICLOS,
    PEDIDO_RECUSAR_PLANO,
    PEDIDO_REFAZER_ACEITE,
    PEDIDO_RETIRAR_CRITERIO,
    NovoPedido,
    PedidoRecusado,
    cancelamento,
    descarte,
)
from graphow.orquestrador.retirada_de_criterio import descartes_da_retirada, no_do_criterio
from graphow.projection.graph_view import GrafoView


def conferir_pedido(view: GrafoView, estado: EstadoDoGoal, pedido: NovoPedido) -> tuple[NovoPedido, Sequence[ItemPatch]]:
    """O pedido completo (o marco do `mais_ciclos`) e o que ele muda no mesmo lote; recusa o que não vale."""
    if estado.fechado or estado.cancelado:
        raise PedidoRecusado(f"o Goal {estado.id_goal} ja esta {estado.status}", {"acao": pedido.acao})
    if pedido.acao == PEDIDO_DESCARTAR_ACHADO:
        return pedido, descarte(view, pedido.alvo, pedido.motivo)
    if pedido.acao == PEDIDO_CANCELAR:
        return pedido, cancelamento(estado.id_goal, pedido.motivo)
    if estado.plano is None:
        raise PedidoRecusado("o Goal ainda nao tem plano", {"acao": pedido.acao})
    if pedido.acao == PEDIDO_MAIS_CICLOS:
        if pedido.ciclos < 1:
            raise PedidoRecusado("--mais-ciclos pede um numero de ciclos positivo", {"ciclos": pedido.ciclos})
        return replace(pedido, alvo=estado.marco_atual().id), ()
    if pedido.acao == PEDIDO_RECUSAR_PLANO:
        return pedido, _recusa_do_plano(estado)
    if pedido.acao == PEDIDO_REFAZER_ACEITE:
        return pedido, _refazer_o_aceite(estado, pedido.alvo)
    if pedido.acao == PEDIDO_RETIRAR_CRITERIO:
        return pedido, descartes_da_retirada(view, no_do_criterio(estado, pedido.alvo), pedido.motivo)
    raise PedidoRecusado(f"pedido desconhecido: {pedido.acao}", {"acao": pedido.acao})


def _recusa_do_plano(estado: EstadoDoGoal) -> Sequence[ItemPatch]:
    """O plano só se recusa antes de qualquer fatia rodar."""
    rodadas = [fatia.codigo for fatia in estado.fatias if fatia.tentativas]
    if rodadas:
        raise PedidoRecusado(f"as fatias {', '.join(rodadas)} ja rodaram: o plano nao se recusa mais; cancele o Goal com --cancelar",
                             {"fatias": rodadas})
    return ()


def _refazer_o_aceite(estado: EstadoDoGoal, criterio: str) -> Sequence[ItemPatch]:
    """Só se refaz o aceite de um critério do plano."""
    codigos = [str(item.get("id")) for item in (estado.plano or {}).get("criterios", [])]
    if criterio not in codigos:
        raise PedidoRecusado(f"{criterio or '(nenhum)'} nao e criterio do plano ({', '.join(codigos)})", {"criterio": criterio})
    return ()
