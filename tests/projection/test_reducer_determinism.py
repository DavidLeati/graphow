"""Teste formal de determinismo estrito do GrafoReducer (prova de 200+ eventos)."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.projection.reducer import GrafoReducer


def test_reducer_reconstrucao_fluxo_nominal() -> None:
    """Testa reconstrução básica a partir de eventos de criação de nó e aresta."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1", "tipo": "Goal", "rotulo": "G1"})),
        EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n2", "tipo": "Task", "rotulo": "T1"})),
        EventoLog.criar(DadosCriacaoEvento(3, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, {
            "id": "e1", "origem_id": "n1", "destino_id": "n2", "tipo": "decompoe"
        })),
    ]
    estado = GrafoReducer.reconstruir(eventos)
    assert estado.versao_log == 3
    assert estado.contem_no("n1")
    assert estado.contem_no("n2")
    assert estado.contem_aresta("e1")


def test_reducer_prova_determinismo_200_eventos_edge_case() -> None:
    """Prova de determinismo com 200 eventos intercalados de nós, arestas, updates e remoções."""
    eventos: list[EventoLog] = []
    seq = 1

    # Criação de 50 nós
    for i in range(1, 51):
        eventos.append(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="david",
                    papel=PapelAutor.HUMANO,
                    tipo_evento=TipoEvento.NO_CRIADO,
                    payload={"id": f"no-{i}", "tipo": TipoNo.TASK.value, "rotulo": f"Task {i}", "propriedades": {"idx": i}},
                )
            )
        )
        seq += 1

    # Criação de 50 arestas
    for i in range(1, 51):
        destino_idx = (i % 50) + 1
        eventos.append(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="david",
                    papel=PapelAutor.HUMANO,
                    tipo_evento=TipoEvento.ARESTA_CRIADA,
                    payload={
                        "id": f"aresta-{i}",
                        "origem_id": f"no-{i}",
                        "destino_id": f"no-{destino_idx}",
                        "tipo": TipoAresta.DEPENDE_DE.value,
                    },
                )
            )
        )
        seq += 1

    # Atualização de 50 nós
    for i in range(1, 51):
        eventos.append(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="executor",
                    papel=PapelAutor.EXECUTOR,
                    tipo_evento=TipoEvento.NO_ATUALIZADO,
                    payload={"id": f"no-{i}", "rotulo": f"Task {i} Atualizada", "propriedades": {"status": "concluido"}},
                    origem=OrigemEvento.HARNESS,
                )
            )
        )
        seq += 1

    # Remoção de 25 nós e 25 execuções (totalizando 200 eventos)
    for i in range(1, 26):
        eventos.append(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="david",
                    papel=PapelAutor.HUMANO,
                    tipo_evento=TipoEvento.NO_REMOVIDO,
                    payload={"id": f"no-{i}"},
                )
            )
        )
        seq += 1

    for i in range(1, 26):
        eventos.append(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="sistema",
                    papel=PapelAutor.SISTEMA,
                    tipo_evento=TipoEvento.EXECUCAO_CONCLUIDA,
                    payload={"id": f"run-{i}", "duracao_ms": 150},
                    origem=OrigemEvento.HARNESS,
                )
            )
        )
        seq += 1

    assert len(eventos) == 200

    # 1ª projeção
    estado_1: GrafoEstado = GrafoReducer.reconstruir(eventos)
    json_1: str = estado_1.serializar_para_json()

    # Apaga estado e reconstrói do zero absoluto
    del estado_1
    estado_2: GrafoEstado = GrafoReducer.reconstruir(eventos)
    json_2: str = estado_2.serializar_para_json()

    # Comparação byte-a-byte estrita
    assert json_1 == json_2
    assert estado_2.versao_log == 200


def test_reducer_remocao_cascata_arestas_edge_case() -> None:
    """Caso de borda: remoção de nó remove automaticamente as arestas conectadas."""
    eventos = [
        EventoLog.criar(DadosCriacaoEvento(1, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n1", "tipo": "Goal"})),
        EventoLog.criar(DadosCriacaoEvento(2, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": "n2", "tipo": "Task"})),
        EventoLog.criar(DadosCriacaoEvento(3, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, {
            "id": "e1", "origem_id": "n1", "destino_id": "n2", "tipo": "decompoe"
        })),
        EventoLog.criar(DadosCriacaoEvento(4, "david", PapelAutor.HUMANO, TipoEvento.NO_REMOVIDO, {"id": "n1"})),
    ]
    estado = GrafoReducer.reconstruir(eventos)
    assert not estado.contem_no("n1")
    assert estado.contem_no("n2")
    assert not estado.contem_aresta("e1")
