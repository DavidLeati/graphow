"""As refs do repositório do humano que o orquestrador move: a base, na integração, e a branch do Goal, depois do rebase.

Toda mudança de ref aqui é condicional e vai a um commit dado, e não ao que
um nome aponta. A integração recebe o commit que a verificação final viu e só
leva a base até ele: a branch do Goal que andou no repositório do humano
depois da verificação para a integração, e o commit que ninguém verificou não
chega à base (revisão da T3g3 e da T3g4, R3: a integração relia a ponta pelo
nome da branch, e o fast-forward da branch do Goal passa pela foto do humano
como avanço). A base anda com `update-ref <base> <verificado> <antigo>`, e o git
recusa se ela andou no meio; o laço, que vê a base fora da história da branch,
volta ao rebase. Antes, a base era forçada (`branch -f`) até a branch do Goal,
e o commit que o humano fizesse nela entre a conferência e o fast-forward
sumia.

Nenhuma das duas refs anda por baixo de um checkout: a base aberta no checkout
do humano avança pelo `merge --ff-only` dele (o git recusa se isso apagar
mudança dele), e a base ou a branch do Goal aberta em qualquer worktree do
repositório (`git worktree list --porcelain`) não se move.
"""

from pathlib import Path

from graphow.orquestrador.git_do_goal import FalhaDoGitDoGoal, GitDoGoal

PREFIXO_DO_WORKTREE: str = "worktree "
PREFIXO_DA_BRANCH: str = "branch "


def worktree_do_ramo(repositorio: Path, ramo: str) -> str:
    """A pasta do worktree do repositório (o principal inclusive) em que a branch está aberta; vazio quando em nenhum."""
    campos = GitDoGoal(repositorio).rodar("worktree", "list", "--porcelain", "-z").split("\x00")
    alvo = f"{PREFIXO_DA_BRANCH}refs/heads/{ramo}"
    if alvo not in campos:
        return ""
    antes = reversed(campos[:campos.index(alvo)])
    return next((campo[len(PREFIXO_DO_WORKTREE):] for campo in antes if campo.startswith(PREFIXO_DO_WORKTREE)), "")


def integrar_por_fast_forward(repositorio: Path, ramo: str, base: str, *, verificado: str) -> str:
    """Avança a base até o commit verificado, só por fast-forward e só se a base e a branch do Goal estão onde a conferência
    as viu; devolve o integrado.

    A branch do Goal que não está mais no commit verificado (alguém a andou
    depois da verificação) recusa a integração, e a base fica. Com a base no
    checkout do humano, é o `merge --ff-only <verificado>` ali. Fora dele,
    `update-ref` com o valor antigo da base, que o git recusa se ela andou; a
    base aberta em outro worktree fica como está.
    """
    git = GitDoGoal(repositorio)
    antigo, ponta = (git.rodar("rev-parse", "--verify", f"refs/heads/{nome}").strip() for nome in (base, ramo))
    if ponta != verificado:
        raise FalhaDoGitDoGoal("a branch do Goal andou depois da verificacao: so o commit verificado vai a base",
                               {"ramo": ramo, "ponta": ponta[:12], "verificado": verificado[:12]})
    if not git.e_ancestral(antigo, verificado):
        raise FalhaDoGitDoGoal("a base andou desde que a branch do Goal saiu dela: nao ha fast-forward", {"base": base, "ramo": ramo})
    aberta = worktree_do_ramo(repositorio, base)
    if aberta and git.ramo_atual() == base:
        git.rodar("merge", "-q", "--ff-only", verificado)
    elif aberta:
        raise FalhaDoGitDoGoal("a base esta aberta em outro worktree do repositorio: o orquestrador nao a move por baixo dele",
                               {"base": base, "worktree": aberta})
    else:
        git.rodar("update-ref", "-m", f"graphow: fast-forward de {base} ate {verificado[:12]} ({ramo})", f"refs/heads/{base}",
                  verificado, antigo)
    return verificado


def recusar_se_aberta(repositorio: Path, ramo: str, *, antes: str, depois: str) -> None:
    """Recusa mover a branch do Goal quando ela está aberta num worktree do repositório do humano, o checkout dele inclusive."""
    aberta = worktree_do_ramo(repositorio, ramo)
    if aberta:
        raise FalhaDoGitDoGoal("a branch do Goal esta aberta no checkout do humano: o rebase nao a move por baixo dele",
                               {"ramo": ramo, "worktree": aberta, "antes": antes[:12], "depois": depois[:12]})
