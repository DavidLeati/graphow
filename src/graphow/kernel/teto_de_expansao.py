"""O teto de expansão (D6 do escopo governado): recusa por contagem, só quando a política liga.

A leitura `teto_expansao` da política do nó vem desligada (0). Ligada, o agente que
cria Task emergente (B3) num Goal que já tem `teto_expansao` emergentes de agente
desde o último zero é recusado, até um `responder_desvio` ou `aprovar_plano` de
humano zerar a contagem. A contagem é a do placar (`custo_de_escopo`), com as Tasks
do próprio lote somadas na ordem. O humano nunca passa por aqui: criar Task é, para
ele, um gesto consciente de escopo. A Task sem ligação já foi recusada antes (D2).
"""

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor
from graphow.kernel.estrutura_apos_lote import EstruturaAposLote
from graphow.kernel.patch_models import PropostaPatch, ResultadoValidacao
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from graphow.projection.classificacao_escopo import ClasseDeEscopo, ClassificadorDeEscopo
from graphow.projection.custo_de_escopo import emergentes_do_agente_desde_o_zero


def validar_teto_de_expansao(
    proposta: PropostaPatch,
    estrutura: EstruturaAposLote,
    classificador: ClassificadorDeEscopo,
) -> ResultadoValidacao:
    """Recusa a Task B3 de agente que passaria do teto da política; sucesso quando ele está desligado."""
    if proposta.papel == PapelAutor.HUMANO:
        return ResultadoValidacao.sucesso()
    admitidas: dict[str, int] = {}
    for id_task in sorted(estrutura.criados):
        id_goal = classificador.goal_da(id_task)
        if id_goal is None or classificador.classe_da(id_task) != ClasseDeEscopo.B3:
            continue
        teto = resolver_politica_do_no(id_task, classificador.view.estado, RastreadorProjetoAncestral()).teto_expansao
        if teto <= 0:
            continue
        if id_goal not in admitidas:
            admitidas[id_goal] = _emergentes_anteriores(classificador, estrutura, id_goal)
        if admitidas[id_goal] >= teto:
            return _recusar_orcamento_esgotado(id_task, id_goal, teto)
        admitidas[id_goal] += 1
    return ResultadoValidacao.sucesso()


def _emergentes_anteriores(classificador: ClassificadorDeEscopo, estrutura: EstruturaAposLote, id_goal: str) -> int:
    """As emergentes de agente do Goal desde o último zero que já existiam antes do lote."""
    antigas = emergentes_do_agente_desde_o_zero(classificador.view, id_goal)
    return sum(1 for task in antigas if task.id not in estrutura.criados)


def _recusar_orcamento_esgotado(id_task: str, id_goal: str, teto: int) -> ResultadoValidacao:
    """Diz o teto, o gesto que reabre e o que fazer com a Task: devolver à raiz, não contornar."""
    return ResultadoValidacao.falha(
        f"Task '{id_task}' passaria do teto de expansão do Goal '{id_goal}': já são {teto} Tasks emergentes de "
        "agente desde o último zero, o limite da política (teto_expansao). Um 'responder_desvio' do humano "
        "(ou um 'aprovar_plano' do humano) reabre o orçamento. Devolva a decisão à raiz: abra uma Question ao "
        "humano ou proponha o que fica fora do Goal, e não contorne pendurando a Task em outra ligação",
        "InvariantGate",
        {"id_task": id_task, "id_goal": id_goal, "teto_expansao": str(teto)},
        modo=ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO,
    )
