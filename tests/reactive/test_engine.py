"""Testes unitários para MotorReativo."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.builtins import RevisorNotificadoBehavior
from graphow.reactive.engine import MotorReativo
from graphow.storage.in_memory_store import InMemoryEventStore


def test_motor_reativo_despacho_nominal() -> None:
    """Testa disparo e persistência de reações pelo MotorReativo."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    motor = MotorReativo(kernel)
    motor.registrar_comportamento(RevisorNotificadoBehavior())

    # Cria a sessao e a task inicial que ela produz
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=[
                    ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-1", value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao"}),
                    ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value, "rotulo": "T1"}),
                    ItemPatch(op=OperacaoPatch.ADD, path="/arestas/prod-t1", value={"id": "prod-t1", "origem_id": "sess-1", "destino_id": "t1", "tipo": TipoAresta.PRODUZ.value}),
                ],
            )
        )
    )

    # Evento de transição para pronto_para_revisao
    dados_update = DadosCriacaoEvento(
        seq=4,
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        tipo_evento=TipoEvento.NO_ATUALIZADO,
        payload={"id": "t1", "propriedades": {"status": StatusTask.PRONTO_PARA_REVISAO.value}},
    )
    ev_update = EventoLog.criar(dados_update)
    store.append_evento(ev_update)

    eventos_gerados = motor.processar_evento(ev_update)
    assert len(eventos_gerados) > 0

    view = kernel.obter_view("main")
    notas = view.listar_nos_por_tipo(TipoNo.NOTE)
    assert len(notas) == 1
    assert "Revisao solicitada" in notas[0].rotulo


def test_motor_reativo_limite_cascata_edge_case() -> None:
    """Caso de borda: limite de profundidade de cascata é respeitado."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    motor = MotorReativo(kernel, limite_cascata=0)
    motor.registrar_comportamento(RevisorNotificadoBehavior())

    dados = DadosCriacaoEvento(1, "executor", PapelAutor.EXECUTOR, TipoEvento.NO_ATUALIZADO, {"id": "t1"})
    ev = EventoLog.criar(dados)
    gerados = motor.processar_evento(ev, profundidade=0)
    assert len(gerados) == 0
