"""O rebase da branch do Goal sobre a base que andou, feito pelo orquestrador no clone do Goal.

Na integração, a base pode ter andado desde que a branch do Goal saiu dela
(outro Goal integrou, o humano commitou), e o fast-forward deixa de existir.
A fase 1 parava em falha. Agora o orquestrador refaz a branch sobre a base
nova, no clone, com o HEAD destacado: a branch do Goal só anda depois da
suíte e do registro no livro-razão. Cada commit antigo vira um novo, na mesma
ordem e com a mesma mensagem (os trailers inclusive), mesmo o vazio e o que a
base já trazia (`--keep-empty --empty=keep --reapply-cherry-picks`): é o par
que leva o Artifact e a fatia ao commit novo. O conflito aborta o rebase, e o
clone volta à branch como estava.

As refs andam depois do registro, cada uma só se ainda estiver no commit de
antes (`update-ref <novo> <antigo>`): a do clone e, com os objetos puxados do
clone, a do repositório do humano. O processo que cai no meio deixa o rebase
pela metade, ou o registro sem as refs: a chamada seguinte, antes de preparar
a área, desfaz o primeiro (`recuperar_o_clone`) e termina o segundo
(`mover_as_refs`).
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.orquestrador.git_do_goal import IDENTIDADE_DE_RESERVA, AreaDoGoal, FalhaDoGitDoGoal, GitDoGoal, commits_entre

OPCOES_DO_REBASE: tuple[str, ...] = (
    "--no-autosquash", "--keep-empty", "--empty=keep", "--reapply-cherry-picks", "--no-update-refs",
)
SEM_ASPAS: tuple[str, ...] = ("-c", "core.quotepath=false")
PASTAS_DO_REBASE: tuple[str, ...] = ("rebase-merge", "rebase-apply")
LIMITE_DO_ERRO: int = 2000


@dataclass(frozen=True)
class RebaseNoClone:
    """O rebase que deu certo: as duas bases, as duas pontas, o par de cada commit e os arquivos que ele mudou na ponta."""

    base_antes: str
    base_depois: str
    antes: str
    depois: str
    pares: tuple[tuple[str, str], ...]
    arquivos: tuple[str, ...]


@dataclass(frozen=True)
class ConflitoNoRebase:
    """O rebase que parou em conflito, já abortado: as bases, a ponta que ficou, os arquivos em conflito e o que o git disse."""

    base_antes: str
    base_depois: str
    antes: str
    arquivos: tuple[str, ...]
    erro: str = ""


def trazer_a_base(area: AreaDoGoal) -> str:
    """A base do repositório do humano, como ela está agora, no clone; devolve o commit dela."""
    clone = GitDoGoal(area.pasta)
    clone.rodar("fetch", "-q", "--no-tags", str(area.repositorio), f"+refs/heads/{area.base}:refs/heads/{area.base}")
    return clone.rodar("rev-parse", f"refs/heads/{area.base}").strip()


def rebasear(area: Path, ramo: str, base: str) -> RebaseNoClone | ConflitoNoRebase:
    """A branch do Goal refeita sobre a base, com o HEAD destacado; no conflito, o rebase sai e o clone volta à branch."""
    git = GitDoGoal(area)
    antes = git.head()
    base_depois = git.rodar("rev-parse", base).strip()
    base_antes = git.rodar("merge-base", antes, base_depois).strip()
    identidade = () if git.tentar("config", "user.email").saida.strip() else IDENTIDADE_DE_RESERVA
    git.rodar("checkout", "-q", "--detach")
    feito = git.tentar(*identidade, "rebase", "-q", *OPCOES_DO_REBASE, base_depois)
    if feito.codigo != 0:
        arquivos = _em_conflito(git)
        git.tentar("rebase", "--abort")
        desfazer_o_rebase(area, ramo)
        return ConflitoNoRebase(base_antes, base_depois, antes, arquivos, (feito.erro or feito.saida).strip()[-LIMITE_DO_ERRO:])
    depois = git.head()
    return RebaseNoClone(base_antes, base_depois, antes, depois, _pares(area, base_depois, antes=antes, depois=depois), arquivos_entre(git, antes, depois))


def arquivos_entre(git: GitDoGoal, antes: str, depois: str) -> tuple[str, ...]:
    """Os arquivos que mudaram de um commit ao outro, sem aspas nem escape no nome."""
    saida = git.rodar(*SEM_ASPAS, "diff", "--name-only", "-z", antes, depois)
    return tuple(caminho for caminho in saida.split("\x00") if caminho)


def _em_conflito(git: GitDoGoal) -> tuple[str, ...]:
    """Os arquivos que o rebase deixou em conflito, no commit em que parou."""
    saida = git.tentar(*SEM_ASPAS, "diff", "--name-only", "--diff-filter=U", "-z").saida
    return tuple(dict.fromkeys(caminho for caminho in saida.split("\x00") if caminho))


def _pares(area: Path, base: str, *, antes: str, depois: str) -> tuple[tuple[str, str], ...]:
    """O commit novo de cada antigo, na ordem; recusa se o rebase não deu um para um com a mesma mensagem."""
    antigos = tuple(reversed(commits_entre(area, base, antes)))
    novos = tuple(reversed(commits_entre(area, base, depois)))
    if [c.mensagem for c in antigos] != [c.mensagem for c in novos]:
        raise FalhaDoGitDoGoal("o rebase nao refez cada commit da branch do Goal com a mesma mensagem",
                               {"antes": antes[:12], "depois": depois[:12], "antigos": len(antigos), "novos": len(novos)})
    return tuple((antigo.hash, novo.hash) for antigo, novo in zip(antigos, novos))


def desfazer_o_rebase(area: Path, ramo: str) -> None:
    """O clone de volta à branch do Goal, que o rebase não moveu, sem o que a suíte deixou."""
    git = GitDoGoal(area)
    git.rodar("checkout", "-q", "-f", ramo)
    git.rodar("clean", "-q", "-fd")


def recuperar_o_clone(area: Path, ramo: str) -> str:
    """O rebase que o processo deixou pela metade sai, e o clone com o HEAD destacado volta à branch; diz o que fez."""
    git = GitDoGoal(area)
    feito = []
    if any((area / ".git" / pasta).exists() for pasta in PASTAS_DO_REBASE):
        git.tentar("rebase", "--abort")
        feito.append("rebase pela metade abortado")
    if not git.ramo_atual() and git.ramo_existe(ramo):
        desfazer_o_rebase(area, ramo)
        feito.append(f"clone de volta a {ramo}")
    return "; ".join(feito)


def mover_as_refs(area: AreaDoGoal, antes: str, depois: str) -> None:
    """A branch do Goal vai de `antes` a `depois` no clone e no repositório do humano, cada uma só se ainda está em `antes`.

    O clone fica na branch, com a árvore do commit novo (o `reset --hard` só
    quando a ref ou o HEAD andaram aqui: a chamada que só confere não apaga
    nada da área). No repositório do humano, a branch aberta no checkout dele
    não é movida por baixo dele: a chamada para dizendo isso.
    """
    ref = f"refs/heads/{area.ramo}"
    clone = GitDoGoal(area.pasta)
    moveu = _ref(clone, ref) == antes
    if moveu:
        clone.rodar("update-ref", ref, depois, antes)
    if not clone.ramo_atual():
        clone.rodar("symbolic-ref", "HEAD", ref)
        moveu = True
    if moveu:
        clone.rodar("reset", "-q", "--hard", "HEAD")
    humano = GitDoGoal(area.repositorio)
    if _ref(humano, ref) != antes or _ref(clone, ref) != depois:
        return
    if humano.ramo_atual() == area.ramo:
        raise FalhaDoGitDoGoal("a branch do Goal esta aberta no checkout do humano: o rebase nao a move por baixo dele",
                               {"ramo": area.ramo, "antes": antes[:12], "depois": depois[:12]})
    humano.rodar("fetch", "-q", "--no-tags", str(area.pasta), ref)
    humano.rodar("update-ref", ref, depois, antes)


def arvore_mesclada(area: Path, ponta: str, base: str) -> tuple[str, tuple[str, ...]]:
    """A árvore da ponta do Goal com a base mesclada (`merge-tree`, os marcadores no conflito) e os arquivos em conflito."""
    feito = GitDoGoal(area).tentar(*SEM_ASPAS, "merge-tree", "--write-tree", "--name-only", "-z", ponta, base)
    partes = feito.saida.split("\x00")
    if feito.codigo not in (0, 1) or not partes[0].strip():
        raise FalhaDoGitDoGoal("o git nao mesclou a ponta do Goal com a base", {"ponta": ponta[:12], "base": base[:12],
                                                                              "erro": feito.erro.strip()})
    arquivos = tuple(dict.fromkeys(_ate_o_vazio(partes[1:]))) if feito.codigo == 1 else ()
    return partes[0].strip(), arquivos


def _ate_o_vazio(partes: list[str]) -> list[str]:
    """Os itens até o primeiro vazio: na saída `-z` do `merge-tree`, os arquivos em conflito antes das mensagens."""
    return partes[:partes.index("")] if "" in partes else partes


def commit_sobre(area: Path, mensagem: str, *, pai: str) -> str:
    """O commit da área inteira (o que está fora de commit inclusive) com o pai dado, sem mover ref nenhuma; devolve o hash."""
    git = GitDoGoal(area)
    git.rodar("add", "-A")
    arvore = git.rodar("write-tree").strip()
    identidade = () if git.tentar("config", "user.email").saida.strip() else IDENTIDADE_DE_RESERVA
    return git.rodar(*identidade, "commit-tree", arvore, "-p", pai, "-m", mensagem).strip()


def _ref(git: GitDoGoal, ref: str) -> str:
    """O commit da ref; vazio quando ela não existe."""
    return git.tentar("rev-parse", "--verify", "--quiet", ref).saida.strip()
