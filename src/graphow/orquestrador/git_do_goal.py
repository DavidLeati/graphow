"""O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração.

O trabalho do Goal acontece num clone local só dele, na branch do Goal: um
`git clone --local` do repositório do humano, sem remoto, só com a branch do
Goal e a base, sem tags, de modo que o agente não enxerga ref, configuração nem
hook do humano. A base vem ao clone a cada chamada, puxada do repositório do
humano, para que `base..HEAD` diga os commits do Goal. Um worktree dividiria tudo isso com o repositório dele, e o que o
agente fizesse ali (ou o que o humano fizesse durante a sessão) se misturaria.
Os objetos vêm por hardlink quando a pasta está no mesmo disco, sem
alternates que apontem o repositório.

Quem commita é o orquestrador, no clone, depois de rodar a suíte; o executor
não escreve no git. A branch do Goal no repositório do humano é só do
orquestrador: ele a cria e a avança puxando do clone (`git fetch <clone>`,
rodado no repositório do humano), sem forçar, depois de cada commit dele e no
começo de cada chamada. A integração na base continua por fast-forward no
repositório do humano. A trava que impede o agente de escrever no git e a
restauração do clone depois de cada sessão moram em orquestrador/trava_do_git.py;
aqui fica o git do próprio orquestrador, que roda sem a trava.
"""

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any

from graphow.core.exceptions import GraphowError

EXECUTAVEL_DO_GIT: str = "git"
VARIAVEIS_DE_OUTRO_REPOSITORIO: frozenset[str] = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"})
# Os trailers que todo commit do orquestrador leva: o Goal e, no da fatia, a Task.
# É por eles que a retomada reconhece o commit da fatia que caiu antes de ser
# registrada, e que a branch que já existe é conferida antes de ser adotada.
TRAILER_DO_GOAL: str = "Graphow-Goal"
TRAILER_DA_TASK: str = "Graphow-Task"
SEPARADOR_DE_COMMITS: str = "\x1e"
SEPARADOR_DO_HASH: str = "\x1f"
# A configuração do repositório do humano que o clone leva: quem assina os
# commits e como o fim de linha vira arquivo, para o clone commitar o que o
# checkout dele commitaria. O resto (remotos, hooks, includes) fica de fora.
CHAVES_COPIADAS_PARA_O_CLONE: tuple[str, ...] = ("user.name", "user.email", "core.autocrlf", "core.eol", "core.safecrlf")
REMOTO_DO_CLONE: str = "origin"
IDENTIDADE_DE_RESERVA: tuple[str, ...] = (
    "-c", "user.name=graphow orquestrar", "-c", "user.email=orquestrador@graphow.invalid",
)
LIMITE_DO_RESUMO_DO_DIFF: int = 4000


class FalhaDoGitDoGoal(GraphowError):
    """O git recusou o que o orquestrador pediu; o contexto traz o comando e a saída de erro."""


@dataclass(frozen=True)
class SaidaDoGit:
    """O código de saída e as duas saídas de um comando do git."""

    codigo: int
    saida: str
    erro: str


@dataclass(frozen=True)
class GitDoGoal:
    """Roda o git numa pasta (o repositório do humano ou a área do Goal), sem a trava do agente."""

    pasta: Path

    def tentar(self, *argumentos: str) -> SaidaDoGit:
        """O comando, sem recusar quando o git sai com erro."""
        comando = [EXECUTAVEL_DO_GIT, "-C", str(self.pasta), *argumentos]
        ambiente = {nome: valor for nome, valor in os.environ.items() if nome.upper() not in VARIAVEIS_DE_OUTRO_REPOSITORIO}
        try:
            feito = subprocess.run(
                comando, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env=ambiente
            )
        except OSError as erro:
            raise FalhaDoGitDoGoal("git indisponivel", {"erro": str(erro)}) from erro
        return SaidaDoGit(feito.returncode, feito.stdout, feito.stderr)

    def rodar(self, *argumentos: str) -> str:
        """A saída padrão; recusa com a saída de erro quando o git falha."""
        feito = self.tentar(*argumentos)
        if feito.codigo != 0:
            raise FalhaDoGitDoGoal(
                "git recusou o comando", {"comando": " ".join(argumentos), "pasta": str(self.pasta), "erro": feito.erro.strip()}
            )
        return feito.saida

    def head(self) -> str:
        """O commit em que a pasta está."""
        return self.rodar("rev-parse", "HEAD").strip()

    def ramo_atual(self) -> str:
        """A branch do HEAD; vazio com o HEAD destacado."""
        return self.rodar("branch", "--show-current").strip()

    def ramo_existe(self, ramo: str) -> bool:
        """A branch local existe."""
        return self.tentar("rev-parse", "--verify", "--quiet", f"refs/heads/{ramo}").codigo == 0

    def mudancas(self) -> tuple[str, ...]:
        """As linhas do `status --porcelain`: o que está fora de commit, ignorados de fora."""
        return tuple(linha for linha in self.rodar("status", "--porcelain").splitlines() if linha.strip())

    def e_ancestral(self, antes: str, depois: str) -> bool:
        """`antes` está na história de `depois` (ou é ele)."""
        return self.tentar("merge-base", "--is-ancestor", antes, depois).codigo == 0

    def arquivos_entre(self, antes: str, depois: str) -> tuple[str, ...]:
        """Os arquivos que mudaram de um commit ao outro."""
        return tuple(linha for linha in self.rodar("diff", "--name-only", antes, depois).splitlines() if linha.strip())

    def resumo_do_diff(self, antes: str, depois: str) -> str:
        """O `diff --stat` entre os dois commits, cortado para caber no briefing."""
        return self.rodar("diff", "--stat", antes, depois).strip()[:LIMITE_DO_RESUMO_DO_DIFF]

    def commits_desde(self, base: str) -> tuple[str, ...]:
        """Hash curto e assunto de cada commit da branch desde a base, do mais antigo ao mais novo."""
        saida = self.rodar("log", "--reverse", "--format=%h %s", f"{base}..HEAD")
        return tuple(linha for linha in saida.splitlines() if linha.strip())


def raiz_do_repositorio(pasta: Path) -> Path:
    """A raiz do repositório git que contém a pasta."""
    return Path(GitDoGoal(pasta).rodar("rev-parse", "--show-toplevel").strip())


@dataclass(frozen=True)
class AreaDoGoal:
    """Onde o trabalho do Goal acontece: o repositório do humano, o clone do Goal, a branch e a base."""

    repositorio: Path
    pasta: Path
    ramo: str
    base: str


def preparar_area(area: AreaDoGoal) -> None:
    """O clone do Goal na branch dele, e a branch do Goal no repositório do humano no commit do clone.

    O clone que já existe é reaproveitado; a área de uma versão anterior, que
    era um worktree do repositório do humano, sai e dá lugar ao clone.
    """
    if (area.pasta / ".git").is_file():
        _tirar_worktree_antigo(area)
    if (area.pasta / ".git").is_dir():
        if GitDoGoal(area.pasta).ramo_atual() != area.ramo:
            raise FalhaDoGitDoGoal("a area do Goal esta em outra branch", {"area": str(area.pasta), "ramo": area.ramo})
    else:
        _clonar(area)
    GitDoGoal(area.pasta).rodar(
        "fetch", "-q", "--no-tags", str(area.repositorio), f"+refs/heads/{area.base}:refs/heads/{area.base}"
    )
    limpar_rastros_do_clone(area.pasta)
    sincronizar_ramo(area)


def _clonar(area: AreaDoGoal) -> None:
    """O clone local da branch do Goal (ou da base, quando ela ainda não existe), sem remoto, tag, reflog nem hook."""
    repositorio = GitDoGoal(area.repositorio)
    if area.pasta.exists() and any(area.pasta.iterdir()):
        raise FalhaDoGitDoGoal("a pasta da area ja existe e nao e um clone do Goal", {"area": str(area.pasta)})
    inicio = area.ramo if repositorio.ramo_existe(area.ramo) else area.base
    area.pasta.parent.mkdir(parents=True, exist_ok=True)
    repositorio.rodar(
        "clone", "-q", "--local", "--no-checkout", "--single-branch", "--no-tags", "--branch", inicio,
        str(area.repositorio), str(area.pasta),
    )
    clone = GitDoGoal(area.pasta)
    if inicio != area.ramo:
        clone.rodar("branch", area.ramo, inicio)
        clone.rodar("symbolic-ref", "HEAD", f"refs/heads/{area.ramo}")
    clone.rodar("remote", "remove", REMOTO_DO_CLONE)
    for chave in CHAVES_COPIADAS_PARA_O_CLONE:
        valor = repositorio.tentar("config", "--get", chave)
        if valor.codigo == 0 and valor.saida.strip():
            clone.rodar("config", chave, valor.saida.strip())
    clone.rodar("reset", "-q", "--hard", "HEAD")


def limpar_rastros_do_clone(pasta: Path) -> None:
    """Tira do clone o reflog (que diz de onde ele veio) e os hooks: nada ali roda nos commits do orquestrador."""
    git_do_clone = pasta / ".git"
    _apagar_arvore(git_do_clone / "logs")
    _apagar_arvore(git_do_clone / "hooks")
    (git_do_clone / "hooks").mkdir(exist_ok=True)


def _tirar_worktree_antigo(area: AreaDoGoal) -> None:
    """A área que era worktree do repositório do humano sai; a branch do Goal fica nele, e o clone parte dela."""
    if GitDoGoal(area.repositorio).tentar("worktree", "remove", "--force", str(area.pasta)).codigo != 0:
        _apagar_arvore(area.pasta)
    GitDoGoal(area.repositorio).tentar("worktree", "prune")


def sincronizar_ramo(area: AreaDoGoal) -> None:
    """A branch do Goal no repositório do humano vai ao commit do clone, puxada dele, só por fast-forward.

    A branch que andou no repositório do humano fora do orquestrador não é
    sobrescrita: a chamada para dizendo isso.
    """
    repositorio = GitDoGoal(area.repositorio)
    destino = f"refs/heads/{area.ramo}"
    head = GitDoGoal(area.pasta).rodar("rev-parse", destino).strip()
    if repositorio.ramo_existe(area.ramo):
        atual = repositorio.rodar("rev-parse", destino).strip()
        if atual == head:
            return
        if not GitDoGoal(area.pasta).e_ancestral(atual, head):
            raise FalhaDoGitDoGoal(
                "a branch do Goal andou no repositorio fora do orquestrador: ela nao e sobrescrita",
                {"ramo": area.ramo, "no_repositorio": atual[:12], "no_clone": head[:12]},
            )
    repositorio.rodar("fetch", "-q", "--no-tags", str(area.pasta), f"{destino}:{destino}")


def mensagem_do_orquestrador(assunto: str, corpo: str, *, id_goal: str, id_task: str = "") -> str:
    """A mensagem do commit com os trailers do Goal e, na fatia, da Task."""
    trailers = [f"{TRAILER_DO_GOAL}: {id_goal}", *([f"{TRAILER_DA_TASK}: {id_task}"] if id_task else [])]
    partes = [assunto.strip(), corpo.strip(), "\n".join(trailers)]
    return "\n\n".join(parte for parte in partes if parte)


def commitar(area: Path, mensagem: str, *, vazio_permitido: bool = False) -> str:
    """Tudo o que mudou na área num commit do orquestrador; devolve o hash.

    O commit vazio vale para a fatia que fechou sem mudar arquivo: cada fatia
    tem o seu commit, com os trailers que a retomada lê.
    """
    git = GitDoGoal(area)
    git.rodar("add", "-A")
    identidade = () if git.tentar("config", "user.email").saida.strip() else IDENTIDADE_DE_RESERVA
    git.rodar(*identidade, "commit", "-q", *(["--allow-empty"] if vazio_permitido else []), "-m", mensagem)
    return git.head()


@dataclass(frozen=True)
class CommitDoGit:
    """Um commit da branch: o hash e a mensagem inteira."""

    hash: str
    mensagem: str

    def tem_trailer(self, chave: str, valor: str) -> bool:
        """A mensagem traz a linha `chave: valor`."""
        return f"{chave}: {valor}" in (linha.strip() for linha in self.mensagem.splitlines())


def commits_entre(area: Path, antes: str, depois: str = "HEAD") -> tuple[CommitDoGit, ...]:
    """Os commits de `antes..depois`, do mais novo ao mais antigo, com a mensagem inteira."""
    saida = GitDoGoal(area).rodar("log", f"--format=%H{SEPARADOR_DO_HASH}%B{SEPARADOR_DE_COMMITS}", f"{antes}..{depois}")
    commits = []
    for bloco in saida.split(SEPARADOR_DE_COMMITS):
        if SEPARADOR_DO_HASH in bloco:
            hash_do_commit, mensagem = bloco.strip().split(SEPARADOR_DO_HASH, 1)
            commits.append(CommitDoGit(hash_do_commit.strip(), mensagem))
    return tuple(commits)


def commit_da_fatia(area: Path, id_task: str, base: str) -> CommitDoGit | None:
    """O commit mais novo da branch, desde a base, que o orquestrador fez para a fatia; None sem nenhum."""
    return next((commit for commit in commits_entre(area, base) if commit.tem_trailer(TRAILER_DA_TASK, id_task)), None)


def arquivos_do_commit(area: Path, hash_do_commit: str) -> tuple[str, ...]:
    """Os arquivos que o commit mudou."""
    saida = GitDoGoal(area).rodar("show", "--name-only", "--format=", hash_do_commit)
    return tuple(linha for linha in saida.splitlines() if linha.strip())


def ultimo_commit_do_arquivo(area: Path, caminho: str) -> str:
    """O commit mais novo que tocou o arquivo; o HEAD quando nenhum tocou."""
    git = GitDoGoal(area)
    return git.rodar("log", "-1", "--format=%H", "--", caminho).strip() or git.head()


def descartar_mudancas(area: Path, arquivo_patch: Path) -> bool:
    """Guarda o que está fora de commit num .patch e volta a área ao HEAD; diz se havia o que guardar.

    Os arquivos ignorados (dependências instaladas, caches) ficam: não são do agente.
    """
    git = GitDoGoal(area)
    if not git.mudancas():
        return False
    git.rodar("add", "-A")
    arquivo_patch.parent.mkdir(parents=True, exist_ok=True)
    arquivo_patch.write_text(git.rodar("diff", "--cached", "--binary", "HEAD"), encoding="utf-8")
    git.rodar("reset", "-q", "--hard", "HEAD")
    git.rodar("clean", "-q", "-fd")
    return True


def restaurar_head(area: Path, ramo: str, esperado: str) -> str:
    """Desfaz o que o agente fez no git: volta à branch e, com `reset --soft`, ao commit esperado.

    As mudanças do commit desfeito voltam à árvore, para o orquestrador
    commitá-las ele mesmo. Devolve o que foi desfeito; vazio quando nada.
    """
    git = GitDoGoal(area)
    feito: list[str] = []
    if git.ramo_atual() != ramo:
        git.rodar("symbolic-ref", "HEAD", f"refs/heads/{ramo}")
        feito.append(f"o agente trocou de branch; a area voltou para {ramo}")
    atual = git.head()
    if atual != esperado:
        git.rodar("reset", "-q", "--soft", esperado)
        feito.append(f"o agente commitou ({atual[:12]}); o commit foi desfeito com reset --soft")
    return "; ".join(feito)


def integrar_por_fast_forward(repositorio: Path, ramo: str, base: str) -> str:
    """Avança a base até a branch do Goal, só por fast-forward; devolve o commit integrado.

    Com a base no checkout do humano, é o `merge --ff-only` ali (o git recusa
    se isso apagar mudança dele). Fora dele, `branch -f`, que o git recusa se
    a base estiver aberta em outro worktree.
    """
    git = GitDoGoal(repositorio)
    if not git.e_ancestral(base, ramo):
        raise FalhaDoGitDoGoal(
            "a base andou desde que a branch do Goal saiu dela: nao ha fast-forward", {"base": base, "ramo": ramo}
        )
    if git.ramo_atual() == base:
        git.rodar("merge", "-q", "--ff-only", ramo)
    else:
        git.rodar("branch", "-f", base, ramo)
    return git.rodar("rev-parse", base).strip()


def remover_area(area: Path) -> bool:
    """Apaga o clone do Goal depois da integração; a branch fica no repositório do humano. Diz se conseguiu."""
    try:
        _apagar_arvore(area)
    except OSError:
        return False
    return not area.exists()


def _apagar_arvore(pasta: Path) -> None:
    """A pasta inteira, inclusive os objetos que o git deixa somente leitura (no Windows, o rmtree recusa)."""
    if not pasta.exists():
        return
    chave = "onexc" if sys.version_info >= (3, 12) else "onerror"
    shutil.rmtree(pasta, **{chave: _liberar_e_repetir})


def _liberar_e_repetir(funcao: Callable[[str], Any], caminho: str, _erro: object) -> None:
    """Tira o somente leitura do arquivo que o rmtree não apagou e tenta de novo."""
    os.chmod(caminho, stat.S_IWRITE)
    funcao(caminho)

