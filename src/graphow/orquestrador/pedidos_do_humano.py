"""Os pedidos do humano ao laço: cada saída que ele tem de um Goal parado, gravada como Decision dele.

O Goal travava sem saída: o bloqueante que o humano aceita não tinha como
sair do caminho, o marco sem ciclo não ganhava outro, o plano ou o teste de
aceite errado não tinha como ser refeito, e o humano não tinha como desistir.
Cada saída é agora um pedido gravado pelo humano, num nó Decision que nasce
dele (o kernel recusa o pedido gravado por outro papel e não deixa editá-lo
nem removê-lo), com o motivo obrigatório:

- `descartar_achado`: o Achado bloqueante sai do caminho no mesmo lote
  (aberto ou corrigido vira descartado, com o motivo do descarte);
- `mais_ciclos`: o marco em que o laço está ganha N ciclos de correção;
- `cancelar`: o Goal vira cancelado, com o motivo, e o laço não o conduz mais;
- `recusar_plano`: o planejador refaz o plano, com o recusado e o motivo no
  briefing (só antes de qualquer fatia rodar);
- `refazer_aceite`: o autor de aceite refaz os testes de um critério, com o
  motivo no briefing;
- `retirar_criterio`: o critério sai da conta do fechamento (o descarte de
  Achado não aprova critério: é a única saída para fechar com um critério
  reprovado), e os Achados abertos que só ele fere se descartam no mesmo lote.

A Decision é produzida pela Sessao do orquestrador do Goal (é por ela que o
pedido entra no laço), mas a proveniência é do humano. O laço lê o estado
(o Achado descartado, os ciclos dados) e atende os pedidos que pedem trabalho
(refazer o plano ou o aceite) uma vez, guardando no Goal os que já atendeu.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from graphow.core import aceite as a
from graphow.core.exceptions import GraphowError
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.papel_do_orquestrador import sessao_do_goal
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.graph_view import GrafoView

PEDIDO_DESCARTAR_ACHADO: str = "descartar_achado"
PEDIDO_MAIS_CICLOS: str = "mais_ciclos"
PEDIDO_CANCELAR: str = "cancelar"
PEDIDO_RECUSAR_PLANO: str = "recusar_plano"
PEDIDO_REFAZER_ACEITE: str = "refazer_aceite"
PEDIDO_RETIRAR_CRITERIO: str = "retirar_criterio"
PEDIDOS: frozenset[str] = frozenset({PEDIDO_DESCARTAR_ACHADO, PEDIDO_MAIS_CICLOS, PEDIDO_CANCELAR, PEDIDO_RECUSAR_PLANO,
                                     PEDIDO_REFAZER_ACEITE, PEDIDO_RETIRAR_CRITERIO})
ESTADOS_QUE_SE_DESCARTAM: frozenset[str] = frozenset({a.ESTADO_ABERTO, a.ESTADO_CORRIGIDO, a.ESTADO_DO_ACOMPANHAMENTO})


class PedidoRecusado(GraphowError):
    """O pedido do humano não vale para o Goal como ele está, ou o kernel o recusou."""


@dataclass(frozen=True)
class PedidoDoHumano:
    """Um pedido gravado: o que o humano pediu, por quê, sobre o quê e quem pediu."""

    id: str
    acao: str
    motivo: str
    alvo: str = ""
    ciclos: int = 0
    por: str = ""


def ler_pedidos(view: GrafoView, id_goal: str) -> tuple[PedidoDoHumano, ...]:
    """Os pedidos do humano sobre o Goal, na ordem do log."""
    produzidos = (view.obter_no(aresta.destino_id) for aresta in view.obter_arestas_saida(sessao_do_goal(id_goal), TipoAresta.PRODUZ))
    pedidos = sorted((no for no in produzidos if no is not None and _e_pedido(no, id_goal)), key=lambda no: (no.ordem.seq_criacao, no.id))
    return tuple(_pedido(no) for no in pedidos)


def _e_pedido(no: NoGrafo, id_goal: str) -> bool:
    """O nó é uma Decision de pedido do humano sobre o Goal, gravada pelo humano."""
    return (no.tipo == TipoNo.DECISION and no.obter_propriedade(a.CAMPO_ACAO_DO_HUMANO) in PEDIDOS
            and no.obter_propriedade("goal") == id_goal and no.proveniencia.papel == PapelAutor.HUMANO.value)


def _pedido(no: NoGrafo) -> PedidoDoHumano:
    """O pedido como o nó o guarda."""
    ciclos = no.obter_propriedade("ciclos")
    return PedidoDoHumano(
        id=no.id, acao=str(no.obter_propriedade(a.CAMPO_ACAO_DO_HUMANO)), motivo=str(no.obter_propriedade("motivo") or ""),
        alvo=str(no.obter_propriedade("alvo") or ""), ciclos=ciclos if isinstance(ciclos, int) and not isinstance(ciclos, bool) else 0,
        por=no.proveniencia.autor,
    )


@dataclass(frozen=True)
class NovoPedido:
    """O que o humano pede pela CLI."""

    acao: str
    motivo: str
    por: str
    alvo: str = ""
    ciclos: int = 0


def gravar_pedido(kernel: WriteKernel, id_goal: str, pedido: NovoPedido, *, extra: Sequence[ItemPatch] = ()) -> str:
    """Grava a Decision do pedido, com o que ele muda no mesmo lote, como o humano; devolve o id dela."""
    if not pedido.motivo.strip():
        raise PedidoRecusado("o pedido do humano pede --motivo", {"acao": pedido.acao})
    view = kernel.obter_view()
    id_no = f"pedido-{id_goal}-{len(ler_pedidos(view, id_goal)) + 1}"
    propriedades = {a.CAMPO_ACAO_DO_HUMANO: pedido.acao, "goal": id_goal, "motivo": pedido.motivo.strip(), "alvo": pedido.alvo,
                    "ciclos": pedido.ciclos, "texto": f"O humano pede {pedido.acao.replace('_', ' ')}" + (f" ({pedido.alvo})" if pedido.alvo else "")}
    id_aresta = f"produz-{sessao_do_goal(id_goal)}-{id_no}"
    operacoes = (
        ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", {"id": id_no, "tipo": TipoNo.DECISION.value, "rotulo": propriedades["texto"],
                                                        "propriedades": propriedades}),
        ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}", {"id": id_aresta, "origem_id": sessao_do_goal(id_goal),
                                                                "destino_id": id_no, "tipo": TipoAresta.PRODUZ.value}),
        *extra,
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor=pedido.por, papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa=f"Pedido do humano no Goal {id_goal}: {pedido.acao}")))
    if not recibo.sucesso:
        raise PedidoRecusado("o kernel recusou o pedido", {"acao": pedido.acao, "motivo": recibo.mensagem})
    return id_no


def escrita(id_no: str, chave: str, valor: object) -> ItemPatch:
    """A escrita de uma propriedade de um nó, no lote do pedido."""
    return ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_no}/propriedades/{chave}", valor)


def descarte(view: GrafoView, id_achado: str, motivo: str) -> list[ItemPatch]:
    """O que o descarte muda no Achado; recusa o que não é Achado, ou o que já está encerrado."""
    no = view.obter_no(id_achado)
    if no is None or no.tipo != TipoNo.ACHADO:
        raise PedidoRecusado(f"'{id_achado}' nao e um Achado", {"achado": id_achado})
    if no.obter_propriedade(a.CAMPO_ESTADO) not in ESTADOS_QUE_SE_DESCARTAM:
        raise PedidoRecusado(f"o Achado '{id_achado}' ja esta {no.obter_propriedade(a.CAMPO_ESTADO)}", {"achado": id_achado})
    return [escrita(id_achado, a.CAMPO_ESTADO, a.ESTADO_DESCARTADO), escrita(id_achado, a.CAMPO_MOTIVO_DO_DESCARTE, motivo.strip())]


def cancelamento(id_goal: str, motivo: str) -> list[ItemPatch]:
    """O que o cancelamento muda no Goal."""
    return [escrita(id_goal, a.CAMPO_STATUS, a.STATUS_CANCELADO), escrita(id_goal, a.CAMPO_MOTIVO_DO_CANCELAMENTO, motivo.strip())]
