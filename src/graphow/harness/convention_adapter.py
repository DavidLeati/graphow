"""Adaptador de fallback baseado em convenção de chamada explícita."""

from collections.abc import Mapping
from typing import Any

from graphow.core.types import PapelAutor, TipoNo
from graphow.harness.identidade_harness import IdentidadeHarness
from graphow.harness.interfaces import AdaptadorDeHarness
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


class ConventionHarnessAdapter(AdaptadorDeHarness):
    """Adaptador agnóstico para ambientes sem suporte a hooks de ciclo de vida nativos."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeHarness | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeHarness = identidade or IdentidadeHarness()

    def registrar_inicio_sessao(
        self,
        id_sessao: str,
        id_setor: str,
        metadados: Mapping[str, Any] | None = None,
    ) -> bool:
        """Cria o nó de Sessao no grafo caso ainda não exista."""
        props = dict(metadados or {})
        props["setor_pai"] = id_setor
        props["status"] = "iniciada_por_convencao"
        operacoes = [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/nos/{id_sessao}",
                value={"id": id_sessao, "tipo": TipoNo.SESSAO.value, "rotulo": f"Sessao {id_sessao}", "propriedades": props},
            )
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Abertura por convenção")
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return recibo.sucesso

    def registrar_fim_sessao(self, id_sessao: str, resumo: str = "") -> bool:
        """Atualiza a sessão como concluída."""
        operacoes = [
            ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_sessao}/propriedades/status", value="concluida"),
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Fechamento por convenção")
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return recibo.sucesso

    def registrar_execucao_run(
        self,
        id_sessao: str,
        modelo: str,
        dados_execucao: Mapping[str, Any],
    ) -> str:
        """Registra nó Run simplificado."""
        id_run = f"run-conv-{id_sessao}"
        props = {"modelo": modelo, **dict(dados_execucao)}
        operacoes = [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/nos/{id_run}",
                value={"id": id_run, "tipo": TipoNo.RUN.value, "rotulo": f"Run {modelo}", "propriedades": props},
            )
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Run por convenção")
        self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return id_run
