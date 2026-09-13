"""Testes unitários para TracerOTel."""

from graphow.observability.tracer import DadosSpanDTO, TracerOTel


def test_tracer_registrar_e_listar_spans_nominal() -> None:
    """Testa criação e consulta de spans GenAI OTel via DTO."""
    tracer = TracerOTel()
    dados = DadosSpanDTO(
        nome_operacao="invoke_agent",
        atributos={"gen_ai.model": "claude-3-7-sonnet", "graphow.no.id": "t1"},
        sucesso=True,
    )
    span = tracer.registrar_span(dados)
    assert span.nome_operacao == "invoke_agent"
    assert span.atributos["gen_ai.model"] == "claude-3-7-sonnet"
    assert len(tracer.listar_todos_spans()) == 1


def test_tracer_filtro_por_trace_id_edge_case() -> None:
    """Caso de borda: isolamento e consulta de múltiplos spans pelo mesmo trace_id."""
    tracer = TracerOTel()
    trace_id = "trace-custom-123"

    tracer.registrar_span(DadosSpanDTO("read_view", {}, trace_id=trace_id))
    tracer.registrar_span(DadosSpanDTO("execute_tool", {}, trace_id=trace_id))
    tracer.registrar_span(DadosSpanDTO("read_view", {}, trace_id="outro-trace"))

    spans_trace = tracer.obter_spans_por_trace(trace_id)
    assert len(spans_trace) == 2
    assert len(tracer.listar_todos_spans()) == 3
