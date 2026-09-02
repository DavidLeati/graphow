"""Testes unitários para SSETransport compatível com AG-UI."""

from graphow.api.sse_transport import SSETransport
from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor


def test_sse_formatar_evento_nominal() -> None:
    """Testa formatação de evento no padrão SSE com chaves obrigatórias."""
    dados = DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1", "rotulo": "Teste"})
    evento = EventoLog.criar(dados)
    frame = SSETransport.formatar_evento_sse(evento)

    assert frame.startswith("event: no_criado\n")
    assert f"id: {evento.id}\n" in frame
    assert "data: {" in frame
    assert frame.endswith("\n\n")


def test_sse_stream_gerador_multiplos_eventos_edge_case() -> None:
    """Caso de borda: geração de stream contínuo de múltiplos eventos."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1"})),
        EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_ATUALIZADO, {"id": "n1"})),
    ]
    stream = list(SSETransport.gerar_stream_ag_ui(eventos))
    assert len(stream) == 2
    assert "event: no_criado" in stream[0]
    assert "event: no_atualizado" in stream[1]
