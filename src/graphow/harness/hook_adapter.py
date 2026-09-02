"""Adaptador de ciclo de vida via hooks de harness (ex: Claude Code / IDE)."""

from collections.abc import Mapping
from typing import Any
import uuid

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.identidade_harness import IdentidadeHarness
from graphow.harness.interfaces import AdaptadorDeHarness
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


class HookHarnessAdapter(AdaptadorDeHarness):
    """Captura eventos de lifecycle automáticos via hooks e traduz para patches no kernel."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeHarness | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeHarness = identidade or IdentidadeHarness()

    def registrar_inicio_sessao(
        self,
        id_sessao: str,
        id_setor: str,
        metadados: Mapping[str, Any] | None = None,
    ) -> bool:
        """Emite patch de criação de Sessao e aresta 'contem' a partir do Setor."""
        props: dict[str, Any] = dict(metadados or {})
        props["status"] = "ativa"
        operacoes = [
            ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_sessao}", value={"id": id_sessao, "tipo": TipoNo.SESSAO.value, "rotulo": f"Sessao {id_sessao}", "propriedades": props}),
            ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/contem-{id_setor}-{id_sessao}", value={"id": f"contem-{id_setor}-{id_sessao}", "origem_id": id_setor, "destino_id": id_sessao, "tipo": TipoAresta.CONTEM.value}),
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Abertura de sessão via Hook")
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return recibo.sucesso

    def registrar_fim_sessao(
        self,
        id_sessao: str,
        resumo: str = "",
    ) -> bool:
        """Atualiza o status da sessão para concluída com anotação de resumo."""
        operacoes = [
            ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_sessao}/propriedades/status", value="concluida"),
            ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_sessao}/propriedades/resumo", value=resumo),
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Fechamento de sessão via Hook")
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return recibo.sucesso

    def registrar_execucao_run(
        self,
        id_sessao: str,
        modelo: str,
        dados_execucao: Mapping[str, Any],
    ) -> str:
        """Cria nó do tipo Run e conecta à Sessao via aresta 'ocorreu_em'."""
        id_run = f"run-{uuid.uuid4()}"
        props: dict[str, Any] = {"modelo": modelo, **dict(dados_execucao)}
        operacoes = [
            ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_run}", value={"id": id_run, "tipo": TipoNo.RUN.value, "rotulo": f"Execucao {modelo}", "propriedades": props}),
            ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/ocorreu-{id_run}", value={"id": f"ocorreu-{id_run}", "origem_id": id_run, "destino_id": id_sessao, "tipo": TipoAresta.OCORREU_EM.value}),
        ]
        dados = DadosPropostaPatch(autor=self._identidade.autor, papel=self._identidade.papel, operacoes=tuple(operacoes), justificativa="Registro de telemetria de Run")
        self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return id_run
