"""Retirar um critério: a única saída do humano para fechar o Goal com um critério que a verificação reprova.

Descartar Achado não aprova critério: o Goal com critério `nao_atende` ou
`parcial` na última verificação não fecha, descarte o humano o que
descartar. Para fechar assim, o humano retira o critério, com o motivo
(`--retirar-criterio C2 --motivo`): o pedido é uma Decision dele, e, no
mesmo lote, os Achados abertos que ferem só aquele critério se descartam com
o motivo da retirada. O laço atende o pedido gravando no `Criterio` que ele
foi `retirado` por aquela Decision (o kernel deixa de cobrá-lo), e o
documento do Goal ganha a seção dos critérios retirados; o `--status` também
os mostra.

O Goal só conclui com pelo menos um critério atendido (decisão do dono do
processo): fechá-lo com todos retirados integrava na base um código que nada
provou. A retirada do último critério leva o Goal a `cancelado`, no mesmo
lote, com o motivo, e o laço para sem integrar; o kernel recusa concluir o
Goal sem critério na conta e só deixa o orquestrador cancelar nesse caso.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, com_retirados, gravar_se_mudou
from graphow.orquestrador.git_do_goal import mensagem_do_orquestrador
from graphow.orquestrador.leitura_das_verificacoes import criterios_ativos, do_orquestrador
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.livro_razao import propriedade
from graphow.orquestrador.pedidos_do_humano import (
    ESTADOS_QUE_SE_DESCARTAM,
    PEDIDO_RETIRAR_CRITERIO,
    PedidoDoHumano,
    PedidoRecusado,
    descarte,
)
from graphow.orquestrador.replanejamento import atendidos_com
from graphow.projection.graph_view import GrafoView


def no_do_criterio(estado: EstadoDoGoal, codigo: str) -> str:
    """O nó do critério do plano, pelo código; recusa o código que não é do plano."""
    criterios = {str(c.get("id")): str(c.get("no", "")) for c in (estado.plano or {}).get("criterios", []) if isinstance(c, Mapping)}
    if codigo not in criterios or not criterios[codigo]:
        raise PedidoRecusado(f"{codigo or '(nenhum)'} nao e criterio do plano ({', '.join(criterios)})", {"criterio": codigo})
    return criterios[codigo]


def descartes_da_retirada(view: GrafoView, id_criterio: str, motivo: str) -> list[ItemPatch]:
    """Os Achados abertos do orquestrador que ferem só o critério retirado, descartados com o motivo da retirada."""
    feridores = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_criterio, TipoAresta.FERE))
    so_dele = [no for no in feridores if do_orquestrador(no) and no.tipo == TipoNo.ACHADO
               and no.obter_propriedade(a.CAMPO_ESTADO) in ESTADOS_QUE_SE_DESCARTAM
               and {aresta.destino_id for aresta in view.obter_arestas_saida(no.id, TipoAresta.FERE)} == {id_criterio}]
    return [operacao for no in so_dele for operacao in descarte(view, no.id, f"criterio retirado pelo humano: {motivo}")]


def retirar_criterio(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None:
    """Grava no Criterio a retirada pela Decision do humano e a mostra no documento do Goal."""
    id_no = no_do_criterio(estado, pedido.alvo)
    retirada = {"decisao": pedido.id, "motivo": pedido.motivo, "por": pedido.por, "codigo": pedido.alvo}
    todas = [*retirados(estado), retirada]
    ultimo = not (criterios_ativos(contexto.livro.view(), estado.id_goal) - {id_no})
    motivo = _motivo_do_cancelamento(todas)
    cancelamento = [propriedade(estado.id_goal, a.CAMPO_STATUS, a.STATUS_CANCELADO),
                    propriedade(estado.id_goal, a.CAMPO_MOTIVO_DO_CANCELAMENTO, motivo)] if ultimo else []
    contexto.livro.gravar([propriedade(id_no, a.CAMPO_RETIRADO, retirada),
                           propriedade(estado.id_goal, a.CAMPO_PEDIDOS_ATENDIDOS, atendidos_com(estado, pedido.id)), *cancelamento],
                          f"Criterio {pedido.alvo} do Goal {estado.id_goal} retirado pelo humano ({pedido.id})")
    _documentar(contexto, todas)
    if not ultimo:
        return None
    return Parada(contexto.id_goal, MotivoDaParada.CANCELADO, f"O Goal {estado.id_goal} foi cancelado, sem integrar: {motivo}.")


def _motivo_do_cancelamento(retiradas: Sequence[Mapping[str, Any]]) -> str:
    """Por que o Goal sem critério na conta vai a cancelado, com os critérios e os pedidos que os retiraram."""
    lista = ", ".join(f"{r['codigo']} ({r['decisao']})" for r in retiradas)
    return f"todos os criterios foram retirados pelo humano ({lista}); sem criterio atendido o Goal nao conclui nem integra"


def retirados(estado: EstadoDoGoal) -> list[Mapping[str, Any]]:
    """As retiradas que o laço já gravou, pela ordem dos pedidos atendidos."""
    atendidos = estado.propriedades.get(a.CAMPO_PEDIDOS_ATENDIDOS)
    feitos = set(atendidos) if isinstance(atendidos, list) else set()
    return [{"decisao": p.id, "motivo": p.motivo, "por": p.por, "codigo": p.alvo} for p in estado.pedidos
            if p.acao == PEDIDO_RETIRAR_CRITERIO and p.id in feitos]


def _documentar(contexto: ContextoDoGoal, retiradas: Sequence[Mapping[str, Any]]) -> None:
    """A seção dos critérios retirados no documento do Goal, commitada se mudou: só o documento, pelo caminho."""
    documento = caminho_do_documento(contexto.configuracao.slug)
    caminho = contexto.area / documento
    if not caminho.is_file():
        return
    linhas = [f"- **{r['codigo']}**, retirado por {r['por']} ({r['decisao']}): {r['motivo']}" for r in retiradas]
    if gravar_se_mudou(caminho, com_retirados(caminho.read_text(encoding="utf-8"), linhas)) and contexto.git.mudancas(documento):
        assunto = f"Registra os criterios retirados pelo humano do Goal {contexto.configuracao.slug}"
        contexto.commitar(mensagem_do_orquestrador(assunto, "", id_goal=contexto.id_goal), caminhos=(documento,))
