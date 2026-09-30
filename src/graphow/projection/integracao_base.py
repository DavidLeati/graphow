"""O ramo base de um Goal e os caminhos em que ele colide, lidos do grafo por herança.

Num goal real, o ramo base ganhou migrations com os mesmos números que o Goal
usava, e só se soube no merge, dias depois: a renumeração levou duas horas.
Para conferir cedo, o condutor precisa saber em que ramo o trabalho vai ser
integrado e que caminhos colidem sem tocar o mesmo arquivo. O humano grava as
duas propriedades no Goal, no Setor ou no Projeto, e o Goal herda cada uma do
primeiro que a tiver.

O Goal não pende do Setor por `contem`: ele é produzido por uma Sessao, que o
Setor contém, e o Setor é contido pelo Projeto. A herança sobe esse caminho.

Daqui saem também os caminhos que o Goal toca, contra os quais o que o ramo
base ganhou é cruzado.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import (
    CAMPO_ARQUIVOS,
    CAMPO_ARQUIVOS_ALVO,
    CAMPO_CAMINHOS_DE_COLISAO,
    CAMPO_RAMO_BASE,
    ler_texto,
    ler_textos,
)
from graphow.core.types import StatusTask, TipoAresta, TipoNo
from graphow.projection.decomposicao import tarefas_da_decomposicao
from graphow.projection.graph_view import GrafoView
from graphow.projection.revisao import artefatos_da_tarefa


@dataclass(frozen=True)
class IntegracaoDoGoal:
    """O ramo base e os globs de colisão que valem para o Goal, com o nó de onde cada um veio.

    Vazio é ausência: ninguém na herança gravou a propriedade.
    """

    ramo_base: str = ""
    origem_do_ramo: str = ""
    caminhos_de_colisao: tuple[str, ...] = ()
    origem_dos_caminhos: str = ""


def resolver_integracao(view: GrafoView, id_goal: str) -> IntegracaoDoGoal:
    """Cada propriedade vem do primeiro nó que a tem: o Goal, depois o Setor, depois o Projeto.

    As duas se resolvem uma a uma. O Projeto pode declarar os globs de
    migration para todos, e um Goal que vai para outro ramo grava só o
    `ramo_base` dele, sem repetir os globs.
    """
    cadeia = cadeia_de_heranca(view, id_goal)
    com_ramo = _primeiro_com(cadeia, lambda no: ler_texto(no.propriedades, CAMPO_RAMO_BASE))
    com_caminhos = _primeiro_com(cadeia, lambda no: ler_textos(no.propriedades.get(CAMPO_CAMINHOS_DE_COLISAO)))
    return IntegracaoDoGoal(
        ramo_base=ler_texto(com_ramo.propriedades, CAMPO_RAMO_BASE) if com_ramo else "",
        origem_do_ramo=com_ramo.id if com_ramo else "",
        caminhos_de_colisao=ler_textos(com_caminhos.propriedades.get(CAMPO_CAMINHOS_DE_COLISAO)) if com_caminhos else (),
        origem_dos_caminhos=com_caminhos.id if com_caminhos else "",
    )


def caminhos_do_goal(view: GrafoView, id_goal: str) -> tuple[str, ...]:
    """Os caminhos que o trabalho do Goal toca, sem repetição e em ordem.

    São os `arquivos_alvo` das tarefas que ainda não fecharam, que é o que
    o Goal vai tocar, e os `arquivos` dos Artifacts de todas as tarefas, que
    é o que ele já tocou: a migration entregue numa tarefa concluída segue no
    ramo do Goal até o merge, e é ela que colide.
    """
    tarefas = tarefas_da_decomposicao(view, id_goal)
    abertas = (no for no in tarefas if no.obter_propriedade("status") != StatusTask.CONCLUIDO.value)
    alvos = [caminho for no in abertas for caminho in ler_textos(no.propriedades.get(CAMPO_ARQUIVOS_ALVO))]
    artefatos = sorted({id_artefato for no in tarefas for id_artefato in artefatos_da_tarefa(view, no.id)})
    entregues = [caminho for id_artefato in artefatos for caminho in _arquivos_do_artefato(view, id_artefato)]
    return tuple(sorted(set(alvos) | set(entregues)))


def _arquivos_do_artefato(view: GrafoView, id_artefato: str) -> tuple[str, ...]:
    """Os arquivos que o executor declarou no Artifact; vazio quando ele sumiu."""
    artefato = view.obter_no(id_artefato)
    return ler_textos(artefato.propriedades.get(CAMPO_ARQUIVOS)) if artefato is not None else ()


def cadeia_de_heranca(view: GrafoView, id_goal: str) -> tuple[NoGrafo, ...]:
    """O Goal, os Setores que contêm as sessões que o produziram e os Projetos desses Setores.

    Cada nível em ordem de identificador, para o mesmo grafo dar sempre a
    mesma resposta quando mais de uma sessão produziu o Goal.
    """
    goal = view.obter_no(id_goal)
    if goal is None:
        return ()
    sessoes = _origens(view, [goal.id], aresta=TipoAresta.PRODUZ, tipo=TipoNo.SESSAO)
    setores = _origens(view, [no.id for no in sessoes], aresta=TipoAresta.CONTEM, tipo=TipoNo.SETOR)
    projetos = _origens(view, [no.id for no in setores], aresta=TipoAresta.CONTEM, tipo=TipoNo.PROJETO)
    return (goal, *setores, *projetos)


def _origens(view: GrafoView, destinos: Iterable[str], *, aresta: TipoAresta, tipo: TipoNo) -> tuple[NoGrafo, ...]:
    """Os nós do tipo pedido que chegam aos destinos pela aresta, sem repetição e em ordem de identificador."""
    ids = {ligacao.origem_id for id_destino in destinos for ligacao in view.obter_arestas_entrada(id_destino, aresta)}
    nos = (view.obter_no(id_no) for id_no in sorted(ids))
    return tuple(no for no in nos if no is not None and no.tipo == tipo)


def _primeiro_com(cadeia: Iterable[NoGrafo], valor: Callable[[NoGrafo], object]) -> NoGrafo | None:
    """O primeiro nó da cadeia em que a leitura devolve algo não vazio."""
    return next((no for no in cadeia if valor(no)), None)
