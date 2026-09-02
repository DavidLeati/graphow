"""Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução.

`HookHarnessAdapter` e `ConventionHarnessAdapter` não tinham chamador algum: as
classes existiam, nenhum script as invocava, e nenhum evento de execução era
emitido. Este serviço é o chamador que faltava, e o subcomando `graphow harness`
é a porta pela qual os hooks o alcançam. Ver achado A-12.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from graphow.core.events import TipoEvento
from graphow.harness.hook_adapter import HookHarnessAdapter
from graphow.harness.identidade_harness import IdentidadeHarness
from graphow.harness.interfaces import AdaptadorDeHarness
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.write_kernel import WriteKernel


class FaseDoHarness(str, Enum):
    """Momentos do ciclo de vida que o ambiente comunica ao grafo."""

    INICIO = "inicio"
    PROGRESSO = "progresso"
    FIM = "fim"


EVENTO_POR_FASE: Mapping[FaseDoHarness, TipoEvento] = {
    FaseDoHarness.INICIO: TipoEvento.EXECUCAO_SOLICITADA,
    FaseDoHarness.PROGRESSO: TipoEvento.EXECUCAO_INICIADA,
    FaseDoHarness.FIM: TipoEvento.EXECUCAO_CONCLUIDA,
}


@dataclass(frozen=True)
class PedidoDeCicloDeVida:
    """O que o hook informa ao grafo em cada disparo."""

    fase: FaseDoHarness
    id_sessao: str
    id_setor: str = ""
    modelo: str = "desconhecido"
    resumo: str = ""
    ramo_id: str = "main"
    metadados: Mapping[str, Any] = field(default_factory=dict)

    @property
    def id_run(self) -> str:
        """Identificador estável do Run, para as três fases atualizarem o mesmo nó."""
        return f"run-{self.id_sessao}"


@dataclass(frozen=True)
class ResultadoCicloDeVida:
    """Recibo do que o serviço conseguiu registrar no grafo."""

    sucesso: bool
    id_run: str
    mensagem: str
    versao_log: int = 0


class ServicoHarness:
    """Traduz cada disparo do hook em escrita no grafo, sob identidade fixada."""

    def __init__(
        self,
        kernel: WriteKernel,
        identidade: IdentidadeHarness | None = None,
        adaptador: AdaptadorDeHarness | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeHarness = identidade or IdentidadeHarness()
        self._adaptador: AdaptadorDeHarness = adaptador or HookHarnessAdapter(kernel, self._identidade)

    def registrar(self, pedido: PedidoDeCicloDeVida) -> ResultadoCicloDeVida:
        """Executa o efeito da fase sobre a sessão e emite o evento de execução."""
        self._ajustar_sessao(pedido)
        recibo = self._kernel.registrar_execucao(self._montar_pedido_de_execucao(pedido))
        return ResultadoCicloDeVida(
            sucesso=recibo.sucesso,
            id_run=pedido.id_run,
            mensagem=recibo.mensagem,
            versao_log=recibo.versao_log,
        )

    def _ajustar_sessao(self, pedido: PedidoDeCicloDeVida) -> None:
        """Abre a Sessao no início e a fecha no fim, ignorando fases intermediárias.

        O evento de execução é registrado de qualquer forma: um hook que roda
        fora de uma sessão declarada ainda produz telemetria válida.
        """
        if pedido.fase == FaseDoHarness.INICIO and pedido.id_setor:
            self._adaptador.registrar_inicio_sessao(
                pedido.id_sessao, pedido.id_setor, dict(pedido.metadados)
            )
            return
        if pedido.fase == FaseDoHarness.FIM and self._sessao_existe(pedido):
            self._adaptador.registrar_fim_sessao(pedido.id_sessao, pedido.resumo)

    def _sessao_existe(self, pedido: PedidoDeCicloDeVida) -> bool:
        """Consulta se há uma Sessao no grafo para fechar."""
        return self._kernel.obter_view(pedido.ramo_id).contem_no(pedido.id_sessao)

    def _montar_pedido_de_execucao(self, pedido: PedidoDeCicloDeVida) -> PedidoDeExecucao:
        """Descreve o evento de execução correspondente à fase informada."""
        return PedidoDeExecucao(
            id_run=pedido.id_run,
            id_sessao=pedido.id_sessao,
            tipo_evento=EVENTO_POR_FASE[pedido.fase],
            autor=self._identidade.autor,
            papel=self._identidade.papel,
            ramo_id=pedido.ramo_id,
            dados={"modelo": pedido.modelo, "resumo": pedido.resumo, **dict(pedido.metadados)},
        )
