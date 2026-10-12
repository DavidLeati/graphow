"""O Goal só fecha com a prova: a verificação final limpa no commit atual, todo critério atendido e nenhum bloqueante aberto.

Na fase 1 a regra morava só no orquestrador: o laço não fechava sem a
verificação limpa, mas o livro-razão aceitava qualquer lote que pusesse o Goal
em `concluido`. Aqui ela é do kernel e vale para todo papel, o humano
inclusive, sobre o estado depois do lote. O Goal que o lote conclui, quando é
conduzido pelo orquestrador (`orquestracao`) ou tem `Criterio` ligado, precisa:

- de uma verificação (Evidence `verificacao_do_goal` que deriva do Goal) como a
  última, pela ordem do log, e que seja a final, sobre o Goal inteiro;
- de que ela seja limpa: veredito `aprovado`, ou todo Achado bloqueante dela
  encerrado (resolvido, ou descartado pelo humano);
- de que ela tenha sido feita no commit do código que é a ponta da branch do
  Goal (`ponta_do_ramo`, que o orquestrador grava do git a cada commit; o
  commit que só muda o documento do Goal não muda o commit do código);
- de parecer `atende` nela para cada critério do Goal (todo `Criterio` que o
  escopa e todo nó que o plano gravado lista como critério); descartar o Achado
  não aprova o critério: o único jeito de fechar sem ele é o humano retirá-lo,
  e o Criterio que uma Decision do humano retirou sai da conta;
- e de que nenhum `Achado` bloqueante do Goal (das verificações e das revisões
  de risco dele, ou que fere critério ou decisão dele) siga aberto ou só
  corrigido.

Quem pode escrever cada uma dessas coisas, e que nada delas se reescreve, é
outra regra (kernel/livro_do_aceite.py): é ela que impede de trocar a prova no
mesmo lote que fecha.
E a regra só conta a verificação, o Achado e a revisão de risco que nasceram
de um lote do orquestrador (a proveniência do nó no log): a Evidence que outro
papel gravou com a ação da verificação não é prova, nem que o livro a deixe
passar.

O Goal de antes do aceite no centro, sem condução nem `Criterio`, fecha como
fechava: a regra não o alcança.

A antevisão do lote (kernel/estrutura_apos_lote.py) aplica só as criações e as
remoções; aqui as escritas de propriedade do lote também entram, para que a
ponta, o estado do achado e a verificação gravados no mesmo lote que fecha
contem como contariam depois dele.
"""

from collections.abc import Iterator, Mapping
from dataclasses import replace
from typing import Any

from graphow.core import aceite as a
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.estrutura_apos_lote import EstruturaAposLote
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.projection.graph_view import GrafoView

PORTAO: str = "InvariantGate"
CAMPO_STATUS: str = "status"
SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2
SEGMENTOS_DA_PROPRIEDADE: int = 4
# A posição no log do nó que nasce no próprio lote: depois de todos os gravados.
SEQ_DO_LOTE: int = 2**62


def validar_fechamento_do_goal(proposta: PropostaPatch, estrutura: EstruturaAposLote) -> ResultadoValidacao:
    """Recusa o lote que conclui um Goal do aceite no centro sem a prova; aprova o resto."""
    view = GrafoView(_com_as_escritas_do_lote(proposta, estrutura.depois))
    for id_goal in dict.fromkeys(_goals_que_o_lote_conclui(proposta, estrutura.depois)):
        motivos = motivos_para_nao_fechar(view, id_goal)
        if motivos:
            return ResultadoValidacao.falha(
                f"Goal '{id_goal}' nao pode ser concluido sem a verificacao final limpa no commit atual: "
                + "; ".join(motivos),
                PORTAO,
                {"id_goal": id_goal},
                modo=ModoFalhaMAST.FECHAMENTO_SEM_VERIFICACAO_LIMPA,
            )
    return ResultadoValidacao.sucesso()


def motivos_para_nao_fechar(view: GrafoView, id_goal: str) -> tuple[str, ...]:
    """O que falta para o Goal fechar; vazio quando a prova está toda lá, ou quando a regra não o alcança."""
    goal = view.obter_no(id_goal)
    if goal is None or not _alcancado(view, goal):
        return ()
    ultima = _ultima_verificacao(view, id_goal)
    if ultima is None:
        return ("o Goal nao tem verificacao",)
    return (
        *_motivos_da_verificacao(view, goal, ultima),
        *_criterios_sem_atende(view, goal, ultima),
        *_bloqueantes_abertos(view, goal),
    )


def _com_as_escritas_do_lote(proposta: PropostaPatch, depois: GrafoEstado) -> GrafoEstado:
    """O estado depois do lote com as propriedades que o lote escreve ou remove nos nós que sobrevivem a ele."""
    nos = dict(depois.nos)
    for item in proposta.operacoes:
        _aplicar_escrita(nos, item)
    return GrafoEstado(nos=nos, arestas=depois.arestas, versao_log=depois.versao_log)


def _aplicar_escrita(nos: dict[str, NoGrafo], item: ItemPatch) -> None:
    """A escrita em `/nos/<id>/propriedades/<chave>` aplicada ao nó, quando ele existe."""
    segmentos = [segmento for segmento in item.path.split("/") if segmento]
    if len(segmentos) != SEGMENTOS_DA_PROPRIEDADE or segmentos[0] != "nos" or segmentos[1] not in nos:
        return
    no = nos[segmentos[1]]
    propriedades = {chave: valor for chave, valor in no.propriedades.items() if chave != segmentos[3]}
    if item.op != OperacaoPatch.REMOVE:
        propriedades[segmentos[3]] = item.value
    nos[no.id] = replace(no, propriedades=propriedades)


def _goals_que_o_lote_conclui(proposta: PropostaPatch, depois: GrafoEstado) -> Iterator[str]:
    """Os Goals em que o lote escreve `status: concluido`, na propriedade, nas propriedades ou no nó inteiro."""
    for item in proposta.operacoes:
        segmentos = [segmento for segmento in item.path.split("/") if segmento]
        if item.op == OperacaoPatch.REMOVE or len(segmentos) < SEGMENTOS_DE_ELEMENTO_INTEIRO or segmentos[0] != "nos":
            continue
        no = depois.nos.get(segmentos[1])
        if no is not None and no.tipo == TipoNo.GOAL and _escreve_concluido(segmentos, item.value):
            yield no.id


def _escreve_concluido(segmentos: list[str], valor: Any) -> bool:
    """A operação grava `concluido` no status do nó."""
    if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE:
        return segmentos[3] == CAMPO_STATUS and valor == StatusTask.CONCLUIDO.value
    propriedades = valor.get("propriedades") if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO and isinstance(valor, dict) else valor
    return isinstance(propriedades, dict) and propriedades.get(CAMPO_STATUS) == StatusTask.CONCLUIDO.value


def _alcancado(view: GrafoView, goal: NoGrafo) -> bool:
    """O Goal é conduzido pelo orquestrador ou tem critério de aceite como nó."""
    return a.CAMPO_CONDUCAO in goal.propriedades or bool(_criterios_do_goal(view, goal))


def _do_orquestrador(no: NoGrafo | None) -> bool:
    """O nó nasceu de um lote do orquestrador: só a verificação, o Achado e a revisão dele contam para fechar."""
    return no is not None and no.proveniencia.papel == PapelAutor.ORQUESTRADOR.value


def _verificacoes(view: GrafoView, id_goal: str) -> list[NoGrafo]:
    """As Evidence de verificação que o orquestrador gravou derivando do Goal, pela ordem do log."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_goal, TipoAresta.DERIVA_DE))
    verificacoes = [no for no in origens if _do_orquestrador(no) and no.obter_propriedade(a.CAMPO_ACAO) == a.ACAO_DA_VERIFICACAO]
    return sorted(verificacoes, key=lambda no: (no.ordem.seq_criacao or SEQ_DO_LOTE, no.id))


def _ultima_verificacao(view: GrafoView, id_goal: str) -> NoGrafo | None:
    """A verificação mais nova no log; a que nasce no próprio lote conta como a mais nova."""
    verificacoes = _verificacoes(view, id_goal)
    return verificacoes[-1] if verificacoes else None


def _achados_de(view: GrafoView, id_evidencia: str) -> list[NoGrafo]:
    """Os Achados que o orquestrador gravou derivando da Evidence."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_evidencia, TipoAresta.DERIVA_DE))
    return [no for no in origens if _do_orquestrador(no) and no.tipo == TipoNo.ACHADO]


def _bloqueante_encerrado(achado: NoGrafo) -> bool:
    """O Achado não é bloqueante, ou foi resolvido, ou descartado pelo humano."""
    if achado.obter_propriedade(a.CAMPO_GRAVIDADE) != a.GRAVIDADE_BLOQUEANTE:
        return True
    return achado.obter_propriedade(a.CAMPO_ESTADO) in a.ESTADOS_QUE_ENCERRAM_O_BLOQUEANTE


def _motivos_da_verificacao(view: GrafoView, goal: NoGrafo, ultima: NoGrafo) -> list[str]:
    """A última verificação é a final, limpa, e vale para a ponta da branch do Goal."""
    motivos: list[str] = []
    if ultima.obter_propriedade(a.CAMPO_FINAL) is not True:
        motivos.append(f"a ultima verificacao ({ultima.id}) nao e a final, sobre o Goal inteiro")
    bloqueantes = [achado for achado in _achados_de(view, ultima.id) if achado.obter_propriedade(a.CAMPO_GRAVIDADE) == a.GRAVIDADE_BLOQUEANTE]
    limpa = ultima.obter_propriedade(a.CAMPO_VEREDITO) == a.VEREDITO_LIMPO or (
        bool(bloqueantes) and all(_bloqueante_encerrado(achado) for achado in bloqueantes)
    )
    if not limpa:
        motivos.append(f"a ultima verificacao ({ultima.id}) nao e limpa")
    verificado = str(ultima.obter_propriedade(a.CAMPO_COMMIT_DO_CODIGO) or "")
    ponta = goal.obter_propriedade(a.CAMPO_PONTA_DO_RAMO)
    atual = str(ponta.get(a.CAMPO_COMMIT_DO_CODIGO) or "") if isinstance(ponta, Mapping) else ""
    if not atual:
        motivos.append("o Goal nao diz a ponta da branch dele (ponta_do_ramo)")
    elif verificado != atual:
        motivos.append(f"a ultima verificacao foi feita no commit {verificado[:12] or '?'}, e a ponta da branch do Goal esta em {atual[:12]}")
    return motivos


def _criterios_do_goal(view: GrafoView, goal: NoGrafo) -> tuple[str, ...]:
    """Os Criterio que escopam o Goal e os nós que o plano gravado lista como critério, menos os que o humano tirou."""
    ligados = [aresta.origem_id for aresta in view.obter_arestas_entrada(goal.id, TipoAresta.ESCOPA)]
    nos = [no for no in (view.obter_no(id_no) for id_no in ligados) if no is not None and no.tipo == TipoNo.CRITERIO]
    plano = goal.obter_propriedade(a.CAMPO_PLANO)
    do_plano = plano.get(a.CAMPO_CRITERIOS_DO_PLANO, []) if isinstance(plano, Mapping) else []
    citados = [str(item.get(a.CAMPO_NO_DO_PARECER)) for item in do_plano if isinstance(item, Mapping) and item.get(a.CAMPO_NO_DO_PARECER)]
    todos = dict.fromkeys([*(no.id for no in nos), *citados])
    return tuple(id_no for id_no in todos if not _retirado_pelo_humano(view, id_no))


def _retirado_pelo_humano(view: GrafoView, id_criterio: str) -> bool:
    """O Criterio saiu do plano por uma Decision do humano (o replanejamento que ele pediu)."""
    no = view.obter_no(id_criterio)
    retirado = no.obter_propriedade(a.CAMPO_RETIRADO) if no is not None else None
    decisao = view.obter_no(str(retirado.get("decisao", ""))) if isinstance(retirado, Mapping) else None
    return decisao is not None and decisao.tipo == TipoNo.DECISION and decisao.proveniencia.papel == PapelAutor.HUMANO.value


def _criterios_sem_atende(view: GrafoView, goal: NoGrafo, ultima: NoGrafo) -> list[str]:
    """Cada critério do Goal sem parecer `atende` na última verificação (o retirado pelo humano já saiu da conta)."""
    pareceres = ultima.obter_propriedade(a.CAMPO_PARECERES)
    vereditos = {
        str(parecer.get(a.CAMPO_NO_DO_PARECER)): str(parecer.get(a.CAMPO_VEREDITO))
        for parecer in (pareceres if isinstance(pareceres, list) else []) if isinstance(parecer, Mapping)
    }
    return [
        f"o criterio {id_no} esta '{vereditos.get(id_no, 'sem parecer')}' na ultima verificacao"
        for id_no in _criterios_do_goal(view, goal)
        if vereditos.get(id_no) != a.VEREDITO_QUE_ATENDE
    ]


def _bloqueantes_abertos(view: GrafoView, goal: NoGrafo) -> list[str]:
    """Os Achados bloqueantes do Goal que nada encerrou: os das verificações e das revisões dele e os que ferem o que é dele."""
    return [
        f"o achado bloqueante {achado.id} esta '{achado.obter_propriedade(a.CAMPO_ESTADO) or a.ESTADO_ABERTO}'"
        for achado in _achados_do_goal(view, goal) if not _bloqueante_encerrado(achado)
    ]


def _achados_do_goal(view: GrafoView, goal: NoGrafo) -> list[NoGrafo]:
    """Os Achados das verificações do Goal, das revisões das fatias dele e os que ferem critério ou decisão dele."""
    origens = [verificacao.id for verificacao in _verificacoes(view, goal.id)] + _revisoes_das_fatias(view, goal.id)
    governam = {aresta.origem_id for tipo in (TipoAresta.ESCOPA, TipoAresta.ORIENTA)
                for aresta in view.obter_arestas_entrada(goal.id, tipo)}
    ferem = [view.obter_no(aresta.origem_id) for id_no in governam for aresta in view.obter_arestas_entrada(id_no, TipoAresta.FERE)]
    achados = [*(achado for origem in origens for achado in _achados_de(view, origem)), *(no for no in ferem if _do_orquestrador(no))]
    return list({achado.id: achado for achado in achados}.values())


def _revisoes_das_fatias(view: GrafoView, id_goal: str) -> list[str]:
    """As Evidence de revisão de risco que derivam das fatias do Goal."""
    fatias = [aresta.destino_id for aresta in view.obter_arestas_saida(id_goal, TipoAresta.DECOMPOE)]
    revisoes = (view.obter_no(aresta.origem_id) for id_task in fatias for aresta in view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE))
    return [no.id for no in revisoes if _do_orquestrador(no) and no.obter_propriedade(a.CAMPO_ACAO) == a.ACAO_DA_REVISAO_DE_RISCO]
