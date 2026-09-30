"""`graphow base-colisoes`: o que o ramo base ganhou e colide com o Goal, dito cedo.

Junta as três metades: o grafo diz o ramo base, os globs e os caminhos que o
Goal toca; o git diz o que o ramo base ganhou desde o merge-base; o cruzamento
puro diz o que colide. O condutor roda o comando ao situar a rodada e, com
colisão, não despacha tarefa nos caminhos de colisão: quem integra é o humano.

O código de saída segue o de `docs-gerar --conferir`: 0 quando não há o que
apontar, inclusive sem `ramo_base` resolvido, 1 quando há colisão. O 2 diz que
a conferência não aconteceu (Goal inexistente, git ausente, ramo base que não
existe no repositório), para quem lê não confundir falta de resposta com
colisão.
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.api.colisoes_base import cruzar_colisoes, nos_caminhos_de_colisao
from graphow.api.git_ramo_base import ComparacaoComBase, ExecutorGit, FalhaDoGit, comparar_com_ramo_base
from graphow.core.types import TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.integracao_base import IntegracaoDoGoal, caminhos_do_goal, resolver_integracao

CODIGO_SEM_COLISAO: int = 0
CODIGO_COM_COLISAO: int = 1
CODIGO_CONFERENCIA_IMPOSSIVEL: int = 2


@dataclass(frozen=True)
class PedidoDeConferencia:
    """O Goal conferido, o repositório em que o git roda e se o ramo remoto é atualizado antes."""

    id_goal: str
    repositorio: Path
    buscar: bool = True


@dataclass(frozen=True)
class RelatorioDeColisoes:
    """As linhas que o comando imprime e o código com que ele sai."""

    linhas: tuple[str, ...]
    codigo: int


def conferir_colisoes(view: GrafoView, pedido: PedidoDeConferencia) -> RelatorioDeColisoes:
    """Resolve o ramo base do Goal, pergunta ao git o que ele ganhou e cruza com o que o Goal toca."""
    goal = view.obter_no(pedido.id_goal)
    if goal is None or goal.tipo != TipoNo.GOAL:
        return RelatorioDeColisoes((f"Goal inexistente: {pedido.id_goal}",), CODIGO_CONFERENCIA_IMPOSSIVEL)
    integracao = resolver_integracao(view, pedido.id_goal)
    if not integracao.ramo_base or not integracao.caminhos_de_colisao:
        return RelatorioDeColisoes((_sem_o_que_conferir(pedido.id_goal, integracao),), CODIGO_SEM_COLISAO)
    cabecalho = _cabecalho(integracao)
    try:
        comparacao = comparar_com_ramo_base(ExecutorGit(pedido.repositorio), integracao.ramo_base, buscar=pedido.buscar)
    except FalhaDoGit as falha:
        return RelatorioDeColisoes((cabecalho, falha.formatar_para_llm()), CODIGO_CONFERENCIA_IMPOSSIVEL)
    return _relatar(integracao, comparacao, caminhos=caminhos_do_goal(view, pedido.id_goal), cabecalho=cabecalho)


def _relatar(
    integracao: IntegracaoDoGoal,
    comparacao: ComparacaoComBase,
    *,
    caminhos: tuple[str, ...],
    cabecalho: str,
) -> RelatorioDeColisoes:
    """O cabeçalho, o aviso do fetch, a contagem, uma linha por colisão e o fecho."""
    ganhos = nos_caminhos_de_colisao(comparacao.arquivos, integracao.caminhos_de_colisao)
    colisoes = cruzar_colisoes(ganhos, caminhos, integracao.caminhos_de_colisao)
    linhas = [cabecalho, f"Aviso: {comparacao.aviso}"] if comparacao.aviso else [cabecalho]
    linhas.append(
        f"Merge-base {comparacao.merge_base}: o ramo base ganhou {len(comparacao.arquivos)} arquivos desde entao, "
        f"{len(ganhos)} nos caminhos de colisao; o Goal toca {len(caminhos)} caminhos"
    )
    linhas.extend(colisao.formatar() for colisao in colisoes)
    if not colisoes:
        return RelatorioDeColisoes((*linhas, f"Sem colisao com {integracao.ramo_base}."), CODIGO_SEM_COLISAO)
    linhas.append(f"Colisoes: {len(colisoes)}. Integre {integracao.ramo_base} antes de seguir nesses caminhos.")
    return RelatorioDeColisoes(tuple(linhas), CODIGO_COM_COLISAO)


def _cabecalho(integracao: IntegracaoDoGoal) -> str:
    """De onde veio cada propriedade, para o humano saber onde mudar."""
    globs = ", ".join(integracao.caminhos_de_colisao)
    return (
        f"Ramo base: {integracao.ramo_base} (de {integracao.origem_do_ramo}); "
        f"caminhos de colisao: {globs} (de {integracao.origem_dos_caminhos})"
    )


def _sem_o_que_conferir(id_goal: str, integracao: IntegracaoDoGoal) -> str:
    """A linha de quando falta uma das duas propriedades: não é erro, só não há o que conferir."""
    if not integracao.ramo_base:
        return f"Goal {id_goal} sem ramo_base no Goal, no Setor nem no Projeto: nada a conferir."
    return (
        f"Ramo base {integracao.ramo_base} (de {integracao.origem_do_ramo}) sem caminhos_de_colisao "
        "no Goal, no Setor nem no Projeto: nada a conferir."
    )
