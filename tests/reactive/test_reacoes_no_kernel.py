"""As reações nativas passam pelos quatro portões, não só pela emissão da proposta.

O teste antigo conferia que o comportamento devolvia uma proposta. A proposta da
decisão substituída era recusada pelo RoleGate e o motor engolia a recusa, então
a suíte ficava verde com a reação morta. Aqui cada reação é submetida ao kernel
de verdade e cobrada pelo efeito no grafo. Ver defeito V-01.
"""

from graphow.core.events import EventoLog
from graphow.core.types import OrigemEvento, PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.graph_view import GrafoView
from graphow.reactive.engine import MotorReativo
from graphow.reactive.interfaces import ComportamentoReativo
from graphow.reactive.montagem import montar_comportamentos_padrao
from graphow.storage.in_memory_store import InMemoryEventStore


def _no(id_no: str, tipo: TipoNo) -> ItemPatch:
    """Operação de criação de um nó de teste."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": id_no},
    )


def _aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de uma aresta tipada de teste."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _submeter_como_humano(kernel: WriteKernel, operacoes: list[ItemPatch]) -> tuple[str, ...]:
    """Escreve no grafo pela sessão humana e devolve os eventos gerados."""
    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes)
        )
    )
    assert recibo.sucesso, recibo.mensagem
    return recibo.eventos_gerados


def _montar_motor(kernel: WriteKernel) -> MotorReativo:
    """Motor com os comportamentos que o produto ativa por padrão."""
    motor = MotorReativo(kernel)
    for comportamento in montar_comportamentos_padrao():
        motor.registrar_comportamento(comportamento)
    return motor


def _kernel_com_decisao_substituida() -> tuple[WriteKernel, EventoLog]:
    """Grafo com a substituição já gravada, e o evento que a registrou."""
    kernel = WriteKernel(InMemoryEventStore())
    _submeter_como_humano(
        kernel,
        [
            _no("sess-1", TipoNo.SESSAO),
            _no("d-velha", TipoNo.DECISION),
            _no("d-nova", TipoNo.DECISION),
            _aresta("p1", "sess-1", "d-velha", TipoAresta.PRODUZ),
        ],
    )
    gerados = _submeter_como_humano(
        kernel, [_aresta("sub-1", "d-nova", "d-velha", TipoAresta.SUBSTITUI)]
    )
    evento = kernel.obter_evento(gerados[-1])
    assert evento is not None
    return kernel, evento


def test_reacao_de_decisao_substituida_chega_ao_grafo_nominal() -> None:
    """A nota de invalidação era recusada no portão e nunca era persistida."""
    kernel, evento = _kernel_com_decisao_substituida()
    motor = _montar_motor(kernel)

    motor.processar_evento(evento)

    notas = kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    assert [nota.rotulo for nota in notas] == ["Decisao d-velha foi substituida por d-nova"]
    assert motor.recusas_registradas == ()


def test_nota_de_invalidacao_aponta_para_a_decisao_vencida_nominal() -> None:
    """Sem a aresta a nota não aparece na vista de quem lê a decisão antiga."""
    kernel, evento = _kernel_com_decisao_substituida()
    _montar_motor(kernel).processar_evento(evento)

    view = kernel.obter_view()
    nota = view.listar_nos_por_tipo(TipoNo.NOTE)[0]
    tipos_de_entrada = {aresta.tipo for aresta in view.obter_arestas_entrada("d-velha")}

    assert TipoAresta.DERIVA_DE in tipos_de_entrada
    assert nota.propriedades["id_decisao_vigente"] == "d-nova"


def test_reacao_e_gravada_com_origem_comportamento_nominal() -> None:
    """A origem do evento persistido distingue a reação de uma escrita de agente."""
    kernel, evento = _kernel_com_decisao_substituida()
    _montar_motor(kernel).processar_evento(evento)

    origens = {ev.origem for ev in kernel.repositorio.ler_eventos("main") if ev.autor.startswith("comportamento")}

    assert origens == {OrigemEvento.COMPORTAMENTO}


def test_reacao_de_revisao_chega_ao_grafo_nominal() -> None:
    """A outra reação nativa também é cobrada pelo efeito, não pela intenção."""
    kernel = WriteKernel(InMemoryEventStore())
    _submeter_como_humano(
        kernel,
        [_no("sess-1", TipoNo.SESSAO), _no("t1", TipoNo.TASK), _aresta("p1", "sess-1", "t1", TipoAresta.PRODUZ)],
    )
    gerados = _submeter_como_humano(
        kernel,
        [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.PRONTO_PARA_REVISAO.value)],
    )
    evento = kernel.obter_evento(gerados[-1])
    assert evento is not None
    motor = _montar_motor(kernel)

    motor.processar_evento(evento)

    notas = kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    assert [nota.rotulo for nota in notas] == ["Revisao solicitada: t1"]
    assert motor.recusas_registradas == ()


class _ComportamentoRecusado(ComportamentoReativo):
    """Comportamento que propõe o que a matriz de papéis nega a um executor."""

    @property
    def nome(self) -> str:
        """Nome identificador do comportamento de teste."""
        return "ComportamentoRecusado"

    def avaliar(self, evento: EventoLog, view: GrafoView) -> PropostaPatch:
        """Propõe uma Constraint, tipo reservado ao humano em qualquer projeto."""
        return PropostaPatch.criar(
            DadosPropostaPatch(
                autor="comportamento-teste",
                papel=PapelAutor.EXECUTOR,
                operacoes=[_no("c-1", TipoNo.CONSTRAINT)],
            )
        )


def test_reacao_recusada_deixa_rastro_edge_case() -> None:
    """Caso de borda: a recusa engolida foi o que escondeu a reação morta."""
    kernel, evento = _kernel_com_decisao_substituida()
    motor = MotorReativo(kernel)
    motor.registrar_comportamento(_ComportamentoRecusado())

    motor.processar_evento(evento)

    recusas = motor.recusas_registradas
    assert len(recusas) == 1
    assert recusas[0].comportamento == "ComportamentoRecusado"
    assert recusas[0].modo_de_falha == "violacao_permissao_papel"
    assert evento.id in recusas[0].descrever()
