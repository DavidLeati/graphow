"""Testes unitários para comportamentos reativos nativos."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import OrigemEvento, PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.reactive.builtins import (
    ReavaliacaoDecisaoSubstituidaBehavior,
    RevisorNotificadoBehavior,
)
from graphow.reactive.montagem import montar_comportamentos_padrao


def _view_com_sessao_e_tarefa() -> GrafoView:
    """Sessao que produz uma Task, para a nota reativa ter onde se prender."""
    nos = {
        "sess-1": NoGrafo("sess-1", TipoNo.SESSAO, "Sprint"),
        "t1": NoGrafo("t1", TipoNo.TASK, "Minha Tarefa"),
    }
    arestas = {"p1": ArestaGrafo("p1", "sess-1", "t1", TipoAresta.PRODUZ)}
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def _evento_de_revisao() -> EventoLog:
    """Evento de transição da Task para pronto_para_revisao."""
    return EventoLog.criar(
        DadosCriacaoEvento(
            seq=1,
            autor="executor-1",
            papel=PapelAutor.EXECUTOR,
            tipo_evento=TipoEvento.NO_ATUALIZADO,
            payload={"id": "t1", "propriedades": {"status": StatusTask.PRONTO_PARA_REVISAO.value}},
        )
    )


def test_revisor_notificado_behavior_nominal() -> None:
    """Testa geração de notificação quando Task entra em pronto_para_revisao."""
    proposta = RevisorNotificadoBehavior().avaliar(_evento_de_revisao(), _view_com_sessao_e_tarefa())

    assert proposta is not None
    assert proposta.papel == PapelAutor.REVISOR
    assert len(proposta.operacoes) == 3


def test_nota_reativa_nasce_ligada_a_sessao_e_a_tarefa_nominal() -> None:
    """A nota órfã não aparecia em vista alguma: agora ela aponta para algo."""
    proposta = RevisorNotificadoBehavior().avaliar(_evento_de_revisao(), _view_com_sessao_e_tarefa())

    caminhos = [operacao.path for operacao in proposta.operacoes]
    destinos = [
        operacao.value["destino_id"] for operacao in proposta.operacoes if "/arestas/" in operacao.path
    ]
    assert sum(1 for caminho in caminhos if caminho.startswith("/arestas/")) == 2
    assert "t1" in destinos


def test_reacao_e_gravada_com_origem_comportamento_nominal() -> None:
    """A origem era derivada do papel e saía como 'harness' em toda reação."""
    proposta = RevisorNotificadoBehavior().avaliar(_evento_de_revisao(), _view_com_sessao_e_tarefa())

    assert proposta.origem == OrigemEvento.COMPORTAMENTO


def test_reacao_sem_sessao_alcancavel_nao_propoe_nada_edge_case() -> None:
    """Caso de borda: sem sessão onde pendurar, é melhor não criar nota órfã."""
    view = GrafoView(GrafoEstado(nos={"t1": NoGrafo("t1", TipoNo.TASK, "Solta")}))

    assert RevisorNotificadoBehavior().avaliar(_evento_de_revisao(), view) is None


def test_reavaliacao_decisao_substituida_edge_case() -> None:
    """Caso de borda: substituição de Decisão emite nota de invalidação de contexto."""
    nos = {
        "sess-1": NoGrafo("sess-1", TipoNo.SESSAO, "Sprint"),
        "d_velha": NoGrafo("d_velha", TipoNo.DECISION, "Decisao Antiga"),
        "d_nova": NoGrafo("d_nova", TipoNo.DECISION, "Decisao Nova"),
    }
    arestas = {"p1": ArestaGrafo("p1", "sess-1", "d_velha", TipoAresta.PRODUZ)}
    view = GrafoView(GrafoEstado(nos=nos, arestas=arestas))
    evento = EventoLog.criar(
        DadosCriacaoEvento(
            seq=2,
            autor="david",
            papel=PapelAutor.HUMANO,
            tipo_evento=TipoEvento.ARESTA_CRIADA,
            payload={
                "id": "e_sub",
                "origem_id": "d_nova",
                "destino_id": "d_velha",
                "tipo": TipoAresta.SUBSTITUI.value,
            },
        )
    )

    proposta = ReavaliacaoDecisaoSubstituidaBehavior().avaliar(evento, view)

    assert proposta is not None
    assert "d_velha" in proposta.justificativa
    assert proposta.origem == OrigemEvento.COMPORTAMENTO


def test_alerta_que_duplicava_a_questao_saiu_edge_case() -> None:
    """Caso de borda: a dúvida já está no grafo; copiá-la como Note era ruído."""
    nomes = {comportamento.nome for comportamento in montar_comportamentos_padrao()}

    assert "AlertaQuestaoPendente" not in nomes
    assert nomes == {"RevisorNotificado", "ReavaliacaoDecisaoSubstituida"}
