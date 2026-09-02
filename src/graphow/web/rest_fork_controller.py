"""Controlador REST especializado na gestão de ramos, criação de Forks e Diff estrutural."""

from typing import Any

from graphow.core.exceptions import ErroEntidadeNaoEncontrada, GraphowError
from graphow.kernel.write_kernel import WriteKernel
from graphow.lineage.fork_manager import ForkManager, PedidoFork
from graphow.lineage.replay_engine import ReplayEngine
from graphow.web.dto import RequisicaoCriarFork, RespostaReciboWeb
from graphow.web.identidade_web import IdentidadeSessaoWeb


class ForkWebController:
    """Controlador para bifurcação histórica e comparação visual de ramos."""

    def __init__(
        self,
        kernel: WriteKernel,
        identidade: IdentidadeSessaoWeb | None = None,
        fork_manager: ForkManager | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb()
        self._fork_manager: ForkManager = fork_manager or ForkManager(kernel.repositorio, kernel.repositorio_ramos)
        self._replay_engine: ReplayEngine = ReplayEngine(kernel.repositorio)

    def criar_fork(self, req: RequisicaoCriarFork) -> RespostaReciboWeb:
        """Cria um novo ramo a partir de um evento de corte especificado."""
        id_corte = req.evento_id_ponto_corte
        if id_corte is None:
            ultimo = self._obter_ultimo_evento_id(req.ramo_origem)
            if ultimo is None:
                return RespostaReciboWeb(sucesso=False, mensagem=f"Ramo origem '{req.ramo_origem}' sem eventos")
            id_corte = ultimo
        pedido = PedidoFork(
            ramo_origem=req.ramo_origem,
            id_evento_corte=id_corte,
            novo_ramo_id=req.novo_ramo,
            autor=self._identidade.autor,
        )
        return self._executar_fork(pedido, id_corte)

    def _executar_fork(self, pedido: PedidoFork, id_corte: str) -> RespostaReciboWeb:
        """Registra a ramificação convertendo falhas de domínio em recibo negativo."""
        try:
            self._fork_manager.criar_fork(pedido)
        except ErroEntidadeNaoEncontrada as erro:
            return RespostaReciboWeb(sucesso=False, mensagem=erro.mensagem)
        except GraphowError as erro:
            return RespostaReciboWeb(sucesso=False, mensagem=erro.mensagem)
        return RespostaReciboWeb(
            sucesso=True,
            mensagem=f"Ramo '{pedido.novo_ramo_id}' criado a partir de '{id_corte}'",
        )

    def _obter_ultimo_evento_id(self, ramo_id: str) -> str | None:
        """Localiza o identificador do evento mais recente no ramo de origem."""
        eventos = self._kernel.repositorio.ler_eventos(ramo_id)
        if not eventos:
            return None
        return eventos[-1].id

    def calcular_diff_ramos(self, ramo_a: str, ramo_b: str) -> dict[str, Any]:
        """Calcula as discrepâncias estruturais entre dois ramos forkados."""
        estado_a = self._kernel.obter_estado(ramo_a)
        estado_b = self._kernel.obter_estado(ramo_b)
        diff_bruto = self._replay_engine.calcular_diff(estado_a, estado_b)
        return {
            "ramo_a": ramo_a,
            "ramo_b": ramo_b,
            "nos_adicionados": diff_bruto["nos_adicionados"],
            "nos_removidos": diff_bruto["nos_removidos"],
            "nos_comuns": diff_bruto["nos_comuns"],
            "arestas_adicionadas": diff_bruto["arestas_adicionadas"],
            "arestas_removidas": diff_bruto["arestas_removidas"],
        }

    def listar_ramos(self) -> list[str]:
        """Lista todos os ramos existentes no repositório."""
        return list(self._kernel.listar_ramos())
