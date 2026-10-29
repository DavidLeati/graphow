"""Recusar o plano: o humano recusa, com o motivo, e o planejador o refaz com o recusado e o motivo no briefing.

O portão do modo supervisionado só tinha `aprovar`. Com `--recusar-plano
--motivo`, antes de qualquer fatia rodar, o laço retira o plano recusado: os
testes de aceite dele saem da área num commit, o plano, o aceite e as
propostas saem do Goal, as Tasks dele ficam no grafo marcadas como
substituídas (fora do plano), e o plano recusado vai, com o motivo, para
`planos_recusados`. O passo seguinte é planejar de novo: o planejador lê no
briefing o que foi recusado e por quê. As Tasks do plano novo nascem com a
versão no id, e os testes de aceite dele, com outro trailer.

O critério que o plano novo não traz mais fica no grafo (o Criterio não se
remove), marcado `retirado` pela Decision do humano que recusou o plano: o
fechamento não o cobra.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core import aceite as a
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, Parada
from graphow.orquestrador.git_do_goal import mensagem_do_orquestrador
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.livro_razao import propriedade
from graphow.orquestrador.pedidos_do_humano import PedidoDoHumano
from graphow.orquestrador.saida_do_aceite import PASTA_DO_ACEITE

PROPRIEDADES_DO_PLANO_VELHO: tuple[str, ...] = (m.CAMPO_PLANO, m.CAMPO_PLANO_PROPOSTO, m.CAMPO_ACEITE, m.CAMPO_ACEITE_PROPOSTO)


def replanejar(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None:
    """Retira o plano recusado (e os testes de aceite dele) e deixa o Goal pronto para o planejador de novo."""
    if estado.aceite is not None and (contexto.area / PASTA_DO_ACEITE).is_dir():
        contexto.git.rodar("rm", "-r", "-q", "--", PASTA_DO_ACEITE)
        assunto = f"Retira os testes de aceite do plano recusado do Goal {contexto.configuracao.slug}"
        contexto.commitar(mensagem_do_orquestrador(assunto, f"O humano recusou o plano: {pedido.motivo}", id_goal=contexto.id_goal),
                          caminhos=(PASTA_DO_ACEITE,))
    contexto.livro.gravar(_operacoes_da_recusa(estado, pedido), f"Plano do Goal {contexto.id_goal} recusado pelo humano ({pedido.id})")
    return None


def _operacoes_da_recusa(estado: EstadoDoGoal, pedido: PedidoDoHumano) -> list[ItemPatch]:
    """O plano velho fora do Goal e na lista dos recusados, as Tasks dele substituídas e o pedido atendido."""
    recusados = estado.propriedades.get(a.CAMPO_PLANOS_RECUSADOS)
    anteriores = [dict(item) for item in recusados if isinstance(item, Mapping)] if isinstance(recusados, list) else []
    recusa = {"plano": dict(estado.plano or {}), "motivo": pedido.motivo, "pedido": pedido.id, "por": pedido.por}
    return [
        *(ItemPatch(OperacaoPatch.REMOVE, f"/nos/{estado.id_goal}/propriedades/{chave}")
          for chave in PROPRIEDADES_DO_PLANO_VELHO if chave in estado.propriedades),
        propriedade(estado.id_goal, a.CAMPO_PLANOS_RECUSADOS, [*anteriores, recusa]),
        propriedade(estado.id_goal, a.CAMPO_PEDIDOS_ATENDIDOS, atendidos_com(estado, pedido.id)),
        *(propriedade(fatia.id, m.CAMPO_SUBSTITUIDA, pedido.id) for fatia in estado.fatias),
    ]


def atendidos_com(estado: EstadoDoGoal, id_pedido: str) -> list[str]:
    """Os pedidos atendidos do Goal, mais o dado."""
    atendidos = estado.propriedades.get(a.CAMPO_PEDIDOS_ATENDIDOS)
    return [*(str(item) for item in atendidos if str(item) != id_pedido), id_pedido] if isinstance(atendidos, list) else [id_pedido]


def bloco_da_recusa(estado: EstadoDoGoal) -> str:
    """No briefing do planejador, o último plano recusado e o motivo do humano; vazio sem recusa."""
    recusados = estado.propriedades.get(a.CAMPO_PLANOS_RECUSADOS)
    if not isinstance(recusados, list) or not recusados or not isinstance(recusados[-1], Mapping):
        return ""
    ultimo: Mapping[str, Any] = recusados[-1]
    plano = ultimo.get("plano") if isinstance(ultimo.get("plano"), Mapping) else {}
    fatias = [f"- {item}" for item in plano.get("fatias", [])]
    criterios = [f"- {c.get('id')}: {c.get('texto')}" for c in plano.get("criterios", []) if isinstance(c, Mapping)]
    return "\n".join([
        "## O humano recusou o plano anterior",
        f"Motivo do humano: {ultimo.get('motivo', '')}",
        f"Plano recusado: {plano.get('titulo', '')}. Criterios:", *criterios, "Fatias:", *fatias,
        "Refaca o plano levando o motivo em conta; nao repita o que ele recusou.",
    ])


def retirados_pela_recusa(estado: EstadoDoGoal, codigos_novos: Sequence[str]) -> dict[str, dict[str, str]]:
    """O Criterio dos planos recusados que o plano novo não traz mais, com a Decision do humano que o retirou."""
    recusados = estado.propriedades.get(a.CAMPO_PLANOS_RECUSADOS)
    if not isinstance(recusados, list) or not recusados or not isinstance(recusados[-1], Mapping):
        return {}
    ultimo = recusados[-1]
    plano = ultimo.get("plano") if isinstance(ultimo.get("plano"), Mapping) else {}
    return {str(c.get("no")): {"decisao": str(ultimo.get("pedido", "")), "motivo": str(ultimo.get("motivo", ""))}
            for c in plano.get("criterios", []) if isinstance(c, Mapping) and c.get("no") and c.get("id") not in codigos_novos}
