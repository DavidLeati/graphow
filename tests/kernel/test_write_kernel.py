"""Testes unitários para o WriteKernel e fluxo transacional."""

from collections.abc import Sequence

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)
from graphow.kernel.schema_gate import SchemaGate
from graphow.kernel import write_kernel
from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore


def _operacoes_de_hierarquia() -> list[ItemPatch]:
    """Projeto, Setor e Sessao encadeados por `contem`, onde o trabalho se pendura."""
    return [
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/proj-1", value={"id": "proj-1", "tipo": TipoNo.PROJETO.value, "rotulo": "Projeto 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/setor-1", value={"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "Setor 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/c-setor-1", value={
            "id": "c-setor-1", "origem_id": "proj-1", "destino_id": "setor-1", "tipo": TipoAresta.CONTEM.value
        }),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-1", value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/c-sess-1", value={
            "id": "c-sess-1", "origem_id": "setor-1", "destino_id": "sess-1", "tipo": TipoAresta.CONTEM.value
        }),
    ]


def test_write_kernel_submissao_nominal() -> None:
    """Testa submissão transacional nominal com criação de nó e aresta."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            *_operacoes_de_hierarquia(),
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/task-1", value={"id": "task-1", "tipo": TipoNo.TASK.value, "rotulo": "Task 1"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value={
                "id": "e1", "origem_id": "sess-1", "destino_id": "task-1", "tipo": TipoAresta.PRODUZ.value
            }),
        ],
        justificativa="Inicialização do fluxo",
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is True
    # Projeto, Setor e as duas `contem` somam quatro eventos aos três originais.
    assert recibo.versao_log == 7
    assert len(recibo.eventos_gerados) == 7

    view = kernel.obter_view("main")
    assert view.total_nos == 4
    assert view.total_arestas == 3


def test_write_kernel_rejeicao_atomica_sem_efeitos_colaterais_edge_case() -> None:
    """Caso de borda: rejeição no portão não persiste nenhum evento e mantém estado intacto."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    # Submissão inválida por violação de papel
    dados_invalidos = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/c1", value={"id": "c1", "tipo": TipoNo.CONSTRAINT.value}),
        ],
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados_invalidos))

    assert recibo.sucesso is False
    assert store.obter_ultimo_seq("main") == 0
    assert kernel.obter_view("main").total_nos == 0


def test_write_kernel_gestao_de_locks_edge_case() -> None:
    """Caso de borda: aquisição, bloqueio e liberação de lock exclusivo de Task."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    # Cria task
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=[
                    *_operacoes_de_hierarquia(),
                    ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value}),
                    ItemPatch(op=OperacaoPatch.ADD, path="/arestas/p-t1", value={
                        "id": "p-t1", "origem_id": "sess-1", "destino_id": "t1", "tipo": TipoAresta.PRODUZ.value
                    }),
                ],
            )
        )
    )

    # Agente A adquire lock
    assert kernel.adquirir_lock_task("t1", "agente-a") is True
    # Agente B tenta adquirir lock sobre mesma task
    assert kernel.adquirir_lock_task("t1", "agente-b") is False

    # Agente B tenta submeter patch e é barrado
    recibo_b = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="agente-b",
                papel=PapelAutor.EXECUTOR,
                operacoes=[
                    ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.EM_ANDAMENTO.value),
                ],
            )
        )
    )
    assert recibo_b.sucesso is False
    assert "bloqueado para escrita" in recibo_b.mensagem

    # Agente A libera lock e agente B consegue adquirir
    assert kernel.liberar_lock_task("t1", "agente-a") is True
    assert kernel.adquirir_lock_task("t1", "agente-b") is True


class _SchemaGatePermissivo(SchemaGate):
    """Aprova tudo: faz o papel de um portão que deixou passar uma forma que a projeção não dobra."""

    def validar(self, proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
        """Aprova o lote sem olhar."""
        return ResultadoValidacao.sucesso()


def test_lote_que_nao_se_aplica_e_recusado_sem_tocar_o_log_edge_case() -> None:
    """Caso de borda: a projeção vinha depois do `append_eventos` e o lote ruim ficava gravado.

    Com um portão que aprova tudo, a aresta de tipo inexistente chega ao
    acumulador, que estoura. O kernel projeta antes de gravar: o lote volta
    recusado, o log não anda e o ramo continua legível.
    """
    store = InMemoryEventStore()
    kernel = WriteKernel(store, DependenciasKernel(schema_gate=_SchemaGatePermissivo()))
    valor = {"id": "e1", "origem_id": "a", "destino_id": "b", "tipo": "tipo_fantasma"}
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value=valor)],
    )

    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.ESTRUTURA_INCOMPLETA.value
    assert recibo.diagnostico is not None and recibo.diagnostico.portao == "WriteKernel"
    assert store.obter_ultimo_seq("main") == 0
    assert kernel.obter_view("main").total_arestas == 0


class _StoreComConcorrente(InMemoryEventStore):
    """Store em que outro escritor ocupa a posição nas primeiras N gravações do kernel."""

    def __init__(self, perdas: int) -> None:
        super().__init__()
        self.perdas_restantes: int = perdas
        self.leituras_integrais: int = 0

    def ler_eventos(self, ramo_id: str = "main") -> list[EventoLog]:
        """Leitura do ramo inteiro, contada: é o custo do replay completo."""
        self.leituras_integrais += 1
        return super().ler_eventos(ramo_id)

    def ler_eventos_desde_seq(self, ramo_id: str, seq_exclusivo: int) -> list[EventoLog]:
        """Leitura incremental, sem passar pela contagem da leitura integral."""
        return [evento for evento in super().ler_eventos(ramo_id) if evento.seq > seq_exclusivo]

    def append_eventos(self, eventos: Sequence[EventoLog]) -> None:
        """Nas primeiras gravações, o concorrente grava antes na mesma posição."""
        if self.perdas_restantes > 0:
            self.perdas_restantes -= 1
            id_no = f"proj-alheio-{self.perdas_restantes}"
            payload = {"id": id_no, "tipo": TipoNo.PROJETO.value, "rotulo": id_no}
            dados = DadosCriacaoEvento(eventos[0].seq, "outro", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload)
            super().append_eventos((EventoLog.criar(dados),))
        super().append_eventos(eventos)


def test_kernel_espera_e_revalida_por_delta_quando_perde_a_posicao_edge_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """Perder seis vezes seguidas não recusa o lote, e nenhuma tentativa refaz o replay inteiro.

    Com quatro tentativas coladas, três processos gravando juntos perdiam de 2%
    a 7% dos lotes; e cada conflito descartava a projeção, obrigando o replay.
    """
    esperas: list[int] = []
    monkeypatch.setattr(write_kernel, "esperar_antes_de_repetir", esperas.append)
    store = _StoreComConcorrente(perdas=6)
    kernel = WriteKernel(store)

    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=tuple(_operacoes_de_hierarquia()))
    resultado = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert resultado.sucesso, resultado.mensagem
    assert esperas == [0, 1, 2, 3, 4, 5]
    assert store.leituras_integrais == 1
    assert kernel.obter_view().contem_no("sess-1")
    assert kernel.obter_view().contem_no("proj-alheio-0")
