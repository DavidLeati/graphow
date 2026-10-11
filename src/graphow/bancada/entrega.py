"""O estado git da entrega: o ramo de trabalho, os commits depois da semente e a árvore suja.

O laboratório mostrou as três formas de entregar: commits no ramo pedido (a
enxuta), commits no ramo com a árvore deixada em outro (o estoque do graphow) e
nada commitado (a agenda e a api do graphow). Os commits contam só o ramo de
trabalho depois da semente; o auditor recebe o ramo descrito do mesmo jeito
que os auditores do laboratório receberam, com a ressalva de onde o trabalho
está quando não está no ramo.
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.bancada.projetos import ErroDaBancada, ProjetoDaBancada
from graphow.bancada.semente import GitDaBancada


@dataclass(frozen=True)
class EstadoDaEntrega:
    """Onde a entrega está no repositório da execução."""

    ramo: str
    ramo_existe: bool
    ramo_atual: str
    commits: int
    arvore_suja: bool

    def em_dicionario(self) -> dict[str, object]:
        """O estado para gravar em JSON."""
        return {
            "ramo": self.ramo,
            "ramo_existe": self.ramo_existe,
            "ramo_atual": self.ramo_atual,
            "commits": self.commits,
            "arvore_suja": self.arvore_suja,
        }


def ler_estado_da_entrega(repositorio: Path, projeto: ProjetoDaBancada) -> EstadoDaEntrega:
    """O ramo de trabalho, os commits nele depois da semente, o ramo do HEAD e se há mudança fora de commit."""
    git = GitDaBancada(repositorio)
    existe = _ramo_existe(git, projeto.ramo)
    commits = int(git.rodar("rev-list", "--count", projeto.ramo, f"^{projeto.semente.commit}").strip()) if existe else 0
    return EstadoDaEntrega(
        ramo=projeto.ramo,
        ramo_existe=existe,
        ramo_atual=git.rodar("branch", "--show-current").strip(),
        commits=commits,
        arvore_suja=bool(git.rodar("status", "--porcelain").strip()),
    )


def descrever_ramo(estado: EstadoDaEntrega) -> str:
    """O ramo como o prompt do auditor o recebe, com a ressalva quando o trabalho não está nele."""
    if not estado.ramo_existe:
        return f"{estado.ramo_atual} (o trabalho está NÃO commitado no working tree; use o working tree como está)"
    if estado.ramo_atual != estado.ramo:
        return (
            f"{estado.ramo} (o working tree está na {estado.ramo_atual}; "
            f"leia a branch {estado.ramo} por worktree temporário)"
        )
    return estado.ramo


def _ramo_existe(git: GitDaBancada, ramo: str) -> bool:
    """O ramo local aponta para um commit."""
    try:
        git.rodar("rev-parse", "--verify", "--quiet", f"refs/heads/{ramo}")
    except ErroDaBancada:
        return False
    return True
