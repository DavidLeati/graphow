"""Testes unitários para ConventionHarnessAdapter."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.convention_adapter import ConventionHarnessAdapter
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore


def _criar_setor_no_projeto(kernel: WriteKernel, id_setor: str) -> None:
    """Cria Projeto e Setor ligados por 'contem', onde as sessões por convenção vão nascer."""
    dados = DadosPropostaPatch(
        "david",
        PapelAutor.HUMANO,
        [
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/proj-1", value={"id": "proj-1", "tipo": TipoNo.PROJETO.value}),
            ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_setor}", value={"id": id_setor, "tipo": TipoNo.SETOR.value}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e-contem", value={
                "id": "e-contem", "origem_id": "proj-1", "destino_id": id_setor, "tipo": TipoAresta.CONTEM.value
            }),
        ],
    )
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso is True


def test_convention_adapter_nominal() -> None:
    """Testa abertura e fechamento por convenção."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    adapter = ConventionHarnessAdapter(kernel)
    _criar_setor_no_projeto(kernel, "setor-default")

    assert adapter.registrar_inicio_sessao("sess-conv-1", "setor-default") is True
    view = kernel.obter_view("main")
    assert view.contem_no("sess-conv-1") is True

    id_run = adapter.registrar_execucao_run("sess-conv-1", "deepseek-r1", {"latencia_ms": 250})
    view_apos_run = kernel.obter_view("main")
    assert view_apos_run.contem_no(id_run) is True

    assert adapter.registrar_fim_sessao("sess-conv-1", "Sucesso") is True
    no_sess = kernel.obter_view("main").obter_no("sess-conv-1")
    assert no_sess is not None
    assert no_sess.obter_propriedade("status") == "concluida"


def test_convention_adapter_multiplas_sessões_edge_case() -> None:
    """Caso de borda: criação de múltiplas sessões sequenciais por convenção."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    adapter = ConventionHarnessAdapter(kernel)
    _criar_setor_no_projeto(kernel, "setor-a")

    for i in range(1, 4):
        adapter.registrar_inicio_sessao(f"s-{i}", "setor-a")

    view = kernel.obter_view("main")
    # Projeto e Setor que hospedam as três sessões
    assert view.total_nos == 5
    assert all(view.contem_no(f"s-{i}") for i in range(1, 4))
