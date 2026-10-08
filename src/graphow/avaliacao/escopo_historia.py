"""A história de um Goal no log: quando cada Task nasceu e começou, onde o plano estava e como as criações se agrupam em lotes.

O plano aprovado não existe no log pré-1.5.0. Aproxima-se, como na seção 7 da
proposta, pelo primeiro momento em que uma Task do Goal foi para `em_andamento`:
as Tasks que já existiam ali são o plano combinado. O lote de criação é o agrupamento
em que o planejador ou o humano abriu Tasks de uma vez; o log grava um carimbo por
chamada (de 8 a 60 s entre Tasks do mesmo lote), por isso o lote não é "o mesmo
segundo" e sim o mesmo autor sem pausa maior que `JANELA_DO_LOTE_SEGUNDOS`.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime

from graphow.avaliacao.corpus_escopo import CorpusEscopo
from graphow.avaliacao.escopo_vista import VistaIndexada
from graphow.core.events import EventoLog, TipoEvento
from graphow.core.models import NoGrafo
from graphow.core.types import StatusTask
from graphow.projection.decomposicao import tarefas_da_decomposicao

JANELA_DO_LOTE_SEGUNDOS: float = 120.0
SEGUNDOS_POR_HORA: float = 3600.0


@dataclass(frozen=True)
class TaskHistorica:
    """Uma Task do Goal: quem a criou, quando, e quando saiu de `pendente` pela primeira vez."""

    id: str
    seq: int
    autor: str
    papel: str
    momento: str
    inicio_seq: int | None
    inicio_momento: str | None

    def comecou_depois_de(self, seq: int) -> bool:
        """A Task ainda não tinha saído de `pendente` no `seq` dado."""
        return self.inicio_seq is None or self.inicio_seq > seq


@dataclass(frozen=True)
class LoteDeCriacao:
    """As Tasks que um mesmo autor abriu em sequência e o fim da escrita da última delas."""

    tasks: tuple[str, ...]
    autor: str
    seq_fim: int
    momento_fim: str


@dataclass(frozen=True)
class HistoriaDoGoal:
    """O Goal no log: o plano aproximado, as Tasks e os lotes de criação depois do plano."""

    id_goal: str
    seq_do_plano: int
    tasks: tuple[TaskHistorica, ...]
    lotes: tuple[LoteDeCriacao, ...]

    @property
    def plano(self) -> tuple[TaskHistorica, ...]:
        """As Tasks que existiam quando o trabalho começou."""
        return tuple(task for task in self.tasks if task.seq <= self.seq_do_plano)

    @property
    def depois_do_plano(self) -> tuple[TaskHistorica, ...]:
        """As Tasks criadas depois do plano."""
        return tuple(task for task in self.tasks if task.seq > self.seq_do_plano)

    def task(self, id_task: str) -> TaskHistorica:
        """A Task pelo identificador."""
        return next(task for task in self.tasks if task.id == id_task)


def historia_do_goal(corpus: CorpusEscopo, id_goal: str) -> HistoriaDoGoal:
    """Extrai do corpus as Tasks, o plano aproximado e os lotes de criação do Goal."""
    nos = tarefas_da_decomposicao(VistaIndexada(corpus.estado), id_goal)
    inicios = _primeiras_saidas_de_pendente(corpus.eventos, frozenset(no.id for no in nos))
    tasks = tuple(sorted((_task_historica(no, inicios) for no in nos), key=lambda task: task.seq))
    seq_do_plano = min(inicio[0] for inicio in inicios.values())
    lotes = _lotes_de_criacao([task for task in tasks if task.seq > seq_do_plano], corpus.eventos)
    return HistoriaDoGoal(id_goal=id_goal, seq_do_plano=seq_do_plano, tasks=tasks, lotes=lotes)


def horas_entre(inicio: str, fim: str) -> float:
    """As horas de `inicio` a `fim`, dois carimbos ISO do log."""
    return (datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)).total_seconds() / SEGUNDOS_POR_HORA


def _primeiras_saidas_de_pendente(
    eventos: tuple[EventoLog, ...], ids: frozenset[str]
) -> dict[str, tuple[int, str]]:
    """Por Task, o `seq` e o carimbo da primeira escrita de `status` diferente de `pendente`."""
    inicios: dict[str, tuple[int, str]] = {}
    for evento in eventos:
        id_no = _task_que_saiu_de_pendente(evento, ids)
        if id_no is not None and id_no not in inicios:
            inicios[id_no] = (evento.seq, evento.timestamp_utc)
    return inicios


def _task_que_saiu_de_pendente(evento: EventoLog, ids: frozenset[str]) -> str | None:
    """O id da Task do Goal que o evento tira de `pendente`; None para qualquer outro evento."""
    if evento.tipo_evento is not TipoEvento.NO_ATUALIZADO:
        return None
    status = evento.payload.get("propriedades", {}).get("status")
    id_no = str(evento.payload.get("id"))
    saiu = status is not None and status != StatusTask.PENDENTE.value
    return id_no if saiu and id_no in ids else None


def _task_historica(no: NoGrafo, inicios: dict[str, tuple[int, str]]) -> TaskHistorica:
    """A Task como a história a lê."""
    inicio = inicios.get(no.id)
    return TaskHistorica(
        id=no.id,
        seq=no.ordem.seq_criacao,
        autor=no.proveniencia.autor,
        papel=no.proveniencia.papel,
        momento=no.metadados.criado_em,
        inicio_seq=inicio[0] if inicio else None,
        inicio_momento=inicio[1] if inicio else None,
    )


def _lotes_de_criacao(tasks: list[TaskHistorica], eventos: tuple[EventoLog, ...]) -> tuple[LoteDeCriacao, ...]:
    """Agrupa as Tasks em ordem de criação: mesmo autor e pausa de até `JANELA_DO_LOTE_SEGUNDOS`."""
    grupos: list[list[TaskHistorica]] = []
    for task in tasks:
        if grupos and _continua_o_lote(grupos[-1][-1], task):
            grupos[-1].append(task)
        else:
            grupos.append([task])
    seqs = [evento.seq for evento in eventos]
    return tuple(_lote(grupo, eventos, seqs) for grupo in grupos)


def _continua_o_lote(anterior: TaskHistorica, task: TaskHistorica) -> bool:
    """A Task é do mesmo autor da anterior e veio dentro da janela."""
    pausa = horas_entre(anterior.momento, task.momento) * SEGUNDOS_POR_HORA
    return task.autor == anterior.autor and pausa <= JANELA_DO_LOTE_SEGUNDOS


def _lote(grupo: list[TaskHistorica], eventos: tuple[EventoLog, ...], seqs: list[int]) -> LoteDeCriacao:
    """O lote com o fim da escrita da última Task: o último evento do mesmo autor e carimbo que a segue."""
    posicao = bisect_left(seqs, grupo[-1].seq)
    ultimo = eventos[posicao]
    while posicao + 1 < len(eventos) and _mesma_escrita(ultimo, eventos[posicao + 1]):
        posicao += 1
    fim = eventos[posicao]
    return LoteDeCriacao(
        tasks=tuple(task.id for task in grupo), autor=grupo[-1].autor, seq_fim=fim.seq, momento_fim=fim.timestamp_utc
    )


def _mesma_escrita(a: EventoLog, b: EventoLog) -> bool:
    """Os dois eventos saíram da mesma escrita: mesmo autor e mesmo carimbo."""
    return a.autor == b.autor and a.timestamp_utc == b.timestamp_utc
