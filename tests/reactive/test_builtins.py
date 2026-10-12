"""Testes unitários para comportamentos reativos nativos."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.reactive.builtins import ReavaliacaoDecisaoSubstituidaBehavior
from graphow.reactive.montagem import montar_comportamentos_padrao


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
    assert nomes == {"ReavaliacaoDecisaoSubstituida", "SessaoEncerrada", "AprendizadosAcumulados"}


def test_revisor_por_task_nao_e_mais_acordado_por_nota_edge_case() -> None:
    """Caso de borda: a Task que vai para `pronto_para_revisao` não gera Note de revisão; a revisão por Task saiu do padrão."""
    nomes = {comportamento.nome for comportamento in montar_comportamentos_padrao()}

    assert "RevisorNotificado" not in nomes
