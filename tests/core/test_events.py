"""Testes unitários para eventos de log transacionais append-only."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor


def test_criar_evento_fluxo_nominal() -> None:
    """Testa criação nominal de EventoLog com construtor de fábrica via DTO."""
    dados = DadosCriacaoEvento(
        seq=1,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": "goal-1", "tipo": "Goal", "rotulo": "Objetivo"},
    )
    evento = EventoLog.criar(dados)
    assert evento.seq == 1
    assert evento.autor == "david"
    assert evento.papel == PapelAutor.HUMANO
    assert evento.origem == OrigemEvento.HUMANO
    assert evento.ramo_id == "main"
    assert len(evento.id) > 0
    assert len(evento.timestamp_utc) > 0


def test_evento_serializacao_payload_ordenada_edge_case() -> None:
    """Caso de borda: serialização do payload é imune à ordem de inserção das chaves."""
    payload_a = {"zeta": 99, "alpha": 1, "beta": 2}
    payload_b = {"alpha": 1, "beta": 2, "zeta": 99}

    ev_a = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload_a))
    ev_b = EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload_b))

    assert ev_a.serializar_payload_json() == ev_b.serializar_payload_json()


def test_evento_campos_opcionais_e_trace_id_edge_case() -> None:
    """Caso de borda: evento com ramo secundário, evento pai e trace_id OTel."""
    dados = DadosCriacaoEvento(
        seq=42,
        autor="agente-executor",
        papel=PapelAutor.EXECUTOR,
        tipo_evento=TipoEvento.EXECUCAO_INICIADA,
        payload={"id_run": "run-42"},
        origem=OrigemEvento.HARNESS,
        ramo_id="experimento-1",
        parent_evento_id="ev-parent-01",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )
    evento = EventoLog.criar(dados)
    assert evento.ramo_id == "experimento-1"
    assert evento.parent_evento_id == "ev-parent-01"
    assert evento.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
