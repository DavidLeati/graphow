"""Serviço que liga os hooks do ambiente ao grafo: abre, marca e fecha a execução.

`HookHarnessAdapter` e `ConventionHarnessAdapter` não tinham chamador algum: as
classes existiam, nenhum script as invocava, e nenhum evento de execução era
emitido. Este serviço é o chamador que faltava, e o subcomando `graphow harness`
é a porta pela qual os hooks o alcançam.

A sessão nasce onde o hook mandar ou, sem `--setor`, no ambiente padrão do
repositório em que ele roda: o Projeto com o nome da pasta e o Setor `Memoria`.
Sem isso o hook sem Setor só registrava telemetria, e a memória não acontecia.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from graphow.core.events import TipoEvento
from graphow.core.types import StatusSessao, TipoAresta
from graphow.harness.ambiente_padrao import AmbientePadrao, GarantidorDeAmbientePadrao
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
    """O que o hook informa ao grafo em cada disparo.

    `diretorio_de_trabalho` é de onde o hook rodou: é ele que nomeia o ambiente
    padrão quando `id_setor` vem vazio. Vazio também, vale o diretório do processo.
    `resumo` é o que alguém declara sobre a sessão; `motivo` é o que o ambiente
    diz do disparo (`source` no início, `reason` no fim) e vai para o Run.
    """

    fase: FaseDoHarness
    id_sessao: str
    id_setor: str = ""
    modelo: str = "desconhecido"
    resumo: str = ""
    ramo_id: str = "main"
    metadados: Mapping[str, Any] = field(default_factory=dict)
    diretorio_de_trabalho: str = ""
    motivo: str = ""

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
    id_setor: str = ""


class ServicoHarness:
    """Traduz cada disparo do hook em escrita no grafo, sob identidade fixada."""

    def __init__(
        self,
        kernel: WriteKernel,
        identidade: IdentidadeHarness | None = None,
        adaptador: AdaptadorDeHarness | None = None,
        *,
        garantidor: GarantidorDeAmbientePadrao | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeHarness = identidade or IdentidadeHarness()
        self._adaptador: AdaptadorDeHarness = adaptador or HookHarnessAdapter(kernel, self._identidade)
        self._garantidor: GarantidorDeAmbientePadrao = garantidor or GarantidorDeAmbientePadrao(
            kernel, self._identidade
        )

    def registrar(self, pedido: PedidoDeCicloDeVida) -> ResultadoCicloDeVida:
        """Executa o efeito da fase sobre a sessão e emite o evento de execução."""
        id_setor = self._ajustar_sessao(pedido)
        recibo = self._kernel.registrar_execucao(self._montar_pedido_de_execucao(pedido))
        return ResultadoCicloDeVida(
            sucesso=recibo.sucesso,
            id_run=pedido.id_run,
            mensagem=recibo.mensagem,
            versao_log=recibo.versao_log,
            id_setor=id_setor,
        )

    def _ajustar_sessao(self, pedido: PedidoDeCicloDeVida) -> str:
        """Abre a Sessao no início e a fecha no fim, ignorando fases intermediárias.

        O evento de execução é registrado de qualquer forma: um hook que roda
        fora de uma sessão declarada ainda produz telemetria válida. Devolve o
        Setor em que a sessão está, quando a fase o conhece.
        """
        if pedido.fase == FaseDoHarness.INICIO:
            return self._abrir_sessao(pedido)
        if pedido.fase == FaseDoHarness.FIM and self._sessao_existe(pedido):
            self._adaptador.registrar_fim_sessao(pedido.id_sessao, pedido.resumo)
        return ""

    def _abrir_sessao(self, pedido: PedidoDeCicloDeVida) -> str:
        """Sessão existente é retomada, reaberta se o fim já a encerrou; sem Setor, o ambiente padrão responde."""
        if self._sessao_existe(pedido):
            self._reabrir_se_encerrada(pedido)
            return self._setor_da_sessao(pedido)
        id_setor = pedido.id_setor or self._garantidor.garantir(
            AmbientePadrao.do_diretorio(pedido.diretorio_de_trabalho), pedido.ramo_id
        )
        if id_setor:
            self._adaptador.registrar_inicio_sessao(pedido.id_sessao, id_setor, dict(pedido.metadados))
        return id_setor

    def _reabrir_se_encerrada(self, pedido: PedidoDeCicloDeVida) -> None:
        """O ambiente retoma sessões que o hook de fim já encerrou; o status volta a dizer a verdade.

        Sem isto a sessão retomada seguia `concluida` enquanto o agente
        trabalhava nela, e o painel a mostrava fechada com o fechamento parado.
        """
        sessao = self._kernel.obter_view(pedido.ramo_id).obter_no(pedido.id_sessao)
        if sessao is None or str(sessao.obter_propriedade("status")) != StatusSessao.CONCLUIDA.value:
            return
        self._adaptador.registrar_reabertura_sessao(pedido.id_sessao)

    def _sessao_existe(self, pedido: PedidoDeCicloDeVida) -> bool:
        """Consulta se há uma Sessao no grafo para fechar."""
        return self._kernel.obter_view(pedido.ramo_id).contem_no(pedido.id_sessao)

    def _setor_da_sessao(self, pedido: PedidoDeCicloDeVida) -> str:
        """O Setor que contém a sessão já aberta, para o recibo dizer onde ela está."""
        arestas = self._kernel.obter_view(pedido.ramo_id).obter_arestas_entrada(pedido.id_sessao, TipoAresta.CONTEM)
        return arestas[0].origem_id if arestas else ""

    def _montar_pedido_de_execucao(self, pedido: PedidoDeCicloDeVida) -> PedidoDeExecucao:
        """Descreve o evento de execução correspondente à fase informada."""
        return PedidoDeExecucao(
            id_run=pedido.id_run,
            id_sessao=pedido.id_sessao,
            tipo_evento=EVENTO_POR_FASE[pedido.fase],
            autor=self._identidade.autor,
            papel=self._identidade.papel,
            ramo_id=pedido.ramo_id,
            dados={"modelo": pedido.modelo, "resumo": pedido.resumo, "motivo": pedido.motivo, **dict(pedido.metadados)},
        )
