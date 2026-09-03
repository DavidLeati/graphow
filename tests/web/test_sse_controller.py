"""Testes unitários para o SSEWebController."""

from pathlib import Path

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.web.sse_controller import NOME_EVENTO_ABERTURA, NOME_EVENTO_DESCARTE, SSEWebController

CAMINHO_CLIENTE_JS: Path = (
    Path(__file__).parent.parent.parent / "src" / "graphow" / "web" / "static" / "js" / "sse_client.js"
)


def _criar_evento_dummy(id_no: str = "n-1") -> EventoLog:
    """Gera um EventoLog de teste."""
    return EventoLog.criar(DadosCriacaoEvento(
        seq=1,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": id_no, "rotulo": "Teste SSE"},
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
    assert f"event: {NOME_EVENTO_ABERTURA}" in msg_open

    msg_evento = next(iterador)
    assert f"event: {TipoEvento.NO_CRIADO.value}" in msg_evento
    assert "Teste SSE" in msg_evento


def test_stream_encerra_quando_o_assinante_deixa_de_estar_registrado_edge_case() -> None:
    """Caso de borda: sem fim de iterador, a resposta HTTP nunca fecha e o cliente não reconecta."""
    ctrl = SSEWebController()
    fila = ctrl.registrar_assinante()
    iterador = ctrl.gerar_stream_para_fila(fila, timeout_segundos=0.01)
    assert f"event: {NOME_EVENTO_ABERTURA}" in next(iterador)

    ctrl.remover_assinante(fila)

    assert f"event: {NOME_EVENTO_DESCARTE}" in next(iterador)
    with pytest.raises(StopIteration):
        next(iterador)


def test_fila_cheia_descarta_o_assinante_e_encerra_o_stream_edge_case() -> None:
    """Caso de borda: o cliente que não acompanha o ritmo é desligado, não deixado no vazio.

    Era este o buraco: `despachar_evento` removia o assinante em silêncio e o
    stream continuava pingando para uma fila órfã.
    """
    ctrl = SSEWebController(limite_de_eventos_em_fila=2)
    fila = ctrl.registrar_assinante()
    iterador = ctrl.gerar_stream_para_fila(fila, timeout_segundos=0.01)
    next(iterador)

    for indice in range(3):
        ctrl.despachar_evento(_criar_evento_dummy(f"n-{indice}"))

    assert ctrl.esta_registrado(fila) is False
    mensagens = list(iterador)
    assert f"event: {NOME_EVENTO_DESCARTE}" in mensagens[-1]


def test_assinante_saudavel_permanece_no_stream_nominal() -> None:
    """O descarte é exceção: quem consome no ritmo continua recebendo."""
    ctrl = SSEWebController(limite_de_eventos_em_fila=2)
    fila = ctrl.registrar_assinante()
    iterador = ctrl.gerar_stream_para_fila(fila, timeout_segundos=0.01)
    next(iterador)

    ctrl.despachar_evento(_criar_evento_dummy("n-1"))
    assert "Teste SSE" in next(iterador)
    ctrl.despachar_evento(_criar_evento_dummy("n-2"))

    assert ctrl.esta_registrado(fila) is True
    assert "Teste SSE" in next(iterador)


def test_cliente_escuta_o_evento_de_descarte_que_o_servidor_emite() -> None:
    """Contrato entre as pontas: renomear no servidor sem renomear no cliente cala o navegador."""
    assert NOME_EVENTO_DESCARTE in CAMINHO_CLIENTE_JS.read_text(encoding="utf-8")


def test_cliente_escuta_todo_tipo_de_evento_do_log() -> None:
    """Um tipo que o servidor emite e o navegador ignora é um fato que nunca chega ao canvas."""
    cliente = CAMINHO_CLIENTE_JS.read_text(encoding="utf-8")
    ausentes = [tipo.value for tipo in TipoEvento if f'"{tipo.value}"' not in cliente]
    assert not ausentes, ausentes


def test_nomes_de_evento_nao_colidem_com_os_reservados_do_event_source() -> None:
    """Nome reservado no campo `event:` faz o navegador confundir mensagem com conexão.

    Foi assim que `event: open` disparava o `onopen` do cliente uma segunda vez,
    a cada conexão, e a ressincronização rodava em dobro.
    """
    reservados = {"open", "error", "message"}
    assert NOME_EVENTO_ABERTURA not in reservados
    assert NOME_EVENTO_DESCARTE not in reservados
