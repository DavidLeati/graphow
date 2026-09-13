"""Testes unitários para a identidade sob a qual o harness escreve no grafo."""

import pytest

from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.types import PapelAutor, TipoNo
from graphow.harness.hook_adapter import HookHarnessAdapter
from graphow.harness.identidade_harness import IdentidadeHarness
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


def _criar_setor(kernel: WriteKernel, id_setor: str) -> None:
    """Cria o Setor que hospedará as sessões registradas pelo harness."""
    operacao = ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_setor}",
        value={"id": id_setor, "tipo": TipoNo.SETOR.value, "rotulo": "Engenharia"},
    )
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=(operacao,), justificativa="setor"
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))


def test_identidade_padrao_e_o_papel_sistema_nominal() -> None:
    """Um harness sem configuração explícita escreve como sistema, não como humano."""
    identidade = IdentidadeHarness()
    assert identidade.papel == PapelAutor.SISTEMA
    assert identidade.autor == "harness"


def test_hook_registra_sessao_sob_papel_sistema_nominal() -> None:
    """A sessão criada pelo hook fica registrada com a autoria correta no log."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel, "setor-1")

    assert HookHarnessAdapter(kernel).registrar_inicio_sessao("sess-1", "setor-1") is True

    eventos = [evento for evento in kernel.repositorio.ler_eventos("main") if evento.autor == "harness"]
    assert eventos
    assert all(evento.papel == PapelAutor.SISTEMA for evento in eventos)


def test_harness_nao_pode_assumir_papel_de_agente_edge_case() -> None:
    """Caso de borda: papéis de agente são recusados na construção da identidade."""
    for papel in (PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR):
        with pytest.raises(ErroPermissaoPapel):
            IdentidadeHarness(autor="hook", papel=papel)


def test_harness_como_sistema_nao_cria_tarefas_edge_case() -> None:
    """Caso de borda: o portão de papéis barra o harness fora da telemetria."""
    kernel = montar_kernel_em_memoria()
    operacao = ItemPatch(
        op=OperacaoPatch.ADD,
        path="/nos/task-1",
        value={"id": "task-1", "tipo": TipoNo.TASK.value, "rotulo": "Tarefa"},
    )
    dados = DadosPropostaPatch(
        autor="harness", papel=PapelAutor.SISTEMA, operacoes=(operacao,), justificativa="tentativa"
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso is False
    assert recibo.modo_de_falha == "violacao_permissao_papel"


def test_identidade_humana_explicita_e_aceita_edge_case() -> None:
    """Caso de borda: o humano pode declarar o próprio harness, ao configurá-lo."""
    identidade = IdentidadeHarness(autor="david", papel=PapelAutor.HUMANO)
    assert identidade.papel == PapelAutor.HUMANO
