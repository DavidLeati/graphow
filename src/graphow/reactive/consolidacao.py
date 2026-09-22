"""Consolidação pedida pelo próprio grafo: os aprendizados de um alcance se acumulam e o motor abre a Task.

Um projeto com vinte aprendizados promovidos herdava vinte linhas em toda
tarefa, e ninguém pedia que fossem consolidados: a memória só crescia. Este
comportamento observa uma Sessao abrir, criada ou reaberta, e conta os
aprendizados vigentes de cada alcance que a cobre: o Setor, o Projeto e o
global. Passado o limite, e sem Task de consolidar pendente para o alcance,
propõe uma, produzida pela sessão que abre e assinada como planejador, o papel
que cria Task. É a mesma compactação que a condensação faz com a sessão, um
nível acima: o agente a encontra em `proximas_tarefas` e na vista de retomada,
escreve os consolidados por `registrar_aprendizado` com `substitui` para os
absorvidos, e o humano os promove, que é quando os absorvidos saem da vista.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from graphow.context.memoria import ALCANCE_GLOBAL, alcances_de, aprendizados_vigentes
from graphow.core.events import EventoLog, TipoEvento
from graphow.core.models import NoGrafo
from graphow.core.types import OrigemEvento, PapelAutor, StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.projection.graph_view import GrafoView
from graphow.reactive.condensacao import ACAO_DE_CONSOLIDAR, CAMPO_ACAO, CAMPO_ALVO
from graphow.reactive.interfaces import ComportamentoReativo

AUTOR_DO_CONSOLIDADOR: str = "comportamento-consolidador"
PREFIXO_DA_TAREFA: str = "task-consolidar"
LIMITE_DE_VIGENTES_POR_ALCANCE: int = 12

# O que a consolidação contém é roteiro da skill do agente, não regra do kernel.
# A descrição da Task repete o essencial para quem a pegar sem ter lido a skill.
ROTEIRO_DA_CONSOLIDACAO: str = (
    "Leia os aprendizados vigentes deste alcance (expandir_no em cada id abaixo) e agrupe-os por tema. "
    "Para cada grupo, registre um Aprendizado consolidado por registrar_aprendizado: afirmacao geral, "
    "como_aplicar que funde os dos absorvidos, origens = a uniao das origens deles e substitui = os ids "
    "absorvidos. Nao apague nada: o absorvido fica no grafo e sai da vista quando o humano promover o "
    "consolidado. Papel: revisor ou executor, donos de deriva_de e, entre Aprendizados, de substitui. "
    "O revisor deixa a Task em pronto_para_revisao; o executor pode concluir. Promover e do humano."
)
CRITERIO_DE_PRONTO: str = (
    "Aprendizados consolidados registrados, cada um com substitui para os absorvidos e deriva_de para as "
    f"origens deles; promovidos, os vigentes do alcance ficam em no maximo {LIMITE_DE_VIGENTES_POR_ALCANCE}"
)


@dataclass(frozen=True)
class Alcance:
    """Um lugar onde aprendizados valem: o id do contêiner ou a marca global, com o rótulo para a Task."""

    id: str
    rotulo: str


GLOBAL: Alcance = Alcance(id=ALCANCE_GLOBAL, rotulo=ALCANCE_GLOBAL)


@dataclass(frozen=True)
class PedidoDeConsolidacao:
    """Um alcance que passou do limite e os vigentes que a Task vai listar."""

    alcance: Alcance
    vigentes: tuple[str, ...]


class AprendizadosAcumuladosBehavior(ComportamentoReativo):
    """Abre a Task de consolidar quando uma Sessao abre num alcance com vigentes demais."""

    @property
    def nome(self) -> str:
        """Nome identificador do comportamento."""
        return "AprendizadosAcumulados"

    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch | None:
        """Reage à Sessao criada ou reaberta; propõe uma Task por alcance lotado e sem pedido pendente."""
        sessao = sessao_que_abre(evento, view)
        if sessao is None:
            return None
        pedidos = pedidos_de_consolidacao(sessao.id, view)
        if not pedidos:
            return None
        return montar_proposta_de_consolidacao(sessao, pedidos)


def sessao_que_abre(evento: EventoLog, view: GrafoView) -> NoGrafo | None:
    """A Sessao que o evento cria ou devolve a `ativa`; None para qualquer outro evento."""
    if not (_cria_sessao(evento) or _reabre_sessao(evento)):
        return None
    sessao = view.obter_no(str(evento.payload.get("id", "")))
    return sessao if sessao is not None and sessao.tipo == TipoNo.SESSAO else None


def _cria_sessao(evento: EventoLog) -> bool:
    """O evento de criação de um nó do tipo Sessao."""
    return evento.tipo_evento == TipoEvento.NO_CRIADO and evento.payload.get("tipo") == TipoNo.SESSAO.value


def _reabre_sessao(evento: EventoLog) -> bool:
    """A escrita do status `ativa`: é como o harness reabre a sessão retomada."""
    if evento.tipo_evento != TipoEvento.NO_ATUALIZADO:
        return False
    return evento.payload.get("propriedades", {}).get("status") == StatusSessao.ATIVA.value


def pedidos_de_consolidacao(id_sessao: str, view: GrafoView) -> tuple[PedidoDeConsolidacao, ...]:
    """Os alcances da sessão que passaram do limite e ainda não têm Task de consolidar aberta."""
    pedidos: list[PedidoDeConsolidacao] = []
    for alcance in alcances_da_sessao(id_sessao, view):
        vigentes = vigentes_no_alcance(alcance.id, view)
        if len(vigentes) > LIMITE_DE_VIGENTES_POR_ALCANCE and not tem_consolidacao_pendente(alcance.id, view):
            pedidos.append(PedidoDeConsolidacao(alcance=alcance, vigentes=vigentes))
    return tuple(pedidos)


def alcances_da_sessao(id_sessao: str, view: GrafoView) -> tuple[Alcance, ...]:
    """O Setor da sessão, o Projeto dele e o global, nesta ordem; sem Setor, só o global."""
    setor = _pai_por_contencao(id_sessao, view)
    return alcances_do_setor(setor.id, view) if setor is not None else (GLOBAL,)


def alcances_do_setor(id_setor: str, view: GrafoView) -> tuple[Alcance, ...]:
    """O Setor, o Projeto que o contém e o global, nesta ordem."""
    alcances: list[Alcance] = []
    setor = view.obter_no(id_setor)
    if setor is not None:
        alcances.append(Alcance(id=setor.id, rotulo=setor.rotulo))
    projeto = _pai_por_contencao(id_setor, view)
    if projeto is not None:
        alcances.append(Alcance(id=projeto.id, rotulo=projeto.rotulo))
    alcances.append(GLOBAL)
    return tuple(alcances)


def _pai_por_contencao(id_no: str, view: GrafoView) -> NoGrafo | None:
    """O nó de onde parte a primeira aresta `contem` que chega neste."""
    entradas = sorted(aresta.origem_id for aresta in view.obter_arestas_entrada(id_no, TipoAresta.CONTEM))
    return view.obter_no(entradas[0]) if entradas else None


def vigentes_no_alcance(alcance: str, view: GrafoView) -> tuple[str, ...]:
    """Ids dos aprendizados vigentes que valem para o alcance, na ordem do log."""
    agora = datetime.now(timezone.utc).isoformat()
    return tuple(no.id for no in aprendizados_vigentes(view, agora) if alcance in alcances_de(no, view))


def tarefas_de_consolidacao_pendentes(alcance: str, view: GrafoView) -> tuple[NoGrafo, ...]:
    """As Tasks de consolidar este alcance ainda abertas, em ordem estável."""
    tarefas = (
        no
        for no in view.listar_nos_por_tipo(TipoNo.TASK)
        if eh_tarefa_de_consolidacao(no) and no.obter_propriedade(CAMPO_ALVO) == alcance and not _esta_concluida(no)
    )
    return tuple(sorted(tarefas, key=lambda no: no.id))


def tem_consolidacao_pendente(alcance: str, view: GrafoView) -> bool:
    """Uma Task de consolidar ainda aberta: pedir outra seria pedir duas vezes."""
    return bool(tarefas_de_consolidacao_pendentes(alcance, view))


def eh_tarefa_de_consolidacao(no: NoGrafo) -> bool:
    """Reconhece a Task que este comportamento abre."""
    return no.tipo == TipoNo.TASK and no.obter_propriedade(CAMPO_ACAO) == ACAO_DE_CONSOLIDAR


def _esta_concluida(no: NoGrafo) -> bool:
    """Uma Task concluída já não conta como pedido pendente."""
    return str(no.obter_propriedade("status", StatusTask.PENDENTE.value)) == StatusTask.CONCLUIDO.value


def montar_proposta_de_consolidacao(sessao: NoGrafo, pedidos: Sequence[PedidoDeConsolidacao]) -> PropostaPatch:
    """Uma Task por alcance lotado, pendurada na sessão que abre e assinada pelo papel que cria Task."""
    operacoes: list[ItemPatch] = []
    for pedido in pedidos:
        id_task = f"{PREFIXO_DA_TAREFA}-{uuid.uuid4().hex[:8]}"
        operacoes.extend((_operacao_da_tarefa(id_task, pedido), _operacao_produz(id_task, sessao.id)))
    alcances = ", ".join(pedido.alcance.id for pedido in pedidos)
    dados = DadosPropostaPatch(
        autor=AUTOR_DO_CONSOLIDADOR,
        papel=PapelAutor.PLANEJADOR,
        operacoes=tuple(operacoes),
        justificativa=f"Sessao {sessao.id} aberta: aprendizados vigentes passam do limite em {alcances}",
        origem=OrigemEvento.COMPORTAMENTO,
    )
    return PropostaPatch.criar(dados)


def _operacao_da_tarefa(id_task: str, pedido: PedidoDeConsolidacao) -> ItemPatch:
    """Criação da Task com o roteiro, os vigentes a consolidar e o critério de pronto."""
    descricao = f"{ROTEIRO_DA_CONSOLIDACAO} Vigentes em {pedido.alcance.id}: {', '.join(pedido.vigentes)}."
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_task}",
        value={
            "id": id_task,
            "tipo": TipoNo.TASK.value,
            "rotulo": _rotulo_da_tarefa(pedido.alcance),
            "propriedades": {
                "status": StatusTask.PENDENTE.value,
                CAMPO_ACAO: ACAO_DE_CONSOLIDAR,
                CAMPO_ALVO: pedido.alcance.id,
                "descricao": descricao,
                "criterio_pronto": CRITERIO_DE_PRONTO,
            },
        },
    )


def _rotulo_da_tarefa(alcance: Alcance) -> str:
    """O rótulo diz o alcance pelo nome que o humano conhece."""
    if alcance.id == ALCANCE_GLOBAL:
        return "Consolidar aprendizados globais"
    return f"Consolidar aprendizados: {alcance.rotulo}"


def _operacao_produz(id_task: str, id_sessao: str) -> ItemPatch:
    """Aresta que pendura a Task na sessão que abre, onde o agente a encontra."""
    id_aresta = f"produz-{id_task}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": id_sessao, "destino_id": id_task, "tipo": TipoAresta.PRODUZ.value},
    )
