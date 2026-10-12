"""O git do Goal: a área de trabalho numa branch própria, o commit de cada fatia e a integração.

O trabalho do Goal acontece num worktree só dele, na branch do Goal, criada da
base: o checkout do humano não é tocado até a integração. Quem commita é o
orquestrador, depois de rodar a suíte; o executor não escreve no git.

A trava do executor tem duas camadas, porque uma sonda real mostrou que a
regra de ferramenta `Bash(git commit:*)` recusa `git commit` e deixa passar
`git -C . commit`. A primeira são as regras de ferramenta da sessão. A segunda
vai no ambiente dela: `GIT_CONFIG_*` aponta `core.hooksPath` para uma pasta
com um hook `reference-transaction` que aborta toda atualização de ref
(commit, inclusive com `--no-verify`, reset, branch, checkout -b, merge,
rebase, stash). O orquestrador roda o próprio git sem essas variáveis. Depois
de cada sessão ele ainda confere HEAD e branch, e desfaz com `reset --soft` o
commit que tenha escapado.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from graphow.core.exceptions import GraphowError

EXECUTAVEL_DO_GIT: str = "git"
VARIAVEIS_DE_OUTRO_REPOSITORIO: frozenset[str] = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"})
NOME_DO_HOOK_DA_TRAVA: str = "reference-transaction"
HOOK_DA_TRAVA: str = (
    "#!/bin/sh\n"
    "# Trava do graphow orquestrar: a sessao do agente nao atualiza ref nenhuma.\n"
    'if [ "$1" = "prepared" ]; then\n'
    '  echo "graphow: o agente nao escreve no git; quem commita e o orquestrador" >&2\n'
    "  exit 1\n"
    "fi\n"
    "exit 0\n"
)
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
    """Onde o trabalho do Goal acontece: o repositório do humano, o worktree, a branch e a base."""

    repositorio: Path
    pasta: Path
    ramo: str
    base: str


def preparar_area(area: AreaDoGoal) -> None:
    """O worktree do Goal na branch dele: reaproveitado se já existe, criado da base se a branch é nova."""
    git = GitDoGoal(area.repositorio)
    if (area.pasta / ".git").exists():
        if GitDoGoal(area.pasta).ramo_atual() != area.ramo:
            raise FalhaDoGitDoGoal("a area do Goal esta em outra branch", {"area": str(area.pasta), "ramo": area.ramo})
        return
    area.pasta.parent.mkdir(parents=True, exist_ok=True)
    git.rodar("worktree", "prune")
    if git.ramo_existe(area.ramo):
        git.rodar("worktree", "add", str(area.pasta), area.ramo)
        return
    git.rodar("worktree", "add", "-b", area.ramo, str(area.pasta), area.base)


def commitar(area: Path, mensagem: str) -> str:
    """Tudo o que mudou na área num commit do orquestrador; devolve o hash."""
    git = GitDoGoal(area)
    git.rodar("add", "-A")
    identidade = () if git.tentar("config", "user.email").saida.strip() else IDENTIDADE_DE_RESERVA
    git.rodar(*identidade, "commit", "-q", "-m", mensagem)
    return git.head()


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
        git.rodar("checkout", "-q", ramo)
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


def remover_area(repositorio: Path, area: Path) -> bool:
    """Tira o worktree do Goal depois da integração; a branch fica. Diz se conseguiu."""
    return GitDoGoal(repositorio).tentar("worktree", "remove", str(area)).codigo == 0


def instalar_trava(pasta: Path) -> dict[str, str]:
    """Grava o hook da trava na pasta e devolve o ambiente que a liga numa sessão de agente."""
    pasta.mkdir(parents=True, exist_ok=True)
    hook = pasta / NOME_DO_HOOK_DA_TRAVA
    hook.write_text(HOOK_DA_TRAVA, encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": pasta.as_posix()}


def regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]:
    """As regras `--disallowedTools` de git de escrita, para cada ferramenta de shell dada."""
    subcomandos = ("commit", "push", "reset", "checkout", "switch", "restore", "merge", "rebase", "stash",
                   "branch", "tag", "cherry-pick", "revert", "am", "worktree", "update-ref")
    return tuple(f"{ferramenta}(git {sub}:*)" for ferramenta in ferramentas for sub in subcomandos)
