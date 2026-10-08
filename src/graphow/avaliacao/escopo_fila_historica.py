"""A fila do histórico (C): o que a ordem antiga serviu e o que a ordem nova serviria, momento a momento.

Em cada momento em que uma Task do Goal saiu de `pendente`, o estado logo antes
dela diz quantas Tasks do plano ainda esperavam e se a escolhida era emergente.
Para o mesmo conjunto de pendentes liberadas compara-se a posição da melhor Task
do plano na ordem antiga (status, id) com a da fila real de hoje (status, faixa, id).
Os ids do corpus são hashes anonimizados, então a ordem por id do corpus é
arbitrária em relação ao plano: a posição antiga é a de um sorteio, não a do log real.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from graphow.avaliacao.corpus_escopo import CorpusEscopo
from graphow.avaliacao.escopo_historia import HistoriaDoGoal, TaskHistorica
from graphow.avaliacao.escopo_sintetico import EscolhaDoMotivo, Sobreposicao, sobrepor
from graphow.avaliacao.escopo_vista import CursorDoCorpus, VistaIndexada
from graphow.core.types import StatusTask
from graphow.projection.classificacao_escopo import BaseDoPlano, ClasseDeEscopo, ClassificadorDeEscopo
from graphow.projection.custo_de_escopo import CLASSES_EMERGENTES
from graphow.projection.decomposicao import tarefas_da_decomposicao
from graphow.projection.faixas_da_fila import FAIXA_DO_QUE_O_PLANO_PEDE
from graphow.projection.fila_trabalho import FilaDeTrabalho, TarefaExecutavel
from graphow.projection.graph_view import GrafoView


@dataclass(frozen=True)
class MomentoDaFila:
    """Uma Task que saiu de `pendente`: a classe dela, o plano que esperava e onde o plano ficava na fila."""

    seq: int
    escolhida: str
    classe: str
    emergente: bool
    faixa: int | None
    pendentes_liberadas: int
    plano_pendente: int
    plano_liberado: int
    posicao_antiga: int | None
    posicao_nova: int | None

    @property
    def emergente_com_plano_pendente(self) -> bool:
        """Escolheu emergente enquanto o plano esperava."""
        return self.emergente and self.plano_pendente > 0

    @property
    def emergente_com_plano_liberado(self) -> bool:
        """Escolheu emergente enquanto havia Task do plano pronta para ser servida."""
        return self.emergente and self.plano_liberado > 0


@dataclass(frozen=True)
class FilaDoGoal:
    """Os momentos do Goal e as médias de posição do plano na ordem antiga e na nova."""

    id_goal: str
    momentos: tuple[MomentoDaFila, ...]

    @property
    def emergentes_escolhidas(self) -> int:
        """Quantas saídas de `pendente` foram de Task emergente."""
        return sum(1 for momento in self.momentos if momento.emergente)

    @property
    def com_plano_pendente(self) -> int:
        """Emergente escolhida com Task do plano ainda `pendente`, liberada ou não."""
        return sum(1 for momento in self.momentos if momento.emergente_com_plano_pendente)

    @property
    def com_plano_liberado(self) -> int:
        """Emergente escolhida com Task do plano `pendente` e pronta para a fila."""
        return sum(1 for momento in self.momentos if momento.emergente_com_plano_liberado)

    @property
    def pedidas_pelo_plano(self) -> int:
        """Das emergentes escolhidas com plano pendente, as que uma Task do plano pedia (faixa 2 da fila)."""
        return sum(1 for m in self.momentos if m.emergente_com_plano_pendente and m.faixa == FAIXA_DO_QUE_O_PLANO_PEDE)

    @property
    def momentos_com_plano_liberado(self) -> int:
        """Em quantos momentos a fila tinha Task do plano `pendente` e liberada (a escolhida inclusive)."""
        return sum(1 for momento in self.momentos if momento.posicao_antiga is not None)

    @property
    def pendentes_por_momento(self) -> float:
        """A média de Tasks `pendente` e liberadas que a fila tinha a cada saída de `pendente`."""
        return sum(m.pendentes_liberadas for m in self.momentos) / len(self.momentos) if self.momentos else 0.0

    def posicao_media(self, *, so_emergentes: bool = False) -> tuple[float, float] | None:
        """(antiga, nova) da melhor Task do plano, nos momentos em que o plano tinha pendente liberada."""
        com_plano = [m for m in self.momentos if m.posicao_antiga is not None and (m.emergente or not so_emergentes)]
        if not com_plano:
            return None
        antiga = sum(m.posicao_antiga or 0 for m in com_plano) / len(com_plano)
        nova = sum(m.posicao_nova or 0 for m in com_plano) / len(com_plano)
        return antiga, nova


def medir_fila(corpus: CorpusEscopo, historia: HistoriaDoGoal) -> FilaDoGoal:
    """Cada saída de `pendente` do Goal a partir do plano, vista no estado logo antes dela."""
    cursor = CursorDoCorpus(corpus)
    saidas = sorted(
        (task for task in historia.tasks if task.inicio_seq is not None and task.inicio_seq >= historia.seq_do_plano),
        key=lambda task: task.inicio_seq or 0,
    )
    momentos = tuple(_momento(cursor, historia, task) for task in saidas)
    return FilaDoGoal(id_goal=historia.id_goal, momentos=momentos)


def _momento(cursor: CursorDoCorpus, historia: HistoriaDoGoal, task: TaskHistorica) -> MomentoDaFila:
    """O momento em que a Task saiu de `pendente`, lido no estado do evento anterior."""
    seq = task.inicio_seq or 0
    sobreposicao = Sobreposicao(historia.seq_do_plano, motivo=EscolhaDoMotivo.NENHUM)
    view = VistaIndexada(sobrepor(cursor.estado_ate(seq - 1), historia.id_goal, sobreposicao))
    classificador = ClassificadorDeEscopo(view, BaseDoPlano.REFERENCIA)
    classe = classificador.classe_da(task.id)
    fila = FilaDeTrabalho(view).proximas_tarefas(historia.id_goal)
    posicoes = _posicoes_do_plano(fila)
    return MomentoDaFila(
        seq=seq,
        escolhida=task.id,
        classe=classe.value,
        emergente=classe in CLASSES_EMERGENTES,
        faixa=next((t.faixa for t in fila if t.id == task.id), None),
        pendentes_liberadas=sum(1 for t in fila if t.status == StatusTask.PENDENTE.value),
        plano_pendente=_plano_pendente(view, classificador, (historia.id_goal, task.id)),
        plano_liberado=sum(1 for t in fila if _e_plano_pendente(t) and t.id != task.id),
        posicao_antiga=posicoes[0],
        posicao_nova=posicoes[1],
    )


def _e_plano_pendente(tarefa: TarefaExecutavel) -> bool:
    """A tarefa da fila é do plano e ainda não começou."""
    return tarefa.escopo == ClasseDeEscopo.PLANO.value and tarefa.status == StatusTask.PENDENTE.value


def _posicoes_do_plano(fila: Sequence[TarefaExecutavel]) -> tuple[int | None, int | None]:
    """A posição (1 em diante) da melhor Task do plano entre as pendentes: na ordem antiga e na da fila."""
    pendentes = [tarefa for tarefa in fila if tarefa.status == StatusTask.PENDENTE.value]
    if not any(_e_plano_pendente(tarefa) for tarefa in pendentes):
        return None, None
    return _posicao(sorted(pendentes, key=lambda tarefa: tarefa.id)), _posicao(pendentes)


def _posicao(ordenadas: Sequence[TarefaExecutavel]) -> int:
    """A posição da primeira Task do plano na sequência, contada de 1."""
    return next(indice for indice, tarefa in enumerate(ordenadas, start=1) if _e_plano_pendente(tarefa))


def _plano_pendente(view: GrafoView, classificador: ClassificadorDeEscopo, ids: tuple[str, str]) -> int:
    """Quantas Tasks do plano, fora a escolhida, estavam `pendente`, liberadas ou não."""
    id_goal, escolhida = ids
    nos = tarefas_da_decomposicao(view, id_goal)
    pendentes = (no for no in nos if no.obter_propriedade("status", StatusTask.PENDENTE.value) == StatusTask.PENDENTE.value)
    return sum(1 for no in pendentes if no.id != escolhida and classificador.classe_da(no.id) == ClasseDeEscopo.PLANO)
