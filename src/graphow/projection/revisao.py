"""A revisão de uma tarefa lida do grafo: os vereditos que ela recebeu e o que vigora entre eles.

O veredito do revisor é uma Evidence com a propriedade `veredito` que deriva do
Artifact entregue e da Task. A medição da orquestração contava esses vereditos
por conta própria, e a posse de tarefa passou a precisar do mesmo dado para
decidir se uma tarefa aprovada pode ser fechada por outro executor. As duas
pontas leem daqui, para uma não achar veredito onde a outra não acha.

Daqui sai também a cadeia de correções: a correção aponta por `corrige` o
veredito que a motivou, e o veredito chega à tarefa julgada, que pode ser ela
mesma uma correção.
"""

from collections.abc import Iterable

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import CAMPO_CORRIGE, CAMPO_VEREDITO, VEREDITO_APROVADO, ler_texto
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def artefatos_da_tarefa(view: GrafoView, id_task: str) -> frozenset[str]:
    """Os Artifacts que derivam da Task: o que o executor entregou para revisão."""
    return frozenset(
        aresta.origem_id
        for aresta in view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE)
        if _eh_do_tipo(view, aresta.origem_id, TipoNo.ARTIFACT)
    )


def vereditos_sobre(view: GrafoView, alvos: Iterable[str]) -> tuple[NoGrafo, ...]:
    """As Evidence com veredito que derivam de algum dos alvos, em ordem de identificador."""
    candidatas = {
        aresta.origem_id
        for id_alvo in alvos
        for aresta in view.obter_arestas_entrada(id_alvo, TipoAresta.DERIVA_DE)
    }
    nos = (view.obter_no(id_no) for id_no in sorted(candidatas))
    return tuple(no for no in nos if no is not None and no.tipo == TipoNo.EVIDENCE and ler_texto(no.propriedades, CAMPO_VEREDITO))


def veredito_vigente(view: GrafoView, id_task: str) -> str:
    """O veredito mais recente sobre a Task ou os Artifacts dela; vazio quando ninguém revisou.

    Uma tarefa pode ser reprovada e depois aprovada, ou o contrário, e só o
    último julgamento diz o que vale agora. Mais recente é a última escrita no
    nó pela ordem do log, não o relógio: o revisor que troca o veredito de uma
    Evidence existente também emite um julgamento novo.
    """
    ultimo = evidencia_do_veredito_vigente(view, id_task)
    return ler_texto(ultimo.propriedades, CAMPO_VEREDITO) if ultimo is not None else ""


def evidencia_do_veredito_vigente(view: GrafoView, id_task: str) -> NoGrafo | None:
    """A Evidence do julgamento mais recente sobre a Task ou os Artifacts dela; None quando ninguém revisou."""
    vereditos = vereditos_sobre(view, {id_task} | artefatos_da_tarefa(view, id_task))
    if not vereditos:
        return None
    return max(vereditos, key=lambda no: (no.ordem.seq_atualizacao, no.ordem.seq_criacao, no.id))


def veredito_efetivo(view: GrafoView, id_task: str) -> str:
    """O veredito vigente, a menos que uma correção aprovada o tenha superado.

    A correção aponta por `corrige` a Evidence da rejeição da original. Se a
    correção vale como aprovada, a rejeição que ela motivou deixou de ser o
    que impede a original, e o veredito efetivo desta é `aprovado`. A correção
    pode ter a própria correção, e a cadeia se segue até uma aprovada ou até
    não haver mais; um ciclo na cadeia não supera nada.
    """
    return _efetivo(view, id_task, frozenset())


def _efetivo(view: GrafoView, id_task: str, visitadas: frozenset[str]) -> str:
    """O veredito efetivo da Task, sem repassar por Task já visitada na cadeia."""
    vigente = veredito_vigente(view, id_task)
    if vigente == VEREDITO_APROVADO or not vigente:
        return vigente
    julgamento = evidencia_do_veredito_vigente(view, id_task)
    corrigidas = visitadas | {id_task}
    superada = julgamento is not None and any(
        _efetivo(view, correcao, corrigidas) == VEREDITO_APROVADO
        for correcao in _correcoes_de(view, julgamento.id)
        if correcao not in corrigidas
    )
    return VEREDITO_APROVADO if superada else vigente


def _correcoes_de(view: GrafoView, id_veredito: str) -> tuple[str, ...]:
    """As Task que corrigem a Evidence de veredito, em ordem de identificador."""
    return tuple(sorted(
        no.id for no in view.listar_nos_por_tipo(TipoNo.TASK) if ler_texto(no.propriedades, CAMPO_CORRIGE) == id_veredito
    ))


def tarefa_julgada(view: GrafoView, id_veredito: str) -> str:
    """A Task que o veredito julgou; vazio quando o veredito não chega a nenhuma.

    O revisor deriva o veredito da Task e do Artifact. Quando falta a aresta
    direta para a Task, ela ainda se alcança pelo Artifact julgado.
    """
    diretas = _destinos_do_tipo(view, id_veredito, TipoNo.TASK)
    if diretas:
        return diretas[0]
    pelo_artefato = sorted(
        id_task for id_artefato in _destinos_do_tipo(view, id_veredito, TipoNo.ARTIFACT)
        for id_task in _destinos_do_tipo(view, id_artefato, TipoNo.TASK)
    )
    return pelo_artefato[0] if pelo_artefato else ""


def profundidade_da_correcao(view: GrafoView, id_task: str) -> int:
    """Quantas correções há na cadeia até a Task original: 0 na original, 1 na primeira correção.

    A cadeia segue o `corrige` até o veredito e dele até a tarefa julgada, e
    repete enquanto essa também for correção. É pelo veredito, e não pelo
    pai na decomposição, porque é o `corrige` que faz de uma Task uma
    correção. Um `corrige` cujo veredito não chega a nenhuma tarefa ainda
    conta um passo, e a cadeia para ali; um ciclo também para.
    """
    profundidade = 0
    visitadas = {id_task}
    no = view.obter_no(id_task)
    while no is not None and ler_texto(no.propriedades, CAMPO_CORRIGE):
        profundidade += 1
        julgada = tarefa_julgada(view, ler_texto(no.propriedades, CAMPO_CORRIGE))
        if not julgada or julgada in visitadas:
            break
        visitadas.add(julgada)
        no = view.obter_no(julgada)
    return profundidade


def _destinos_do_tipo(view: GrafoView, id_origem: str, tipo: TipoNo) -> list[str]:
    """Os nós do tipo pedido de que a origem deriva, em ordem de identificador."""
    return sorted(
        aresta.destino_id
        for aresta in view.obter_arestas_saida(id_origem, TipoAresta.DERIVA_DE)
        if _eh_do_tipo(view, aresta.destino_id, tipo)
    )


def _eh_do_tipo(view: GrafoView, id_no: str, tipo: TipoNo) -> bool:
    """O nó existe e é do tipo pedido."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == tipo
