"""Testes unitários para HookHarnessAdapter."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.hook_adapter import HookHarnessAdapter
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
)
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore


def _criar_ambiente_com_setor() -> tuple[WriteKernel, HookHarnessAdapter]:
    """Cria repositório, kernel com Setor pré-existente e adaptador."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    # Pré-cria Projeto e Setor
    dados = DadosPropostaPatch(
        "david",
        PapelAutor.HUMANO,
        [
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/proj-1", value={"id": "proj-1", "tipo": TipoNo.PROJETO.value}),
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/setor-1", value={"id": "setor-1", "tipo": TipoNo.SETOR.value}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e-contem", value={
                "id": "e-contem", "origem_id": "proj-1", "destino_id": "setor-1", "tipo": TipoAresta.CONTEM.value
            }),
        ],
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))
    adapter = HookHarnessAdapter(kernel)
    return kernel, adapter


def test_hook_adapter_ciclo_vida_nominal() -> None:
    """Testa abertura de sessão, registro de run e fechamento via hooks."""
    kernel, adapter = _criar_ambiente_com_setor()

    # Início de sessão
    sucesso_inicio = adapter.registrar_inicio_sessao("sess-100", "setor-1", {"contexto": "testes"})
    assert sucesso_inicio is True

    view = kernel.obter_view("main")
    assert view.contem_no("sess-100") is True

    # Registro de Run
    id_run = adapter.registrar_execucao_run("sess-100", "claude-3-7-sonnet", {"tokens": 1200})
    assert id_run.startswith("run-")
    view_apos_run = kernel.obter_view("main")
    assert view_apos_run.contem_no(id_run) is True

    # Fim de sessão
    sucesso_fim = adapter.registrar_fim_sessao("sess-100", "Concluído com sucesso")
    assert sucesso_fim is True
    no_sess = kernel.obter_view("main").obter_no("sess-100")
    assert no_sess is not None
    assert no_sess.obter_propriedade("status") == "concluida"


def test_hook_adapter_setor_inexistente_edge_case() -> None:
    """Caso de borda: vinculação a setor inexistente falha na validação do schema."""
    _, adapter = _criar_ambiente_com_setor()
    sucesso = adapter.registrar_inicio_sessao("sess-err", "setor-fantasma")
    assert sucesso is False
