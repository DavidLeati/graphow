"""O que cada passo do laço recebe: o Goal, a configuração, as sessões, o orçamento e onde gravar.

As opções vêm da linha de comando; as dependências (kernel, executor de
sessão, telemetria e a pasta de estado) vêm de quem monta o laço, a CLI ou a
bancada. A parada diz por que o laço parou e o que falta para seguir.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal
from graphow.orquestrador.sessoes_de_papel import MODO_DE_PERMISSAO_PADRAO, SessoesDePapel
from graphow.orquestrador.suite import TEMPO_LIMITE_DA_SUITE_S
from graphow.sessoes.pedido import TEMPO_LIMITE_PADRAO_S
from graphow.sessoes.sessao_claude import ExecutorDeSessao
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria

MAXIMO_DE_TENTATIVAS: int = 2
MAXIMO_DE_CICLOS_DE_CORRECAO: int = 2
ORCAMENTO_PADRAO_USD: float = 30.0


class GoalInexistente(GraphowError):
    """O Goal pedido não está no livro-razão."""


class MotivoDaParada(str, Enum):
    """Por que o laço devolveu a palavra."""

    FECHADO = "fechado"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    AGUARDANDO_RESPOSTA = "aguardando_resposta"
    PENDENCIA = "pendencia"
    ORCAMENTO = "orcamento"
    PRONTO_PARA_INTEGRAR = "pronto_para_integrar"
    BLOQUEANTES_RESTANTES = "bloqueantes_restantes"
    FALHA = "falha"


@dataclass(frozen=True)
class Parada:
    """O laço parou: em que Goal, por quê e o que fazer para seguir."""

    id_goal: str
    motivo: MotivoDaParada
    mensagem: str

    @property
    def fechou(self) -> bool:
        """O Goal fechou."""
        return self.motivo == MotivoDaParada.FECHADO


@dataclass(frozen=True)
class OpcoesDoLaco:
    """O que a chamada pede; None quer dizer "o que já está gravado no Goal, ou o padrão"."""

    modo: str | None = None
    ramo: str = ""
    base: str = ""
    orcamento_usd: float | None = None
    area: Path | None = None
    tempo_limite_da_suite_s: float = TEMPO_LIMITE_DA_SUITE_S


@dataclass(frozen=True)
class DependenciasDoLaco:
    """O que o laço usa e não decide: o grafo, as sessões, a telemetria e onde guardar o estado de cada Goal."""

    kernel: WriteKernel
    executor: ExecutorDeSessao
    telemetria: RepositorioTelemetria
    pasta_de_estado: Path
    modelos: Mapping[str, str] = field(default_factory=dict)
    modo_de_permissao: str = MODO_DE_PERMISSAO_PADRAO
    tempo_limite_da_sessao_s: float = TEMPO_LIMITE_PADRAO_S


@dataclass(frozen=True)
class ContextoDoGoal:
    """Um Goal sendo conduzido: o livro-razão, a configuração gravada e as sessões dele."""

    livro: LivroRazaoDoGoal
    configuracao: m.ConfiguracaoDoGoal
    sessoes: SessoesDePapel
    telemetria: RepositorioTelemetria
    pasta: Path
    opcoes: OpcoesDoLaco

    @property
    def id_goal(self) -> str:
        """O Goal."""
        return self.livro.id_goal

    @property
    def area(self) -> Path:
        """O worktree do Goal."""
        return Path(self.configuracao.area)

    @property
    def git(self) -> GitDoGoal:
        """O git da área."""
        return GitDoGoal(self.area)

    @property
    def banco_descartavel(self) -> Path:
        """O banco que a suíte e os hooks das sessões recebem, para não escreverem no do usuário."""
        return self.pasta / "descartavel.db"

    def estado(self) -> EstadoDoGoal:
        """O estado do Goal relido do livro-razão."""
        estado = ler_estado(self.livro.view(), self.id_goal)
        if estado is None:
            raise GoalInexistente("Goal nao encontrado no livro-razao", {"id_goal": self.id_goal})
        return estado

    def patch(self, nome: str) -> Path:
        """Onde guardar o que uma tentativa deixou fora de commit."""
        return self.pasta / "patches" / f"{nome}.patch"

    def gasto(self) -> float:
        """O custo conhecido das sessões do Goal até agora."""
        return self.telemetria.totais(self.id_goal).custo_usd

    def restante(self) -> float:
        """O que sobra do orçamento."""
        return self.configuracao.orcamento_usd - self.gasto()

    def sem_orcamento(self) -> Parada | None:
        """A parada por orçamento, quando ele acabou; None quando ainda dá para abrir sessão."""
        gasto = self.gasto()
        if gasto < self.configuracao.orcamento_usd:
            return None
        return Parada(
            self.id_goal,
            MotivoDaParada.ORCAMENTO,
            f"Orcamento do Goal esgotado: US$ {gasto:.2f} de US$ {self.configuracao.orcamento_usd:.2f}. "
            f"Para seguir, rode de novo com --orcamento-usd maior.",
        )
