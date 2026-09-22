"""Condensação pedida pelo próprio grafo: a sessão encerra e o motor abre a Task.

O esqueleto do fechamento é do kernel e é determinístico. A prosa que explica
por que cada decisão vale, que achado mudou uma decisão e o que não fazer de
novo é trabalho de agente, e ninguém a pedia: as sessões nasciam pelo MCP e
pela interface e nunca eram encerradas, e quando o harness as encerrava nada
acontecia. Este comportamento observa a Sessao passar a `concluida` e propõe
uma Task de condensação pendurada nela, assinada como planejador, o papel que
cria Task. O agente a pega por `proximas_tarefas`, lê a sessão, escreve a Note
pelo PatchBoard e passa pelos mesmos quatro portões que qualquer outro.
"""

import uuid

from graphow.context.fechamento import ACAO_DE_CONDENSACAO
from graphow.core.events import EventoLog, TipoEvento
from graphow.core.models import NoGrafo
from graphow.core.types import OrigemEvento, PapelAutor, StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.projection.graph_view import GrafoView
from graphow.reactive.interfaces import ComportamentoReativo

ACAO_DE_CONDENSAR: str = "condensar_sessao"
# A acao da Task de consolidar aprendizados mora aqui, ao lado da de condensar,
# porque o balanco da sessao precisa das duas e reactive/consolidacao.py importa
# deste modulo: as Tasks que o grafo abre sozinho nao sao trabalho da sessao.
ACAO_DE_CONSOLIDAR: str = "consolidar_aprendizados"
ACOES_ABERTAS_PELO_GRAFO: frozenset[str] = frozenset({ACAO_DE_CONDENSAR, ACAO_DE_CONSOLIDAR})
AUTOR_DO_CONDENSADOR: str = "comportamento-condensador"
PREFIXO_DA_TAREFA: str = "task-condensar"
CAMPO_ACAO: str = "acao"
CAMPO_ALVO: str = "id_alvo"

# O que a condensação contém é roteiro da skill do agente, não regra do kernel.
# A descrição da Task repete o essencial para quem a pegar sem ter lido a skill.
ROTEIRO_DA_CONDENSACAO: str = (
    "Leia a sessao com ler_vista e escreva uma Note produzida por ela, com acao "
    f"'{ACAO_DE_CONDENSACAO}' e id_alvo igual ao id da sessao. No corpo: as decisoes "
    "vigentes com o motivo, os achados que mudaram uma decisao, o que ficou aberto e o "
    "que nao fazer de novo. Cada afirmacao carrega deriva_de para o no de onde saiu. "
    "Papel: revisor ou executor, donos de deriva_de. O revisor deixa a Task em "
    "pronto_para_revisao; o executor pode concluir."
)
CRITERIO_DE_PRONTO: str = "Note de condensacao produzida pela sessao, com deriva_de para cada no condensado"

# Só o que carrega conhecimento pede condensação. Uma sessão que só tem a
# própria telemetria, ou só a Task de condensar, não tem o que condensar.
TIPOS_QUE_PEDEM_CONDENSACAO: frozenset[TipoNo] = frozenset(
    {
        TipoNo.GOAL,
        TipoNo.TASK,
        TipoNo.DECISION,
        TipoNo.QUESTION,
        TipoNo.ARTIFACT,
        TipoNo.EVIDENCE,
        TipoNo.NOTE,
    }
)


class SessaoEncerradaBehavior(ComportamentoReativo):
    """Abre a Task de condensação quando uma Sessao passa a `concluida`."""

    @property
    def nome(self) -> str:
        """Nome identificador do comportamento."""
        return "SessaoEncerrada"

    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch | None:
        """Reage à escrita do status `concluida` numa Sessao com trabalho a condensar."""
        if evento.tipo_evento != TipoEvento.NO_ATUALIZADO:
            return None
        propriedades = evento.payload.get("propriedades", {})
        if propriedades.get("status") != StatusSessao.CONCLUIDA.value:
            return None
        sessao = view.obter_no(str(evento.payload.get("id", "")))
        if sessao is None or sessao.tipo != TipoNo.SESSAO:
            return None
        if not tem_trabalho_a_condensar(sessao.id, view) or tem_condensacao_pendente(sessao.id, view):
            return None
        return montar_proposta_de_condensacao(sessao)


def produzidos_pela_sessao(id_sessao: str, view: GrafoView) -> tuple[NoGrafo, ...]:
    """Nós que a sessão produziu, na ordem estável dos identificadores."""
    nos = (
        view.obter_no(aresta.destino_id)
        for aresta in view.obter_arestas_saida(id_sessao, TipoAresta.PRODUZ)
    )
    return tuple(sorted((no for no in nos if no is not None), key=lambda no: no.id))


def tem_trabalho_a_condensar(id_sessao: str, view: GrafoView) -> bool:
    """Há conhecimento na sessão além da telemetria e das Tasks que o grafo abriu nela sozinho."""
    return any(
        no.tipo in TIPOS_QUE_PEDEM_CONDENSACAO and not eh_tarefa_aberta_pelo_grafo(no)
        for no in produzidos_pela_sessao(id_sessao, view)
    )


def tem_condensacao_pendente(id_sessao: str, view: GrafoView) -> bool:
    """Uma Task de condensar ainda aberta: pedir outra seria pedir duas vezes."""
    return any(
        eh_tarefa_de_condensacao(no) and not _esta_concluida(no)
        for no in produzidos_pela_sessao(id_sessao, view)
    )


def eh_tarefa_de_condensacao(no: NoGrafo) -> bool:
    """Reconhece a Task que este comportamento abre."""
    return no.tipo == TipoNo.TASK and no.obter_propriedade(CAMPO_ACAO) == ACAO_DE_CONDENSAR


def eh_tarefa_aberta_pelo_grafo(no: NoGrafo) -> bool:
    """Condensar a sessão ou consolidar aprendizados: pedido do grafo, não trabalho da sessão."""
    return no.tipo == TipoNo.TASK and str(no.obter_propriedade(CAMPO_ACAO, "")) in ACOES_ABERTAS_PELO_GRAFO


def _esta_concluida(no: NoGrafo) -> bool:
    """Uma Task concluída já não conta como pedido pendente."""
    return str(no.obter_propriedade("status", StatusTask.PENDENTE.value)) == StatusTask.CONCLUIDO.value


def montar_proposta_de_condensacao(sessao: NoGrafo) -> PropostaPatch:
    """A Task pendurada na sessão que a motivou, assinada pelo papel que cria Task."""
    id_task = f"{PREFIXO_DA_TAREFA}-{uuid.uuid4().hex[:8]}"
    dados = DadosPropostaPatch(
        autor=AUTOR_DO_CONDENSADOR,
        papel=PapelAutor.PLANEJADOR,
        operacoes=(_operacao_da_tarefa(id_task, sessao), _operacao_produz(id_task, sessao.id)),
        justificativa=f"Sessao {sessao.id} encerrada: condensacao pendente",
        origem=OrigemEvento.COMPORTAMENTO,
    )
    return PropostaPatch.criar(dados)


def _operacao_da_tarefa(id_task: str, sessao: NoGrafo) -> ItemPatch:
    """Criação da Task com o roteiro e o critério de pronto da condensação."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_task}",
        value={
            "id": id_task,
            "tipo": TipoNo.TASK.value,
            "rotulo": f"Condensar sessao: {sessao.rotulo}",
            "propriedades": {
                "status": StatusTask.PENDENTE.value,
                CAMPO_ACAO: ACAO_DE_CONDENSAR,
                CAMPO_ALVO: sessao.id,
                "descricao": ROTEIRO_DA_CONDENSACAO,
                "criterio_pronto": CRITERIO_DE_PRONTO,
            },
        },
    )


def _operacao_produz(id_task: str, id_sessao: str) -> ItemPatch:
    """Aresta que pendura a Task na sessão encerrada, onde o agente a encontra."""
    id_aresta = f"produz-{id_task}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={
            "id": id_aresta,
            "origem_id": id_sessao,
            "destino_id": id_task,
            "tipo": TipoAresta.PRODUZ.value,
        },
    )
