"""Quem fecha uma Task precisa de revisão aprovada: a regra do kernel, fora da política.

A política de governança escolhe quem faz cada gesto, mas a exigência de
veredito não é gesto: vale em todo preset. Uma proposta de papel não humano que
escreve `concluido` numa Task é recusada se o veredito efetivo da Task
(projection/revisao.py) não for `aprovado`: o vigente, ou a rejeição superada
por uma correção aprovada. O veredito é lido no estado depois do lote: a
Evidence de revisão aprovada criada no mesmo lote conta, e a que o lote
remove não conta.

Só conta o veredito de Evidence de papel que julga (revisor, humano ou árbitro,
pela proveniência do nó): o executor que cria a própria aprovação não fecha a
própria Task. O aceite pelo teto de correções (kernel/aceite_pelo_teto.py) é a
outra porta, e a Decision que o dá precisa ser de quem pode aceitar.

São isentos o humano, que é o dono do grafo, e as Tasks de manutenção de
memória que o próprio grafo abre sem revisor (condensar a sessão e consolidar
aprendizados): exigir revisão delas travaria a memória.
"""

from collections.abc import Iterator
from dataclasses import replace

from graphow.core.models import GrafoEstado, NoGrafo, OrdemNoLog, ProvenienciaNo
from graphow.core.orquestracao import ACOES_ABERTAS_PELO_GRAFO, CAMPO_ACAO, CAMPO_VEREDITO, VEREDITO_APROVADO
from graphow.core.types import PapelAutor, StatusTask, TipoNo
from graphow.kernel.aceite_pelo_teto import aceite_libera_o_fechamento
from graphow.kernel.estrutura_apos_lote import EstruturaAposLote
from graphow.kernel.matriz_papeis import papel_julga
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch
from graphow.projection.graph_view import GrafoView
from graphow.projection.revisao import veredito_efetivo

SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2
SEGMENTOS_DA_PROPRIEDADE: int = 4
CAMPO_STATUS: str = "status"


def tarefas_sem_veredito_aprovado(proposta: PropostaPatch, estrutura: EstruturaAposLote) -> tuple[str, ...]:
    """As Tasks que o lote conclui sem veredito efetivo `aprovado` nem aceite pelo teto.

    Vazio para o humano e para as Tasks isentas. Em ordem de aparição no lote.
    """
    if proposta.papel == PapelAutor.HUMANO:
        return ()
    view = GrafoView(_estado_do_julgamento(proposta, estrutura))
    concluidas = dict.fromkeys(_ids_que_o_lote_conclui(proposta))
    return tuple(
        id_task for id_task in concluidas
        if _exige_veredito(id_task, estrutura.depois) and not _liberada(view, id_task)
    )


def _liberada(view: GrafoView, id_task: str) -> bool:
    """A revisão aprovou, direto ou por uma correção aprovada, ou um aceite legítimo a liberou."""
    return veredito_efetivo(view, id_task) == VEREDITO_APROVADO or aceite_libera_o_fechamento(view, id_task)


def _ids_que_o_lote_conclui(proposta: PropostaPatch) -> Iterator[str]:
    """Os nós em que a operação escreve `status` igual a `concluido`, na propriedade ou no nó inteiro."""
    for item in proposta.operacoes:
        if item.op not in (OperacaoPatch.ADD, OperacaoPatch.REPLACE):
            continue
        segmentos = [seg for seg in item.path.split("/") if seg]
        if segmentos and segmentos[0] == "nos" and _escreve_concluido(item, segmentos):
            yield segmentos[1]


def _escreve_concluido(item: ItemPatch, segmentos: list[str]) -> bool:
    """A operação grava `concluido` no status: na propriedade isolada, nas propriedades ou no nó inteiro."""
    if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE:
        return segmentos[2:] == ["propriedades", CAMPO_STATUS] and item.value == StatusTask.CONCLUIDO.value
    if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO:
        return _status_dentro(item.value.get("propriedades")) if isinstance(item.value, dict) else False
    if segmentos[2:] == ["propriedades"]:
        return _status_dentro(item.value)
    return False


def _status_dentro(propriedades: object) -> bool:
    """O mapa de propriedades traz o status `concluido`."""
    return isinstance(propriedades, dict) and propriedades.get(CAMPO_STATUS) == StatusTask.CONCLUIDO.value


def _exige_veredito(id_task: str, estado: GrafoEstado) -> bool:
    """O nó é uma Task que sobrevive ao lote e não é manutenção de memória aberta pelo grafo."""
    no = estado.nos.get(id_task)
    if no is None or no.tipo != TipoNo.TASK:
        return False
    return str(no.obter_propriedade(CAMPO_ACAO, "")) not in ACOES_ABERTAS_PELO_GRAFO


def _estado_do_julgamento(proposta: PropostaPatch, estrutura: EstruturaAposLote) -> GrafoEstado:
    """O estado depois do lote, preparado para ler o julgamento: criados por último, veredito só de quem julga.

    O nó da antevisão nasce sem posição no log nem proveniência. A posição
    decide o veredito mais recente: uma Evidence aprovada criada no lote
    perderia para uma rejeição antiga, e os criados passam a ocupar posições
    além da versão do log. A proveniência diz de que papel é cada nó: os
    criados no lote são do papel que propõe o lote. E o veredito de Evidence
    que não é de papel que julga não conta: sai do nó, e a Evidence deixa de
    ser um julgamento.
    """
    depois = estrutura.depois
    origem = ProvenienciaNo(autor=proposta.autor, papel=proposta.papel.value)
    posicoes = {id_no: posicao for posicao, id_no in enumerate(sorted(estrutura.criados), start=1)}
    nos: dict[str, NoGrafo] = {}
    for id_no, no in depois.nos.items():
        if id_no in posicoes:
            seq = depois.versao_log + posicoes[id_no]
            no = replace(no, proveniencia=origem, ordem=OrdemNoLog(seq_criacao=seq, seq_atualizacao=seq))
        nos[id_no] = _sem_veredito_de_quem_nao_julga(no)
    return GrafoEstado(nos=nos, arestas=depois.arestas, versao_log=depois.versao_log)


def _sem_veredito_de_quem_nao_julga(no: NoGrafo) -> NoGrafo:
    """A Evidence cuja proveniência não é de quem julga perde a propriedade `veredito`."""
    if no.tipo != TipoNo.EVIDENCE or CAMPO_VEREDITO not in no.propriedades or papel_julga(no.proveniencia.papel):
        return no
    return replace(no, propriedades={chave: valor for chave, valor in no.propriedades.items() if chave != CAMPO_VEREDITO})
