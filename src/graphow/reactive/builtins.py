"""Comportamentos reativos nativos desacoplados do Graphow.

Cada reação nasce ligada à sessão e ao nó que a motivou, e é gravada com origem
`comportamento`. A reação que duplicava a própria Question como Note saiu: ela
gerava ruído sem informação — a dúvida já está no grafo, com aresta `bloqueia`,
selo no canvas e presença na vista. Ver achado A-10.
"""

from graphow.core.events import EventoLog, TipoEvento
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import PropostaPatch
from graphow.projection.graph_view import GrafoView
from graphow.reactive.interfaces import ComportamentoReativo
from graphow.reactive.notas import PedidoDeNota, localizar_sessao_de, montar_proposta_de_nota


class RevisorNotificadoBehavior(ComportamentoReativo):
    """Acorda o revisor quando uma Task transiciona para 'pronto_para_revisao'."""

    @property
    def nome(self) -> str:
        """Nome identificador do comportamento."""
        return "RevisorNotificado"

    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch | None:
        """Verifica transição de status para pronto_para_revisao."""
        if evento.tipo_evento != TipoEvento.NO_ATUALIZADO:
            return None
        propriedades = evento.payload.get("propriedades", {})
        if propriedades.get("status") != StatusTask.PRONTO_PARA_REVISAO.value:
            return None
        return self._montar_nota(str(evento.payload.get("id", "")), view)

    def _montar_nota(self, id_task: str, view: GrafoView) -> PropostaPatch | None:
        """Cria a nota de revisão apontando para a tarefa e para a sessão dela."""
        tarefa = view.obter_no(id_task)
        id_sessao = localizar_sessao_de(id_task, view) if tarefa is not None else None
        if tarefa is None or id_sessao is None:
            return None
        return montar_proposta_de_nota(
            PedidoDeNota(
                prefixo="nota-rev",
                rotulo=f"Revisao solicitada: {tarefa.rotulo}",
                id_alvo=id_task,
                id_sessao=id_sessao,
                autor="comportamento-revisor",
                papel=PapelAutor.REVISOR,
                propriedades={"acao": "revisar_artefatos"},
            )
        )


class ReavaliacaoDecisaoSubstituidaBehavior(ComportamentoReativo):
    """Invalidação de tarefas dependentes quando uma Decisão é substituída.

    A nota é assinada como revisor porque `deriva_de` pertence a humano, executor
    e revisor. Assinada como planejador, ela era recusada pelo RoleGate e o motor
    descartava a recusa em silêncio: a reação existia no código e nunca no grafo.
    Ampliar a matriz para o planejador resolveria o sintoma e abriria a camada de
    proveniência do trabalho a quem só planeja. Ver defeito V-01.
    """

    @property
    def nome(self) -> str:
        """Nome identificador do comportamento."""
        return "ReavaliacaoDecisaoSubstituida"

    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch | None:
        """Detecta criação de aresta 'substitui' entre Decisões."""
        if evento.tipo_evento != TipoEvento.ARESTA_CRIADA:
            return None
        if evento.payload.get("tipo") != TipoAresta.SUBSTITUI.value:
            return None
        antiga = view.obter_no(str(evento.payload.get("destino_id", "")))
        if antiga is None or antiga.tipo != TipoNo.DECISION:
            return None
        return self._montar_nota(antiga, str(evento.payload.get("origem_id", "")), view)

    def _montar_nota(self, antiga: NoGrafo, id_nova: str, view: GrafoView) -> PropostaPatch | None:
        """Cria a nota de invalidação presa à decisão que deixou de valer."""
        id_sessao = localizar_sessao_de(antiga.id, view)
        if id_sessao is None:
            return None
        return montar_proposta_de_nota(
            PedidoDeNota(
                prefixo="nota-invalida",
                rotulo=f"Decisao {antiga.id} foi substituida por {id_nova}",
                id_alvo=antiga.id,
                id_sessao=id_sessao,
                autor="comportamento-invalidador",
                papel=PapelAutor.REVISOR,
                propriedades={"acao": "reavaliar_dependentes", "id_decisao_vigente": id_nova},
            )
        )
