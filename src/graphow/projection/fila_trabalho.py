"""Fila de trabalho: quais tarefas de uma sessão estão de fato executáveis agora.

Nenhuma consulta devolvia "tarefas executáveis". O reconhecimento sugerido pela
skill — buscar a Sessao e ler a vista dela — devolvia vizinhos ordenados por
identificador e sem status, e o agente precisava chamar `expandir_no` tarefa a
tarefa, gastando o orçamento que a vista deveria poupar. Ver achado A-07.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from graphow.core.models import NoGrafo
from graphow.core.types import StatusTask, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

PROFUNDIDADE_MAXIMA_DA_SESSAO: int = 32

ARESTAS_DE_ALCANCE: frozenset[TipoAresta] = frozenset(
    {TipoAresta.PRODUZ, TipoAresta.DECOMPOE}
)

# Uma tarefa concluída não volta para a fila; uma bloqueada aguarda o humano.
STATUS_FORA_DA_FILA: frozenset[str] = frozenset(
    {StatusTask.CONCLUIDO.value, StatusTask.BLOQUEADO.value}
)

# Ordem de atendimento: o que já está pronto para alguém olhar vem antes do que
# ainda nem começou. Dentro de cada faixa, o identificador mantém a ordem estável.
PRIORIDADE_POR_STATUS: Mapping[str, int] = {
    StatusTask.PRONTO_PARA_REVISAO.value: 0,
    StatusTask.EM_ANDAMENTO.value: 1,
    StatusTask.PENDENTE.value: 2,
}
PRIORIDADE_DE_STATUS_DESCONHECIDO: int = 9


class MotivoDeImpedimento(str, Enum):
    """Por que uma tarefa da sessão não está disponível agora."""

    CONCLUIDA = "concluida"
    DUVIDA_ABERTA = "duvida_aberta"
    DEPENDENCIA_PENDENTE = "dependencia_pendente"
    POSSE_DE_OUTRO = "posse_de_outro"


@dataclass(frozen=True)
class TarefaImpedida:
    """Tarefa fora da fila, com o motivo que a mantém de fora.

    Uma fila vazia sem explicação deixa o agente tão parado quanto a ausência de
    fila deixava: ele não sabe se deve esperar, escalar ou encerrar. Ver A-07.
    """

    id: str
    rotulo: str
    status: str
    motivo: MotivoDeImpedimento

    def em_dicionario(self) -> dict[str, object]:
        """Forma serializável para a resposta da ferramenta MCP."""
        return {
            "id": self.id,
            "rotulo": self.rotulo,
            "status": self.status,
            "motivo": self.motivo.value,
        }


@dataclass(frozen=True)
class TarefaExecutavel:
    """Tarefa liberada para trabalho, com o que o agente precisa para decidir."""

    id: str
    rotulo: str
    status: str
    criterio_pronto: str = ""
    depende_de: tuple[str, ...] = field(default_factory=tuple)

    def em_dicionario(self) -> dict[str, object]:
        """Forma serializável para a resposta da ferramenta MCP."""
        return {
            "id": self.id,
            "rotulo": self.rotulo,
            "status": self.status,
            "criterio_pronto": self.criterio_pronto,
            "depende_de": list(self.depende_de),
        }


class FilaDeTrabalho:
    """Consulta pura que ordena as tarefas prontas para execução em uma sessão."""

    def __init__(self, view: GrafoView, locks_ativos: Mapping[str, str] | None = None) -> None:
        self._view: GrafoView = view
        self._locks: Mapping[str, str] = dict(locks_ativos or {})

    def proximas_tarefas(self, id_sessao: str) -> tuple[TarefaExecutavel, ...]:
        """Tarefas da sessão com dependências cumpridas, sem dúvida aberta e sem posse."""
        candidatas = [
            no for no in self._coletar_tarefas_da_sessao(id_sessao) if self._esta_liberada(no)
        ]
        ordenadas = sorted(candidatas, key=self._chave_de_ordenacao)
        return tuple(self._descrever(no) for no in ordenadas)

    def tarefas_impedidas(self, id_sessao: str) -> tuple[TarefaImpedida, ...]:
        """Tarefas da sessão que não entraram na fila, cada uma com o seu motivo."""
        impedidas = [
            self._descrever_impedimento(no)
            for no in sorted(self._coletar_tarefas_da_sessao(id_sessao), key=lambda no: no.id)
            if not self._esta_liberada(no)
        ]
        return tuple(impedidas)

    def _descrever_impedimento(self, no: NoGrafo) -> TarefaImpedida:
        """Projeta a tarefa impedida com o primeiro motivo que a exclui."""
        status = str(no.obter_propriedade("status", StatusTask.PENDENTE.value))
        return TarefaImpedida(
            id=no.id, rotulo=no.rotulo, status=status, motivo=self._identificar_motivo(no, status)
        )

    def _identificar_motivo(self, no: NoGrafo, status: str) -> MotivoDeImpedimento:
        """Escolhe o motivo mais informativo entre os que se aplicam."""
        if status == StatusTask.CONCLUIDO.value:
            return MotivoDeImpedimento.CONCLUIDA
        if self._view.esta_bloqueada(no.id):
            return MotivoDeImpedimento.DUVIDA_ABERTA
        if no.id in self._locks:
            return MotivoDeImpedimento.POSSE_DE_OUTRO
        return MotivoDeImpedimento.DEPENDENCIA_PENDENTE

    def _chave_de_ordenacao(self, no: NoGrafo) -> tuple[int, str]:
        """Ordem estável por prioridade de status e, em empate, por identificador."""
        status = str(no.obter_propriedade("status", StatusTask.PENDENTE.value))
        return (PRIORIDADE_POR_STATUS.get(status, PRIORIDADE_DE_STATUS_DESCONHECIDO), no.id)

    def _descrever(self, no: NoGrafo) -> TarefaExecutavel:
        """Projeta o nó no DTO que a fila devolve."""
        return TarefaExecutavel(
            id=no.id,
            rotulo=no.rotulo,
            status=str(no.obter_propriedade("status", StatusTask.PENDENTE.value)),
            criterio_pronto=str(no.obter_propriedade("criterio_pronto", "")),
            depende_de=self._identificadores_de_dependencia(no.id),
        )

    def _coletar_tarefas_da_sessao(self, id_sessao: str) -> tuple[NoGrafo, ...]:
        """Percorre `produz` e `decompoe` a partir da sessão, reunindo suas Tasks."""
        visitados: set[str] = {id_sessao}
        fronteira: list[str] = [id_sessao]
        encontradas: dict[str, NoGrafo] = {}
        for _ in range(PROFUNDIDADE_MAXIMA_DA_SESSAO):
            if not fronteira:
                break
            fronteira = self._expandir_nivel(fronteira, visitados, encontradas)
        return tuple(encontradas.values())

    def _expandir_nivel(
        self,
        fronteira: list[str],
        visitados: set[str],
        encontradas: dict[str, NoGrafo],
    ) -> list[str]:
        """Expande um nível de descendentes, registrando as Tasks alcançadas."""
        proxima: list[str] = []
        for id_no in fronteira:
            proxima.extend(self._descendentes_novos(id_no, visitados, encontradas))
        return proxima

    def _descendentes_novos(
        self,
        id_no: str,
        visitados: set[str],
        encontradas: dict[str, NoGrafo],
    ) -> tuple[str, ...]:
        """Coleta os filhos ainda não visitados de um nó, anotando as Tasks."""
        novos: list[str] = []
        for aresta in self._view.obter_arestas_saida(id_no):
            if aresta.tipo not in ARESTAS_DE_ALCANCE or aresta.destino_id in visitados:
                continue
            visitados.add(aresta.destino_id)
            novos.append(aresta.destino_id)
            self._anotar_se_tarefa(aresta.destino_id, encontradas)
        return tuple(novos)

    def _anotar_se_tarefa(self, id_no: str, encontradas: dict[str, NoGrafo]) -> None:
        """Registra o nó entre as tarefas da sessão quando ele for uma Task."""
        no = self._view.obter_no(id_no)
        if no is not None and no.tipo == TipoNo.TASK:
            encontradas[id_no] = no

    def _esta_liberada(self, no: NoGrafo) -> bool:
        """Uma tarefa entra na fila quando nada mais depende de outra pessoa."""
        status = str(no.obter_propriedade("status", StatusTask.PENDENTE.value))
        if status in STATUS_FORA_DA_FILA or no.id in self._locks:
            return False
        if self._view.esta_bloqueada(no.id):
            return False
        return self._dependencias_cumpridas(no.id)

    def _dependencias_cumpridas(self, id_task: str) -> bool:
        """Toda Task apontada por `depende_de` precisa estar concluída."""
        return all(
            self._esta_concluida(id_dependencia)
            for id_dependencia in self._identificadores_de_dependencia(id_task)
        )

    def _identificadores_de_dependencia(self, id_task: str) -> tuple[str, ...]:
        """Lista, em ordem estável, os pré-requisitos declarados da tarefa."""
        arestas = self._view.obter_arestas_saida(id_task, TipoAresta.DEPENDE_DE)
        return tuple(sorted(aresta.destino_id for aresta in arestas))

    def _esta_concluida(self, id_task: str) -> bool:
        """Uma dependência ausente do grafo não trava a fila; uma aberta trava."""
        no = self._view.obter_no(id_task)
        if no is None:
            return True
        return no.obter_propriedade("status") == StatusTask.CONCLUIDO.value
