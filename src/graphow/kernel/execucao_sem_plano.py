"""O executor não assume a Task de um Goal que ainda não tem plano aprovado (D3 do escopo governado).

Sem plano aprovado não há referência para o desvio: tudo o que o executor
fizesse contaria como emergente. O gesto que destrava é o `aprovar_plano`, do
humano ou, se a política lhe entrega, do árbitro; qualquer versão serve, só a do
humano vira referência. A Task sem Goal acima dela por `decompoe` fica livre, e
o humano nunca passa por aqui (o RoleGate nem o avalia).

Os portões só rodam na submissão: o replay do log não passa por eles. Por isso
esta regra vale para os eventos gravados a partir da ontologia 1.5.0 (seção 6.1
da proposta), e um log antigo, com executor em andamento sob Goal sem plano,
reproduz sem erro.
"""

from collections.abc import Sequence

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, StatusTask, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, ResultadoValidacao
from graphow.kernel.permissao_de_aresta import ContextoPapel
from graphow.projection.escopo_plano import goal_da_task, plano_vigente
from graphow.projection.graph_view import GrafoView

SEGMENTOS_DO_STATUS: int = 4
CHAVE_DO_STATUS: str = "status"


def validar_plano_para_assumir(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao:
    """Recusa o executor que põe em andamento a Task de um Goal sem plano aprovado."""
    if contexto.proposta.papel != PapelAutor.EXECUTOR or not _vai_para_em_andamento(segmentos, item):
        return ResultadoValidacao.sucesso()
    view = GrafoView(contexto.estado_com_lote)
    no = view.obter_no(segmentos[1])
    if no is None or no.tipo != TipoNo.TASK:
        return ResultadoValidacao.sucesso()
    id_goal = goal_da_task(view, no.id)
    if id_goal is None or plano_vigente(view, id_goal) is not None:
        return ResultadoValidacao.sucesso()
    return ResultadoValidacao.falha(
        f"Papel 'executor' nao pode assumir a Task '{no.id}': o Goal {id_goal} não tem plano aprovado; "
        "um aprovar_plano (humano, ou árbitro se a política entregar) o destrava. "
        "Devolva a tarefa e peça a aprovação ao humano com 'abrir_questao'",
        "RoleGate",
        {"id_task": no.id, "id_goal": id_goal},
        modo=ModoFalhaMAST.PLANO_NAO_APROVADO,
    )


def _vai_para_em_andamento(segmentos: Sequence[str], item: ItemPatch) -> bool:
    """A operação escreve `status = em_andamento` numa propriedade de nó."""
    if len(segmentos) != SEGMENTOS_DO_STATUS or tuple(segmentos[2:]) != ("propriedades", CHAVE_DO_STATUS):
        return False
    return item.op != OperacaoPatch.REMOVE and str(item.value) == StatusTask.EM_ANDAMENTO.value

