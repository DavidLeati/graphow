"""O placar de escopo de um Goal: o plano, o desvio desde a referência e os gatilhos K e M.

A projeção só lê o grafo. Os limiares chegam de quem chama, que os resolve da
política (`kernel.politica_governanca.resolver_politica_do_no`): o placar não
conhece política. K diz qual decisão revisar (uma raiz passou de K Tasks
emergentes desde a referência ou desde a última resposta humana àquela raiz); M
pega a expansão fragmentada (emergentes não-humanas do Goal desde o último zero,
ou o plano parado enquanto o emergente anda). Só a aprovação de plano e a
resposta de desvio feitas por humano zeram; as do árbitro aparecem e não zeram.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.escopo import ACAO_VEREDITO_DE_ESCOPO, CAMPO_FASE, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.orquestracao import CAMPO_ACAO, ler_texto
from graphow.core.types import PapelAutor, StatusTask, TipoAresta
from graphow.projection.apresentacao_do_placar import (
    linhas_curtas_do_placar,
    linhas_de_desvio,
    linhas_do_placar,
    placar_em_dicionario,
)
from graphow.projection.classificacao_escopo import ClasseDeEscopo
from graphow.projection.custo_de_escopo import (
    SEM_REFERENCIA,
    CustoDaRaiz,
    TaskDoEscopo,
    custo_por_raiz,
    seq_da_referencia,
    tasks_desde_a_referencia,
)
from graphow.projection.escopo_plano import (
    VersaoDoPlano,
    planos_do_goal,
    plano_de_referencia,
    seq_do_ultimo_zero,
    tasks_do_plano,
)
from graphow.projection.graph_view import GrafoView

GATILHO_POR_RAIZ: str = "raiz"
GATILHO_POR_GOAL: str = "goal"
GATILHO_INANICAO: str = "inanicao"
CLASSES_SEMPRE_NO_PLACAR: tuple[ClasseDeEscopo, ...] = (
    ClasseDeEscopo.B1,
    ClasseDeEscopo.B3,
    ClasseDeEscopo.CORRECAO,
    ClasseDeEscopo.INTEGRACAO,
    ClasseDeEscopo.REVERSAO,
)


@dataclass(frozen=True)
class LimiaresDeDesvio:
    """K (por raiz) e M (por Goal), como a política os resolveu para o Goal."""

    por_raiz: int
    por_goal: int


@dataclass(frozen=True)
class RespostaDeDesvio:
    """Uma resposta ao placar: quem, com que papel, a que raiz (None é o Goal) e o que disse."""

    seq: int
    respondido_por: str
    papel: str
    raiz: str | None
    resposta: str

    @property
    def do_arbitro(self) -> bool:
        """O árbitro dispensou o alerta; o placar marca e a resposta não zera nada."""
        return self.papel == PapelAutor.ARBITRO.value

    @property
    def eh_humana(self) -> bool:
        """Só a resposta humana zera o contador."""
        return self.papel == PapelAutor.HUMANO.value


@dataclass(frozen=True)
class ResumoDoPlano:
    """O plano de referência: quantas Tasks, quantas concluídas e as que nunca começaram, por fase."""

    total: int
    concluidas: int
    sem_comecar: tuple[str, ...]
    sem_comecar_por_fase: Mapping[str, int]


@dataclass(frozen=True)
class RaizDoPlacar:
    """Uma raiz com o custo dela e o que os gatilhos dizem: contador de K, se passou e se falta o veredito."""

    custo: CustoDaRaiz
    contador_k: int
    passou_de_k: bool
    veredito_pendente: bool

    @property
    def raiz(self) -> str:
        """O identificador da raiz."""
        return self.custo.raiz

    @property
    def emergentes(self) -> int:
        """As Tasks B3 e sem ligação da raiz desde a referência."""
        return len(self.custo.emergentes)


@dataclass(frozen=True)
class GatilhoDeDesvio:
    """Um gatilho avaliado: qual, sobre que raiz, a contagem contra o limiar e se disparou."""

    tipo: str
    raiz: str | None
    contagem: int
    limiar: int
    disparou: bool


@dataclass(frozen=True)
class PlacarDeEscopo:
    """Tudo que o placar mostra de um Goal, calculado do grafo e dos limiares recebidos."""

    id_goal: str
    referencia: VersaoDoPlano | None
    versoes_do_arbitro: tuple[VersaoDoPlano, ...]
    plano: ResumoDoPlano
    contagem_por_classe: Mapping[str, int]
    raizes: tuple[RaizDoPlacar, ...]
    cadeia_mais_longa: int
    respostas_de_desvio: tuple[RespostaDeDesvio, ...]
    emergentes_para_m: int
    gatilhos: tuple[GatilhoDeDesvio, ...]
    sem_veredito: tuple[str, ...]
    limiares: LimiaresDeDesvio

    @property
    def raiz_que_mais_gerou(self) -> RaizDoPlacar | None:
        """A raiz com mais emergentes; None quando nenhuma gerou."""
        topo = self.raizes[0] if self.raizes else None
        return topo if topo is not None and topo.emergentes > 0 else None

    def em_dicionario(self) -> dict[str, Any]:
        """O placar como dicionário simples, para a web e o MCP."""
        return placar_em_dicionario(self)

    def linhas(self) -> tuple[str, ...]:
        """As cinco linhas da seção 4.7 da proposta."""
        return linhas_do_placar(self)

    def linhas_curtas(self) -> tuple[str, ...]:
        """O placar em até três linhas, para a vista de Task e de Sessão."""
        return linhas_curtas_do_placar(self)

    def linhas_de_desvio(self) -> tuple[str, ...]:
        """Os gatilhos disparados e as respostas de desvio, para a cadência `desvio`."""
        return linhas_de_desvio(self)


def montar_placar(view: GrafoView, id_goal: str, limiares: LimiaresDeDesvio) -> PlacarDeEscopo:
    """O placar do Goal contra o plano de referência, com os limiares recebidos."""
    tasks = tasks_desde_a_referencia(view, id_goal)
    respostas = respostas_de_desvio(view, id_goal)
    base_de_k = _BaseDeK(seq_da_referencia(view, id_goal), respostas, limiares.por_raiz)
    raizes = tuple(
        sorted(
            (_raiz_do_placar(view, custo, base_de_k) for custo in custo_por_raiz(view, tasks)),
            key=lambda raiz: (-raiz.emergentes, raiz.raiz),
        )
    )
    plano = _resumo_do_plano(view, id_goal)
    contagem_m, saidas_de_pendente = _contagem_para_m(view, id_goal, tasks)
    return PlacarDeEscopo(
        id_goal=id_goal,
        referencia=plano_de_referencia(view, id_goal),
        versoes_do_arbitro=_versoes_do_arbitro(view, id_goal),
        plano=plano,
        contagem_por_classe=_contagem_por_classe(tasks),
        raizes=raizes,
        cadeia_mais_longa=max((raiz.custo.profundidade for raiz in raizes), default=0),
        respostas_de_desvio=respostas,
        emergentes_para_m=contagem_m,
        gatilhos=_avaliar_gatilhos(raizes, (contagem_m, saidas_de_pendente, bool(plano.sem_comecar)), limiares),
        sem_veredito=tuple(raiz.raiz for raiz in raizes if raiz.veredito_pendente),
        limiares=limiares,
    )


def gatilhos_disparados(placar: PlacarDeEscopo) -> tuple[GatilhoDeDesvio, ...]:
    """Os gatilhos K, M e de inanição que dispararam; vazio quando o desvio cabe nos limiares."""
    return tuple(gatilho for gatilho in placar.gatilhos if gatilho.disparou)


def respostas_de_desvio(view: GrafoView, id_goal: str) -> tuple[RespostaDeDesvio, ...]:
    """As respostas de desvio do Goal, em ordem de `seq`; entrada malformada é ignorada."""
    no = view.obter_no(id_goal)
    bruto = no.obter_propriedade(CAMPO_RESPOSTAS_DE_DESVIO) if no is not None else None
    itens = bruto if isinstance(bruto, (list, tuple)) else ()
    respostas = (_ler_resposta(item) for item in itens)
    return tuple(sorted((r for r in respostas if r is not None), key=lambda r: r.seq))


def _ler_resposta(item: Any) -> RespostaDeDesvio | None:
    """Uma entrada de `respostas_de_desvio`, ou None quando falta `seq` inteiro ou o papel não é de agente nem humano."""
    if not isinstance(item, Mapping):
        return None
    seq, papel = item.get("seq"), item.get("papel")
    if not isinstance(seq, int) or isinstance(seq, bool) or papel not in (PapelAutor.HUMANO.value, PapelAutor.ARBITRO.value):
        return None
    raiz = item.get("raiz")
    return RespostaDeDesvio(
        seq=seq,
        respondido_por=str(item.get("respondido_por", "")),
        papel=papel,
        raiz=raiz if isinstance(raiz, str) and raiz else None,
        resposta=str(item.get("resposta", "")),
    )


@dataclass(frozen=True)
class _BaseDeK:
    """O que K precisa além da raiz: o `seq` da referência, as respostas de desvio e o limiar."""

    corte: int
    respostas: tuple[RespostaDeDesvio, ...]
    limiar: int


def _raiz_do_placar(view: GrafoView, custo: CustoDaRaiz, base: _BaseDeK) -> RaizDoPlacar:
    """Avalia K na raiz: conta os emergentes desde a referência ou a última resposta humana a ela.

    A resposta humana sem raiz vale para todas: quem responde viu o placar inteiro.
    """
    seqs_das_respostas = [r.seq for r in base.respostas if r.eh_humana and r.raiz in (None, custo.raiz)]
    corte = max([base.corte, *seqs_das_respostas])
    contadas = [task for task in custo.emergentes if task.seq > corte]
    passou = len(contadas) > base.limiar
    pendente = passou and not _tem_veredito(view, custo.raiz, contadas[base.limiar].seq)
    return RaizDoPlacar(custo=custo, contador_k=len(contadas), passou_de_k=passou, veredito_pendente=pendente)


def _tem_veredito(view: GrafoView, raiz: str, depois_de: int) -> bool:
    """Há Evidence de veredito de escopo com `deriva_de` para a raiz, criada depois da Task que a fez passar de K."""
    origens = (view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(raiz, TipoAresta.DERIVA_DE))
    return any(
        no is not None
        and ler_texto(no.propriedades, CAMPO_ACAO) == ACAO_VEREDITO_DE_ESCOPO
        and no.ordem.seq_criacao > depois_de
        for no in origens
    )


def _contagem_para_m(view: GrafoView, id_goal: str, tasks: tuple[TaskDoEscopo, ...]) -> tuple[int, int]:
    """Quantas emergentes não-humanas vieram desde o último zero e quantas delas já saíram de `pendente`."""
    zero = seq_do_ultimo_zero(view, id_goal)
    corte = zero if zero > 0 else SEM_REFERENCIA
    contadas = [task for task in tasks if task.eh_emergente and not task.humana and task.seq > corte]
    return len(contadas), sum(1 for task in contadas if task.status != StatusTask.PENDENTE.value)


def _avaliar_gatilhos(
    raizes: tuple[RaizDoPlacar, ...],
    para_m: tuple[int, int, bool],
    limiares: LimiaresDeDesvio,
) -> tuple[GatilhoDeDesvio, ...]:
    """K de cada raiz que gerou emergente, M do Goal e a inanição do plano."""
    contagem_m, saidas_de_pendente, plano_parado = para_m
    por_raiz = tuple(
        GatilhoDeDesvio(GATILHO_POR_RAIZ, raiz.raiz, raiz.contador_k, limiares.por_raiz, raiz.passou_de_k)
        for raiz in raizes
        if raiz.contador_k > 0
    )
    por_goal = GatilhoDeDesvio(GATILHO_POR_GOAL, None, contagem_m, limiares.por_goal, contagem_m > limiares.por_goal)
    inanicao = GatilhoDeDesvio(
        GATILHO_INANICAO, None, saidas_de_pendente, limiares.por_raiz, plano_parado and saidas_de_pendente > limiares.por_raiz
    )
    return (*por_raiz, por_goal, inanicao)


def _resumo_do_plano(view: GrafoView, id_goal: str) -> ResumoDoPlano:
    """O plano de referência em números; zerado quando nenhum humano aprovou plano."""
    referencia = plano_de_referencia(view, id_goal)
    if referencia is None:
        return ResumoDoPlano(total=0, concluidas=0, sem_comecar=(), sem_comecar_por_fase={})
    nos = [no for id_no in sorted(tasks_do_plano(view, id_goal, referencia)) if (no := view.obter_no(id_no))]
    status = {no.id: ler_texto(no.propriedades, "status") or StatusTask.PENDENTE.value for no in nos}
    sem_comecar = tuple(no.id for no in nos if status[no.id] == StatusTask.PENDENTE.value)
    fases: dict[str, int] = {}
    for no in nos:
        fase = ler_texto(no.propriedades, CAMPO_FASE)
        if no.id in sem_comecar and fase:
            fases[fase] = fases.get(fase, 0) + 1
    concluidas = sum(1 for valor in status.values() if valor == StatusTask.CONCLUIDO.value)
    return ResumoDoPlano(total=len(nos), concluidas=concluidas, sem_comecar=sem_comecar, sem_comecar_por_fase=dict(sorted(fases.items())))


def _versoes_do_arbitro(view: GrafoView, id_goal: str) -> tuple[VersaoDoPlano, ...]:
    """As versões do plano aprovadas pelo árbitro depois da referência."""
    referencia = plano_de_referencia(view, id_goal)
    base = referencia.versao if referencia is not None else 0
    return tuple(
        plano
        for plano in planos_do_goal(view, id_goal)
        if plano.papel == PapelAutor.ARBITRO.value and plano.versao > base
    )


def _contagem_por_classe(tasks: tuple[TaskDoEscopo, ...]) -> dict[str, int]:
    """Tasks desde a referência por classe: as cinco do placar sempre, as outras quando existem."""
    contagem = {classe.value: 0 for classe in CLASSES_SEMPRE_NO_PLACAR}
    for task in tasks:
        contagem[task.classe.value] = contagem.get(task.classe.value, 0) + 1
    return contagem
