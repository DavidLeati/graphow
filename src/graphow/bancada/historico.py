"""A medida `historico`: a suíte do projeto em cada commit da branch entregue, depois da semente.

O orquestrador só commita a fatia com a suíte verde; a exceção legítima é o
commit com `Graphow-Aceite: vermelho` (os testes de aceite, e o que vem antes
da primeira fatia, com o código da base). A medida confere isso de fora: num
clone do repositório da execução, faz checkout de cada commit de
`semente..ramo`, do mais antigo ao mais novo, roda o comando da suíte do
plano pelo mesmo caminho que o orquestrador (`rodar_suite`: o shell dos
agentes, banco descartável, sem cache) e conta os verdes, os vermelhos
esperados (com o trailer) e os inesperados. Os testes de aceite não ficam
ocultos, como na suíte da fatia: vale o comando como o plano o declarou, o
que um `git bisect run` veria.

Cada suíte tem o seu tempo-limite. A que estoura, ou o commit em que o git
falha, conta como vermelho daquele commit, e os outros seguem. O comando vem
do plano do Goal no livro-razão da execução (`orquestrar.json` diz o Goal);
a arquitetura sem plano (a `enxuta`) fica sem a medida, com o motivo, a menos
que o comando seja dado.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from graphow.bancada.arquitetura_orquestrar import ARQUIVO_DA_PARADA
from graphow.core.exceptions import GraphowError
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.orquestrador.git_do_goal import ACEITE_VERMELHO, TRAILER_DO_ACEITE, CommitDoGit, GitDoGoal, commits_entre, remover_area
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.suite import rodar_suite
from graphow.storage.sqlite_store import SQLiteEventStore

VERDE: str = "verde"
VERMELHO_ESPERADO: str = "vermelho_esperado"
VERMELHO_INESPERADO: str = "vermelho_inesperado"
TEMPO_LIMITE_DA_SUITE_S: float = 600.0
PASTA_DO_CLONE: str = "clone"
BANCO_DESCARTAVEL: str = "graphow-descartavel.db"
# O fim da saída da suíte vermelha que fica no registro, para dizer por que ela falhou.
LIMITE_DO_FIM_DA_SAIDA: int = 1500


@dataclass(frozen=True)
class CommitMedido:
    """Um commit da branch: o hash, o assunto, a situação da suíte nele, o código de saída e o fim da saída do vermelho."""

    commit: str
    assunto: str
    situacao: str
    codigo: int | None
    tempo_esgotado: bool = False
    fim_da_saida: str = ""


@dataclass(frozen=True)
class Historico:
    """A suíte commit a commit, ou por que ela não foi medida (`erro`)."""

    comando: str
    commits: tuple[CommitMedido, ...] = ()
    erro: str = ""

    def contar(self, situacao: str) -> int:
        """Quantos commits saíram na situação dada."""
        return sum(1 for commit in self.commits if commit.situacao == situacao)

    def resumo(self) -> str:
        """Verdes, vermelhos esperados e inesperados, numa linha."""
        if self.erro:
            return f"historico nao medido: {self.erro}"
        return (f"{self.contar(VERDE)} verde(s), {self.contar(VERMELHO_ESPERADO)} vermelho(s) esperado(s), "
                f"{self.contar(VERMELHO_INESPERADO)} vermelho(s) inesperado(s) em {len(self.commits)} commit(s)")

    def em_dicionario(self) -> dict[str, Any]:
        """A medida como `execucao.json` a grava."""
        return {"comando": self.comando, "verdes": self.contar(VERDE), "vermelhos_esperados": self.contar(VERMELHO_ESPERADO),
                "vermelhos_inesperados": self.contar(VERMELHO_INESPERADO), "erro": self.erro,
                "commits": [asdict(commit) for commit in self.commits]}


def medir_historico(repositorio: Path, comando: str, *, semente: str, ramo: str,
                    tempo_limite_s: float = TEMPO_LIMITE_DA_SUITE_S) -> Historico:
    """A suíte em cada commit de `semente..ramo`, num clone descartável; a falha do git que impede tudo vira o erro."""
    if not comando.strip():
        return Historico("", erro="sem comando da suite (a arquitetura nao tem plano)")
    pasta = Path(tempfile.mkdtemp(prefix="graphow-historico-"))
    try:
        commits = tuple(reversed(commits_entre(repositorio, semente, ramo)))
        GitDoGoal(pasta).rodar("clone", "-q", "--local", "--no-checkout", str(repositorio), str(pasta / PASTA_DO_CLONE))
        medidos = tuple(_medir_commit(pasta, comando, commit, tempo_limite_s=tempo_limite_s) for commit in commits)
    except (GraphowError, OSError) as erro:
        return Historico(comando, erro=erro.formatar_para_llm() if isinstance(erro, GraphowError) else str(erro))
    finally:
        remover_area(pasta)
    return Historico(comando, medidos)


def _medir_commit(pasta: Path, comando: str, commit: CommitDoGit, *, tempo_limite_s: float) -> CommitMedido:
    """O checkout limpo do commit no clone e a suíte nele; o git que falha ali é o vermelho deste commit só."""
    clone = pasta / PASTA_DO_CLONE
    assunto = (commit.mensagem.strip().splitlines() or [""])[0]
    vermelho = VERMELHO_ESPERADO if commit.tem_trailer(TRAILER_DO_ACEITE, ACEITE_VERMELHO) else VERMELHO_INESPERADO
    git = GitDoGoal(clone)
    checkout = git.tentar("checkout", "-q", "--force", "--detach", commit.hash)
    limpeza = git.tentar("clean", "-q", "-fdx")
    if checkout.codigo != 0 or limpeza.codigo != 0:
        return CommitMedido(commit.hash, assunto, vermelho, None, fim_da_saida=f"git: {checkout.erro or limpeza.erro}".strip())
    suite = rodar_suite(clone, comando, pasta / BANCO_DESCARTAVEL, tempo_limite_s=tempo_limite_s)
    if suite.passou:
        return CommitMedido(commit.hash, assunto, VERDE, suite.codigo)
    return CommitMedido(commit.hash, assunto, vermelho, suite.codigo, suite.tempo_esgotado, suite.saida[-LIMITE_DO_FIM_DA_SAIDA:])


@dataclass(frozen=True)
class PedidoDoHistorico:
    """A execução a medir: a pasta (com `orquestrar.json`), o repositório, o banco, a semente, o ramo e o tempo de cada suíte.

    Sem `comando`, vale o do plano do Goal no livro-razão.
    """

    execucao: Path
    repositorio: Path
    banco: Path
    semente: str
    ramo: str
    tempo_limite_s: float = TEMPO_LIMITE_DA_SUITE_S
    comando: str = ""


def comando_do_plano(execucao: Path, banco: Path) -> str:
    """O comando da suíte do plano do Goal da execução, lido do livro-razão dela; vazio sem Goal ou sem plano."""
    parada = execucao / ARQUIVO_DA_PARADA
    if not parada.is_file() or not banco.is_file():
        return ""
    dados = json.loads(parada.read_text(encoding="utf-8"))
    id_goal = str(dados.get("id_goal") or "") if isinstance(dados, dict) else ""
    with SQLiteEventStore(banco) as store:
        estado = ler_estado(montar_kernel_sqlite(store).obter_view(), id_goal)
    plano = (estado.plano if estado is not None else None) or {}
    return str(plano.get("comando_suite") or "")


def historico_da_execucao(pedido: PedidoDoHistorico) -> Historico:
    """A medida sobre uma execução, com o comando dado ou o do plano; a falha ao ler a execução vira o erro, e nunca sobe."""
    try:
        comando = pedido.comando or comando_do_plano(pedido.execucao, pedido.banco)
        return medir_historico(pedido.repositorio, comando, semente=pedido.semente, ramo=pedido.ramo,
                               tempo_limite_s=pedido.tempo_limite_s)
    except (GraphowError, OSError, ValueError) as erro:
        return Historico(pedido.comando, erro=erro.formatar_para_llm() if isinstance(erro, GraphowError) else str(erro))
