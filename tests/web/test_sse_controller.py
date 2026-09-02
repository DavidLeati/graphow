"""Testes unitários para o SSEWebController."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.web.sse_controller import SSEWebController


def _criar_evento_dummy() -> EventoLog:
    """Gera um EventoLog de teste."""
    return EventoLog.criar(DadosCriacaoEvento(
        seq=1,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": "n-1", "rotulo": "Teste SSE"},
        origem=OrigemEvento.HUMANO,
    ))


def test_sse_fluxo_nominal_registro_e_despacho() -> None:
    """Valida registro de ouvinte e entrega de evento despachado."""
    ctrl = SSEWebController()
    fila = ctrl.registrar_assinante()

    evento = _criar_evento_dummy()
    enviados = ctrl.despachar_evento(evento)
    assert enviados == 1

    msg = fila.get_nowait()
    assert msg.id == evento.id
    ctrl.remover_assinante(fila)


def test_sse_remocao_assinante_edge_case() -> None:
    """Valida remoção segura de ouvinte."""
    ctrl = SSEWebController()
    fila = ctrl.registrar_assinante()
    assert len(ctrl._assinantes) == 1

    ctrl.remover_assinante(fila)
    assert len(ctrl._assinantes) == 0

    # Remoção idempotente
    ctrl.remover_assinante(fila)
    assert len(ctrl._assinantes) == 0


def test_sse_stream_geracao_mensagens_edge_case() -> None:
    """Valida geração de stream com mensagem de abertura e formatação SSE."""
    ctrl = SSEWebController()
    fila = ctrl.registrar_assinante()
    evento = _criar_evento_dummy()
    fila.put(evento)

    iterador = ctrl.gerar_stream_para_fila(fila, timeout_segundos=0.01)
    msg_open = next(iterador)
    assert "event: open" in msg_open

    msg_evento = next(iterador)
    assert f"event: {TipoEvento.NO_CRIADO.value}" in msg_evento
    assert "Teste SSE" in msg_evento
