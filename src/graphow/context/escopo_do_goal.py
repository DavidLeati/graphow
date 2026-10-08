"""A seção de escopo da vista: o placar do Goal, em versão curta na Task e na Sessão.

O planejador e o humano leem o placar inteiro na vista do Goal e uma versão de
até três linhas na da Task e na da Sessão, porque é ali que o desvio nasce. O
executor não recebe o placar (não é dele), mas recebe a linha que diz por que
não pode assumir a Task de um Goal sem plano aprovado: o RoleGate recusa, e a
vista evita a tentativa. Os limiares K e M vêm da política do Projeto do Goal,
pelo mesmo caminho da seção Governanca.
"""

from graphow.context.governanca_vigente import resolver_politica_na_vista
from graphow.context.secoes import PrioridadeRetencao, SecaoContexto, em_uma_linha
from graphow.core.governanca import PoliticaGovernanca
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.projection.escopo_plano import goal_da_task, plano_vigente
from graphow.projection.graph_view import GrafoView
from graphow.projection.placar_escopo import LimiaresDeDesvio, PlacarDeEscopo, montar_placar

TITULO_DA_SECAO_DE_ESCOPO: str = "Escopo Do Goal"
TITULO_DA_SECAO_DE_PLANO: str = "Plano Do Goal"
ORDEM_DE_EXIBICAO_DO_ESCOPO: int = 1
MAXIMO_DE_GOALS_NA_SESSAO: int = 3
PAPEIS_COM_PLACAR: frozenset[PapelAutor] = frozenset({PapelAutor.PLANEJADOR, PapelAutor.HUMANO})
AVISO_SEM_PLANO: str = (
    "Plano: não aprovado — o executor não assume Tasks deste Goal até um aprovar_plano "
    "(humano, ou árbitro se a política entregar)"
)


def tem_plano_aprovado(view: GrafoView, id_goal: str) -> bool:
    """O Goal tem alguma versão de plano aprovada, de humano ou de árbitro: o que destrava o executor."""
    return plano_vigente(view, id_goal) is not None


def limiares_da_politica(politica: PoliticaGovernanca) -> LimiaresDeDesvio:
    """K e M como a política os entrega."""
    return LimiaresDeDesvio(por_raiz=politica.limiar_desvio_por_raiz, por_goal=politica.limiar_desvio_por_goal)


def limiares_do_goal(view: GrafoView, id_goal: str) -> LimiaresDeDesvio:
    """K e M do Goal, como a política do Projeto que o contém os resolve."""
    return limiares_da_politica(resolver_politica_na_vista(id_goal, view))


def placar_do_goal(view: GrafoView, id_goal: str) -> PlacarDeEscopo:
    """O placar do Goal com os limiares da política."""
    return montar_placar(view, id_goal, limiares_do_goal(view, id_goal))


def montar_secao_de_escopo(alvo: NoGrafo, view: GrafoView, papel: PapelAutor) -> SecaoContexto | None:
    """A seção de escopo que o papel lê no alvo; None quando o papel ou o alvo não a comportam."""
    if papel in PAPEIS_COM_PLACAR:
        return _secao_do_placar(alvo, view)
    if papel == PapelAutor.EXECUTOR and alvo.tipo == TipoNo.TASK:
        return _secao_do_executor(alvo, view)
    return None


def _secao_do_placar(alvo: NoGrafo, view: GrafoView) -> SecaoContexto | None:
    """O placar inteiro no Goal; a versão curta de cada Goal na Task e na Sessão."""
    if alvo.tipo == TipoNo.GOAL:
        return _secao(TITULO_DA_SECAO_DE_ESCOPO, _linhas_do_goal(view, alvo.id))
    goals = _goals_do_alvo(alvo, view)
    if not goals:
        return None
    return _secao(TITULO_DA_SECAO_DE_ESCOPO, tuple(linha for id_goal in goals for linha in _linhas_curtas(view, id_goal)))


def _linhas_do_goal(view: GrafoView, id_goal: str) -> tuple[str, ...]:
    """O aviso de plano não aprovado, quando for o caso, e o placar inteiro com os gatilhos."""
    placar = placar_do_goal(view, id_goal)
    aviso = () if tem_plano_aprovado(view, id_goal) else (AVISO_SEM_PLANO,)
    return tuple(f"- {em_uma_linha(linha)}" for linha in (*aviso, *placar.linhas(), *placar.linhas_de_desvio()))


def _linhas_curtas(view: GrafoView, id_goal: str) -> tuple[str, ...]:
    """Até três linhas do Goal, com o id à frente; sem plano aprovado o aviso vai no lugar da primeira."""
    linhas = placar_do_goal(view, id_goal).linhas_curtas()
    if not tem_plano_aprovado(view, id_goal):
        linhas = (AVISO_SEM_PLANO, *linhas[1:])
    return tuple(f"- [{em_uma_linha(id_goal)}] {em_uma_linha(linha)}" for linha in linhas)


def _secao_do_executor(alvo: NoGrafo, view: GrafoView) -> SecaoContexto | None:
    """A linha que diz ao executor por que não assume a Task: só quando o Goal dela não tem plano."""
    id_goal = goal_da_task(view, alvo.id)
    if id_goal is None or tem_plano_aprovado(view, id_goal):
        return None
    linha = (
        f"- Você não pode assumir esta Task: o Goal {em_uma_linha(id_goal)} não tem plano aprovado; "
        "um aprovar_plano (humano, ou árbitro se a política entregar) a destrava. "
        "Devolva a tarefa e peça a aprovação ao humano com abrir_questao"
    )
    return _secao(TITULO_DA_SECAO_DE_PLANO, (linha,))


def _goals_do_alvo(alvo: NoGrafo, view: GrafoView) -> tuple[str, ...]:
    """O Goal da Task; os Goals que a Sessão produz ou aos quais as Tasks dela pertencem, no máximo três."""
    if alvo.tipo == TipoNo.TASK:
        id_goal = goal_da_task(view, alvo.id)
        return (id_goal,) if id_goal is not None else ()
    if alvo.tipo != TipoNo.SESSAO:
        return ()
    produzidos = [a.destino_id for a in view.obter_arestas_saida(alvo.id, TipoAresta.PRODUZ)]
    goals = {id_no for id_no in produzidos if _eh_do_tipo(view, id_no, TipoNo.GOAL)}
    goals.update(
        id_goal
        for id_no in produzidos
        if _eh_do_tipo(view, id_no, TipoNo.TASK) and (id_goal := goal_da_task(view, id_no)) is not None
    )
    return tuple(sorted(goals))[:MAXIMO_DE_GOALS_NA_SESSAO]


def _eh_do_tipo(view: GrafoView, id_no: str, tipo: TipoNo) -> bool:
    """O nó existe e é do tipo."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == tipo


def _secao(titulo: str, linhas: tuple[str, ...]) -> SecaoContexto:
    """A seção com a retenção alta, logo depois das restrições."""
    return SecaoContexto(
        titulo=titulo,
        linhas=linhas,
        ordem_exibicao=ORDEM_DE_EXIBICAO_DO_ESCOPO,
        prioridade_retencao=PrioridadeRetencao.ESCOPO,
    )
