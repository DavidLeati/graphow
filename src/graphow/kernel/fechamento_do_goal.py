"""O Goal só fecha com a prova: a verificação final limpa no commit atual, todo critério atendido e nenhum bloqueante aberto.

Na fase 1 a regra morava só no orquestrador: o laço não fechava sem a
verificação limpa, mas o livro-razão aceitava qualquer lote que pusesse o Goal
em `concluido`. Aqui ela é do kernel e vale para todo papel, o humano
inclusive, sobre o estado depois do lote. O Goal que o lote conclui, quando é
conduzido pelo orquestrador (`orquestracao`) ou tem `Criterio` ligado, precisa:

- de uma verificação (Evidence `verificacao_do_goal` que deriva do Goal) como a
  última, pelo número, e que seja a final, sobre o Goal inteiro;
- de veredito limpo nessa verificação;
- de que ela tenha sido feita no commit do código que é a ponta da branch do
  Goal (`ponta_do_ramo`, que o orquestrador grava do git a cada commit; o
  commit que só muda o documento do Goal não muda o commit do código);
- de parecer `atende` nela para cada critério do Goal: todo `Criterio` que o
  escopa e todo nó que o plano gravado lista como critério;
- e de que nenhum `Achado` bloqueante das verificações do Goal siga aberto ou
  só corrigido, sem a verificação que o resolve.

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
from graphow.core.types import StatusTask, TipoAresta, TipoNo
from graphow.kernel.estrutura_apos_lote import EstruturaAposLote
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.projection.graph_view import GrafoView

PORTAO: str = "InvariantGate"
CAMPO_STATUS: str = "status"
SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2
SEGMENTOS_DA_PROPRIEDADE: int = 4


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
        *_motivos_da_verificacao(goal, ultima),
        *_criterios_sem_atende(view, goal, ultima),
        *_bloqueantes_abertos(view, id_goal),
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


def _verificacoes(view: GrafoView, id_goal: str) -> list[NoGrafo]:
    """As Evidence de verificação que derivam do Goal."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_goal, TipoAresta.DERIVA_DE))
    return [no for no in origens if no is not None and no.obter_propriedade(a.CAMPO_ACAO) == a.ACAO_DA_VERIFICACAO]


def _ultima_verificacao(view: GrafoView, id_goal: str) -> NoGrafo | None:
    """A verificação de maior número; entre as sem número, a mais nova no log."""
    verificacoes = _verificacoes(view, id_goal)
    return max(verificacoes, key=lambda no: (_inteiro(no.obter_propriedade(a.CAMPO_NUMERO)), no.ordem.seq_criacao, no.id), default=None)


def _inteiro(valor: object) -> int:
    """O número gravado, ou zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


def _motivos_da_verificacao(goal: NoGrafo, ultima: NoGrafo) -> list[str]:
    """A última verificação é a final, limpa, e vale para a ponta da branch do Goal."""
    motivos: list[str] = []
    if ultima.obter_propriedade(a.CAMPO_FINAL) is not True:
        motivos.append(f"a ultima verificacao ({ultima.id}) nao e a final, sobre o Goal inteiro")
    if ultima.obter_propriedade(a.CAMPO_VEREDITO) != a.VEREDITO_LIMPO:
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
    """Os Criterio que escopam o Goal e os nós que o plano gravado lista como critério."""
    ligados = [aresta.origem_id for aresta in view.obter_arestas_entrada(goal.id, TipoAresta.ESCOPA)]
    nos = [no for no in (view.obter_no(id_no) for id_no in ligados) if no is not None and no.tipo == TipoNo.CRITERIO]
    plano = goal.obter_propriedade(a.CAMPO_PLANO)
    do_plano = plano.get(a.CAMPO_CRITERIOS_DO_PLANO, []) if isinstance(plano, Mapping) else []
    citados = [str(item.get(a.CAMPO_NO_DO_PARECER)) for item in do_plano if isinstance(item, Mapping) and item.get(a.CAMPO_NO_DO_PARECER)]
    return tuple(dict.fromkeys([*(no.id for no in nos), *citados]))


def _criterios_sem_atende(view: GrafoView, goal: NoGrafo, ultima: NoGrafo) -> list[str]:
    """Cada critério do Goal sem parecer `atende` na última verificação."""
    pareceres = ultima.obter_propriedade(a.CAMPO_PARECERES)
    vereditos = {
        str(parecer.get(a.CAMPO_NO_DO_PARECER)): str(parecer.get(a.CAMPO_VEREDITO))
        for parecer in (pareceres if isinstance(pareceres, list) else []) if isinstance(parecer, Mapping)
    }
    return [
        f"o criterio {id_no} esta '{vereditos.get(id_no, 'sem parecer')}' na ultima verificacao"
        for id_no in _criterios_do_goal(view, goal) if vereditos.get(id_no) != a.VEREDITO_QUE_ATENDE
    ]


def _bloqueantes_abertos(view: GrafoView, id_goal: str) -> list[str]:
    """Os Achados bloqueantes das verificações do Goal que nenhuma verificação limpa resolveu."""
    achados = (
        view.obter_no(aresta.origem_id)
        for verificacao in _verificacoes(view, id_goal)
        for aresta in view.obter_arestas_entrada(verificacao.id, TipoAresta.DERIVA_DE)
    )
    return [
        f"o achado bloqueante {no.id} esta '{no.obter_propriedade(a.CAMPO_ESTADO) or a.ESTADO_ABERTO}'"
        for no in achados
        if no is not None and no.tipo == TipoNo.ACHADO and no.obter_propriedade(a.CAMPO_GRAVIDADE) == a.GRAVIDADE_BLOQUEANTE
        and no.obter_propriedade(a.CAMPO_ESTADO) not in a.ESTADOS_QUE_ENCERRAM_O_BLOQUEANTE
    ]
