"""Testes unitários para MotorReativo."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.builtins import ReavaliacaoDecisaoSubstituidaBehavior
from graphow.reactive.engine import MotorReativo
from graphow.storage.in_memory_store import InMemoryEventStore


def _no(id_no: str, tipo: TipoNo) -> ItemPatch:
    """A criação de um nó."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": id_no})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """A criação de uma aresta."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}",
                     value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value})


def _kernel_com_decisao_substituida() -> WriteKernel:
    """Projeto, Setor, Sessao e duas Decisions, a nova substituindo a velha, gravadas sem motor ligado."""
    kernel = WriteKernel(InMemoryEventStore())
    operacoes = [
        _no("proj-1", TipoNo.PROJETO), _no("setor-1", TipoNo.SETOR), _aresta("proj-1", "setor-1", TipoAresta.CONTEM),
        _no("sess-1", TipoNo.SESSAO), _aresta("setor-1", "sess-1", TipoAresta.CONTEM),
        _no("d-velha", TipoNo.DECISION), _aresta("sess-1", "d-velha", TipoAresta.PRODUZ),
        _no("d-nova", TipoNo.DECISION), _aresta("sess-1", "d-nova", TipoAresta.PRODUZ),
        _aresta("d-nova", "d-velha", TipoAresta.SUBSTITUI),
    ]
    recibo = kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes)))
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _evento_da_substituicao(kernel: WriteKernel) -> EventoLog:
    """O evento que criou a aresta `substitui`."""
    return next(evento for evento in kernel.repositorio.ler_eventos("main")
                if evento.tipo_evento == TipoEvento.ARESTA_CRIADA and evento.payload.get("tipo") == TipoAresta.SUBSTITUI.value)


def test_motor_reativo_despacho_nominal() -> None:
    """Testa disparo e persistência de reações pelo MotorReativo."""
    kernel = _kernel_com_decisao_substituida()
    motor = MotorReativo(kernel)
    motor.registrar_comportamento(ReavaliacaoDecisaoSubstituidaBehavior())

    eventos_gerados = motor.processar_evento(_evento_da_substituicao(kernel))

    assert len(eventos_gerados) > 0
    notas = kernel.obter_view("main").listar_nos_por_tipo(TipoNo.NOTE)
    assert len(notas) == 1
    assert "Decisao d-velha foi substituida por d-nova" in notas[0].rotulo


def test_motor_reativo_limite_cascata_edge_case() -> None:
    """Caso de borda: limite de profundidade de cascata é respeitado."""
    kernel = _kernel_com_decisao_substituida()
    motor = MotorReativo(kernel, limite_cascata=0)
    motor.registrar_comportamento(ReavaliacaoDecisaoSubstituidaBehavior())

    gerados = motor.processar_evento(_evento_da_substituicao(kernel), profundidade=0)

    assert len(gerados) == 0
