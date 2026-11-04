"""As refs do repositório do humano que o orquestrador move: a base, na integração, e a branch do Goal, depois do rebase.

Toda mudança de ref aqui é condicional: ela só anda se ainda está no commit
que o orquestrador conferiu. A integração lia a base, conferia o
fast-forward e depois forçava a base (`branch -f`) até a branch do Goal: o
commit que o humano fizesse na base entre os dois sumia dela. Agora a base
anda com `update-ref <base> <ponta> <antigo>`, e o git recusa se ela andou
no meio; o laço, que vê a base fora da história da branch, volta ao rebase.

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


def integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str:
    """Avança a base até a branch do Goal, só por fast-forward e só se ela não andou desde a conferência; devolve o integrado.

    Com a base no checkout do humano, é o `merge --ff-only` ali. Fora dele,
    `update-ref` com o valor antigo da base, que o git recusa se ela andou; a
    base aberta em outro worktree fica como está.
    """
    git = GitDoGoal(repositorio)
    antigo, ponta = (git.rodar("rev-parse", "--verify", f"refs/heads/{nome}").strip() for nome in (base, ramo))
    if not git.e_ancestral(antigo, ponta):
        raise FalhaDoGitDoGoal(
            "a base andou desde que a branch do Goal saiu dela: nao ha fast-forward", {"base": base, "ramo": ramo}
        )
    aberta = worktree_do_ramo(repositorio, base)
    if aberta and git.ramo_atual() == base:
        git.rodar("merge", "-q", "--ff-only", ponta)
    elif aberta:
        raise FalhaDoGitDoGoal("a base esta aberta em outro worktree do repositorio: o orquestrador nao a move por baixo dele",
                               {"base": base, "worktree": aberta})
    else:
        git.rodar("update-ref", "-m", f"graphow: fast-forward de {base} ate {ramo}", f"refs/heads/{base}", ponta, antigo)
    return git.rodar("rev-parse", base).strip()


def recusar_se_aberta(repositorio: Path, ramo: str, *, antes: str, depois: str) -> None:
    """Recusa mover a branch do Goal quando ela está aberta num worktree do repositório do humano, o checkout dele inclusive."""
    aberta = worktree_do_ramo(repositorio, ramo)
    if aberta:
        raise FalhaDoGitDoGoal("a branch do Goal esta aberta no checkout do humano: o rebase nao a move por baixo dele",
                               {"ramo": ramo, "worktree": aberta, "antes": antes[:12], "depois": depois[:12]})
