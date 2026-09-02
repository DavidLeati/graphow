"""Testes unitários para o WriteKernel e fluxo transacional."""

from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore


def test_write_kernel_submissao_nominal() -> None:
    """Testa submissão transacional nominal com criação de nó e aresta."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-1", value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao 1"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/task-1", value={"id": "task-1", "tipo": TipoNo.TASK.value, "rotulo": "Task 1"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value={
                "id": "e1", "origem_id": "sess-1", "destino_id": "task-1", "tipo": TipoAresta.PRODUZ.value
            }),
        ],
        justificativa="Inicialização do fluxo",
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is True
    assert recibo.versao_log == 3
    assert len(recibo.eventos_gerados) == 3

    view = kernel.obter_view("main")
    assert view.total_nos == 2
    assert view.total_arestas == 1


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
                    ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value}),
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
