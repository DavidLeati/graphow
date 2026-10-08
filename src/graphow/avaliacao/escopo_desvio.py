"""Os eventos de desvio do histórico (A) e a antecedência do alerta (B), pelo placar real de escopo.

Percorre os lotes de criação de Task depois do plano, monta o placar com o estado
até o fim de cada lote e conta um evento quando algum gatilho dispara; vários
gatilhos no mesmo lote são um evento só. Depois de cada evento simula a cadência:
uma resposta humana de desvio, sem raiz, logo após o lote, que zera K e M. A
antecedência pergunta, para cada evento, se as Tasks emergentes que o alerta cobre
ainda não tinham começado quando ele soou, e em quantas horas a primeira delas começou.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from graphow.avaliacao.corpus_escopo import CorpusEscopo
from graphow.avaliacao.escopo_historia import HistoriaDoGoal, LoteDeCriacao, horas_entre
from graphow.avaliacao.escopo_sintetico import EscolhaDoMotivo, Sobreposicao, resposta_humana_sem_raiz, sobrepor
from graphow.avaliacao.escopo_vista import CursorDoCorpus, VistaIndexada
from graphow.projection.custo_de_escopo import TaskDoEscopo, tasks_desde_a_referencia
from graphow.projection.graph_view import GrafoView
from graphow.projection.placar_escopo import (
    GATILHO_POR_RAIZ,
    GatilhoDeDesvio,
    LimiaresDeDesvio,
    gatilhos_disparados,
    montar_placar,
)

LIMIARES_DA_PROPOSTA: LimiaresDeDesvio = LimiaresDeDesvio(por_raiz=3, por_goal=5)
TODOS_OS_GATILHOS: frozenset[str] = frozenset({"raiz", "goal", "inanicao"})
SO_O_GATILHO_POR_RAIZ: frozenset[str] = frozenset({GATILHO_POR_RAIZ})


@dataclass(frozen=True)
class ConfiguracaoDoDesvio:
    """Como medir: os limiares, que gatilhos contam e qual Decision vira a `motivada_por` da Task.

    A seção 7 da proposta mediu só o K por raiz; o desenho final soma o M por Goal e
    a inanição do plano. Medir os dois separa o que reproduz o texto do que o
    desenho acrescentou.
    """

    limiares: LimiaresDeDesvio = LIMIARES_DA_PROPOSTA
    motivo: EscolhaDoMotivo = EscolhaDoMotivo.MAIS_RECENTE
    gatilhos: frozenset[str] = TODOS_OS_GATILHOS
    com_resposta: bool = True


@dataclass(frozen=True)
class EventoDeDesvio:
    """Um lote em que algum gatilho disparou: onde, quais gatilhos e o que o alerta cobria."""

    lote: int
    seq: int
    momento: str
    tasks_no_lote: int
    gatilhos: tuple[str, ...]
    cobertas: int
    nao_comecadas: int
    horas_ate_a_primeira_execucao: float | None

    @property
    def chegou_antes_do_trabalho(self) -> bool:
        """Ao menos uma Task coberta pelo alerta ainda não tinha começado."""
        return self.nao_comecadas > 0


@dataclass(frozen=True)
class DesvioDoGoal:
    """Os eventos de desvio de um Goal sob os limiares K e M, e quantos lotes foram avaliados."""

    id_goal: str
    configuracao: ConfiguracaoDoDesvio
    lotes_avaliados: int
    eventos: tuple[EventoDeDesvio, ...]

    @property
    def total(self) -> int:
        """Quantos eventos de desvio houve."""
        return len(self.eventos)

    @property
    def antes_do_trabalho(self) -> int:
        """Em quantos eventos o alerta chegou antes de toda a execução das Tasks que cobria."""
        return sum(1 for evento in self.eventos if evento.chegou_antes_do_trabalho)

    @property
    def cobertas(self) -> int:
        """Quantas Tasks emergentes os alertas cobriam, somadas por evento."""
        return sum(evento.cobertas for evento in self.eventos)

    @property
    def nao_comecadas(self) -> int:
        """Dessas, quantas ainda não tinham começado quando o alerta soou."""
        return sum(evento.nao_comecadas for evento in self.eventos)

    @property
    def horas_ate_a_primeira_execucao(self) -> tuple[float, ...]:
        """Por evento com Task ainda não iniciada que depois começou, as horas até a primeira delas."""
        return tuple(e.horas_ate_a_primeira_execucao for e in self.eventos if e.horas_ate_a_primeira_execucao is not None)

    def por_gatilho(self) -> Mapping[str, int]:
        """Em quantos eventos cada tipo de gatilho esteve entre os disparados."""
        contagem: dict[str, int] = {}
        for evento in self.eventos:
            for tipo in evento.gatilhos:
                contagem[tipo] = contagem.get(tipo, 0) + 1
        return dict(sorted(contagem.items()))


def medir_desvio(
    corpus: CorpusEscopo, historia: HistoriaDoGoal, configuracao: ConfiguracaoDoDesvio = ConfiguracaoDoDesvio()
) -> DesvioDoGoal:
    """Os eventos de desvio do Goal, com a resposta humana simulada depois de cada um."""
    simulacao = _Simulacao(CursorDoCorpus(corpus), historia, configuracao)
    eventos = [evento for indice, lote in enumerate(historia.lotes) if (evento := simulacao.avaliar(indice, lote))]
    return DesvioDoGoal(
        id_goal=historia.id_goal,
        configuracao=configuracao,
        lotes_avaliados=len(historia.lotes),
        eventos=tuple(eventos),
    )


class _Alerta(NamedTuple):
    """Os gatilhos que dispararam num lote e as Tasks emergentes que eles cobriam."""

    disparados: tuple[GatilhoDeDesvio, ...]
    cobertas: tuple[TaskDoEscopo, ...]


class _Simulacao:
    """Avança o histórico lote a lote e guarda as respostas que o humano teria dado."""

    def __init__(self, cursor: CursorDoCorpus, historia: HistoriaDoGoal, configuracao: ConfiguracaoDoDesvio) -> None:
        self._cursor: CursorDoCorpus = cursor
        self._historia: HistoriaDoGoal = historia
        self._configuracao: ConfiguracaoDoDesvio = configuracao
        self._respostas: list[Mapping[str, Any]] = []

    def avaliar(self, indice: int, lote: LoteDeCriacao) -> EventoDeDesvio | None:
        """O evento do lote, ou None quando nenhum gatilho dispara; o evento zera a contagem."""
        view = self._vista_do_lote(lote)
        placar = montar_placar(view, self._historia.id_goal, self._configuracao.limiares)
        disparados = tuple(g for g in gatilhos_disparados(placar) if g.tipo in self._configuracao.gatilhos)
        if not disparados:
            return None
        alerta = _Alerta(disparados, self._cobertas(view, disparados))
        evento = self._evento(indice, lote, alerta)
        if self._configuracao.com_resposta:
            self._respostas.append(resposta_humana_sem_raiz(lote.seq_fim))
        return evento

    def _vista_do_lote(self, lote: LoteDeCriacao) -> GrafoView:
        """O estado no fim do lote, com o plano, a `motivada_por` e as respostas até agora."""
        estado = self._cursor.estado_ate(lote.seq_fim)
        sobreposicao = Sobreposicao(self._historia.seq_do_plano, tuple(self._respostas), self._configuracao.motivo)
        return VistaIndexada(sobrepor(estado, self._historia.id_goal, sobreposicao))

    def _corte(self) -> int:
        """O `seq` desde o qual o contador conta: a última resposta, ou o plano."""
        return int(self._respostas[-1]["seq"]) if self._respostas else self._historia.seq_do_plano

    def _cobertas(self, view: GrafoView, disparados: tuple[GatilhoDeDesvio, ...]) -> tuple[TaskDoEscopo, ...]:
        """As emergentes que os gatilhos disparados contavam: as da raiz (K) ou as do Goal (M, inanição)."""
        raizes = {g.raiz for g in disparados if g.tipo == GATILHO_POR_RAIZ}
        do_goal = any(g.tipo != GATILHO_POR_RAIZ for g in disparados)
        emergentes = [t for t in tasks_desde_a_referencia(view, self._historia.id_goal) if t.eh_emergente]
        recentes = [t for t in emergentes if t.seq > self._corte()]
        return tuple(t for t in recentes if t.raiz in raizes or (do_goal and not t.humana))

    def _evento(self, indice: int, lote: LoteDeCriacao, alerta: "_Alerta") -> EventoDeDesvio:
        """O evento com a antecedência: as cobertas que só começam depois do alerta."""
        disparados, cobertas = alerta.disparados, alerta.cobertas
        ainda_nao = [t for t in cobertas if self._historia.task(t.id).comecou_depois_de(lote.seq_fim)]
        return EventoDeDesvio(
            lote=indice,
            seq=lote.seq_fim,
            momento=lote.momento_fim,
            tasks_no_lote=len(lote.tasks),
            gatilhos=tuple(sorted({g.tipo for g in disparados})),
            cobertas=len(cobertas),
            nao_comecadas=len(ainda_nao),
            horas_ate_a_primeira_execucao=self._horas_ate_a_primeira(lote, ainda_nao),
        )

    def _horas_ate_a_primeira(self, lote: LoteDeCriacao, ainda_nao: list[TaskDoEscopo]) -> float | None:
        """Das cobertas que não tinham começado, as horas até a primeira que de fato começou; None se nenhuma."""
        inicios = [self._historia.task(t.id).inicio_momento for t in ainda_nao]
        horas = [horas_entre(lote.momento_fim, momento) for momento in inicios if momento is not None]
        return min(horas) if horas else None
