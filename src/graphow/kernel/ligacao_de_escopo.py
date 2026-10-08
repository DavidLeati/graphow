"""A Task que nasce sob um plano aprovado diz de onde veio (D2 do escopo governado).

Depois do `aprovar_plano`, toda Task criada sob o Goal precisa de uma ligação que o
kernel confere pela estrutura e pelo TIPO do alvo: subdivisão de Task do plano,
correção, acompanhamento, integração, reversão, ou `motivada_por` mais
`atende_criterio`. O Goal como pai sozinho não basta. A regra lê o estado depois do
lote, com as ligações que o próprio lote cria, e por isso cobre o `criar_tarefa` e o
`propor_patch`; vale para todo autor, o humano inclusive: invariante estrutural não
distingue quem escreve. Goal sem plano aprovado segue livre.

A Decision que o planejador cria para orientar o trabalho de um Goal com plano
também diz de onde veio, por `motivada_por`: assim a cadeia "decisão, Task,
evidência, nova decisão" tem raiz calculável. A classificação é a de
`projection/classificacao_escopo.py`, a mesma da fila e do placar. Os portões só
rodam na submissão: o replay do log antigo, com Task sem ligação sob Goal com
planos, reproduz sem erro.
"""

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.estrutura_apos_lote import EstruturaAposLote
from graphow.kernel.patch_models import PropostaPatch, ResultadoValidacao
from graphow.kernel.teto_de_expansao import validar_teto_de_expansao
from graphow.projection.classificacao_escopo import (
    LIGACOES_ACEITAS,
    BaseDoPlano,
    ClassificadorDeEscopo,
)
from graphow.projection.escopo_plano import plano_vigente
from graphow.projection.graph_view import GrafoView

EXEMPLO_DE_CRIAR_TAREFA: str = (
    "criar_tarefa(titulo=..., id_sessao=..., motivada_por=['<id da Decision, Evidence, Task ou Question>'], "
    "atende_criterio=['<id da Constraint criterio_aceite do Goal>'])"
)
TIPOS_CONFERIDOS: frozenset[TipoNo] = frozenset({TipoNo.TASK, TipoNo.DECISION})


def validar_escopo_das_tarefas(proposta: PropostaPatch, estrutura: EstruturaAposLote) -> ResultadoValidacao:
    """Confere as ligações de escopo das Tasks e Decisions que o lote cria e, ligado, o teto de expansão."""
    if not _criados_do_tipo(estrutura, TIPOS_CONFERIDOS):
        return ResultadoValidacao.sucesso()
    classificador = ClassificadorDeEscopo(GrafoView(estrutura.depois_no_log(proposta)), BaseDoPlano.VIGENTE)
    for id_task in _criados_do_tipo(estrutura, frozenset({TipoNo.TASK})):
        if not classificador.ligacao_valida(id_task):
            return _recusar_task_sem_ligacao(id_task, classificador.goal_da(id_task))
    resultado = _conferir_decisions(proposta, estrutura, classificador)
    if not resultado.aprovado:
        return resultado
    return validar_teto_de_expansao(proposta, estrutura, classificador)


def _conferir_decisions(
    proposta: PropostaPatch,
    estrutura: EstruturaAposLote,
    classificador: ClassificadorDeEscopo,
) -> ResultadoValidacao:
    """A Decision do planejador que orienta trabalho de Goal com plano leva `motivada_por`."""
    if proposta.papel != PapelAutor.PLANEJADOR:
        return ResultadoValidacao.sucesso()
    view = classificador.view
    for id_decisao in _criados_do_tipo(estrutura, frozenset({TipoNo.DECISION})):
        id_goal = _goal_com_plano_orientado_por(classificador, id_decisao)
        if id_goal is not None and not view.obter_arestas_saida(id_decisao, TipoAresta.MOTIVADA_POR):
            return _recusar_decision_sem_motivo(id_decisao, id_goal)
    return ResultadoValidacao.sucesso()


def _criados_do_tipo(estrutura: EstruturaAposLote, tipos: frozenset[TipoNo]) -> tuple[str, ...]:
    """Os nós dos tipos que o lote cria e que sobrevivem a ele, em ordem de id."""
    nos = estrutura.depois.nos
    return tuple(id_no for id_no in sorted(estrutura.criados) if id_no in nos and nos[id_no].tipo in tipos)


def _goal_com_plano_orientado_por(classificador: ClassificadorDeEscopo, id_decisao: str) -> str | None:
    """O Goal com plano vigente que a Decision orienta, direto ou por uma Task dele; None sem nenhum."""
    view = classificador.view
    for aresta in view.obter_arestas_saida(id_decisao, TipoAresta.ORIENTA):
        id_goal = _goal_do_alvo(classificador, aresta.destino_id)
        if id_goal is not None and plano_vigente(view, id_goal) is not None:
            return id_goal
    return None


def _goal_do_alvo(classificador: ClassificadorDeEscopo, id_alvo: str) -> str | None:
    """O próprio Goal, ou o Goal acima da Task; None para qualquer outro alvo."""
    no = classificador.view.obter_no(id_alvo)
    if no is None:
        return None
    if no.tipo == TipoNo.GOAL:
        return no.id
    return classificador.goal_da(id_alvo) if no.tipo == TipoNo.TASK else None


def _recusar_task_sem_ligacao(id_task: str, id_goal: str | None) -> ResultadoValidacao:
    """Lista as ligações aceitas e um exemplo, para o autor refazer o lote sem adivinhar."""
    aceitas = "; ".join(f"{classe.value}: {texto}" for classe, texto in LIGACOES_ACEITAS.items())
    return ResultadoValidacao.falha(
        f"Task '{id_task}' nasce no Goal '{id_goal}', que tem plano aprovado, sem ligação de escopo. "
        f"Ligações aceitas: {aceitas}. O Goal como pai sozinho não basta. Exemplo: {EXEMPLO_DE_CRIAR_TAREFA}. "
        "Se a Task é trabalho novo que o plano não previu, replaneje: peça nova versão do plano com 'aprovar_plano' "
        "(ou proponha o que fica fora do Goal), em vez de pendurá-la como subdivisão",
        "InvariantGate",
        {"id_task": id_task, "id_goal": id_goal or ""},
        modo=ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE,
    )


def _recusar_decision_sem_motivo(id_decisao: str, id_goal: str) -> ResultadoValidacao:
    """Diz que a Decision de um Goal com plano leva `motivada_por`."""
    return ResultadoValidacao.falha(
        f"Decision '{id_decisao}' orienta trabalho do Goal '{id_goal}', que tem plano aprovado, e nasce sem "
        "'motivada_por'. Crie no mesmo lote a aresta 'motivada_por' partindo dela para a Decision, Evidence, "
        "Task ou Question que a motivou: a origem de uma decisão é estrutural",
        "InvariantGate",
        {"id_decisao": id_decisao, "id_goal": id_goal},
        modo=ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE,
    )
