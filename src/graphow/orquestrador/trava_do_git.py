"""A trava do git nas sessões de agente: as regras, o ambiente e a conferência depois de cada sessão.

O agente não escreve no git; quem commita é o orquestrador. São três camadas,
porque cada uma sozinha tem furo conhecido:

1. As regras de ferramenta (`--disallowedTools`) negam o git de escrita, o
   `git -c` e o `git -C` (com eles, `git -C . commit` e
   `git -c core.hooksPath=<vazia> commit` passavam pelas outras regras).
2. O ambiente da sessão aponta `core.hooksPath` para uma pasta com o hook
   `reference-transaction`, que aborta toda atualização de ref, e o
   `pre-push`, que recusa todo push. O `git -c` na linha de comando vence o
   ambiente: por isso a primeira camada o nega, e a terceira existe. O
   ambiente também dá ao agente uma identidade de committer própria, que vai
   para o reflog de toda ref que ele mexer.
3. Antes de cada sessão o orquestrador fotografa as refs (`for-each-ref`,
   remotas inclusive), a branch de cada checkout e a configuração do
   repositório; depois, compara. A ref que mudou sem entrada do humano no
   reflog volta ao que era (a apagada é recriada, a criada é apagada); a
   configuração volta à de antes, com a que estava guardada numa cópia; o
   checkout de outra pasta que trocou de branch é só relatado, porque
   desfazer mexeria nos arquivos do humano. Qualquer achado faz a sessão
   falhar com a lista do que se viu. A branch do Goal fica de fora: o commit
   que escapou nela volta à árvore por `restaurar_head`.

O push que passou por cima das três não se desfaz; a ref remota que ele
moveu aparece na conferência, e a sessão falha dizendo isso.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import time

from graphow.orquestrador.git_do_goal import GitDoGoal

NOME_DO_COMMITTER_DO_AGENTE: str = "graphow agente"
EMAIL_DO_COMMITTER_DO_AGENTE: str = "agente@graphow.invalid"
HOOKS_DA_TRAVA: Mapping[str, str] = {
    "reference-transaction": (
        "#!/bin/sh\n"
        "# Trava do graphow orquestrar: a sessao do agente nao atualiza ref nenhuma.\n"
        'if [ "$1" = "prepared" ]; then\n'
        '  echo "graphow: o agente nao escreve no git; quem commita e o orquestrador" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    ),
    "pre-push": (
        "#!/bin/sh\n"
        "# Trava do graphow orquestrar: a sessao do agente nao publica nada.\n"
        'echo "graphow: o agente nao faz push; quem integra e o orquestrador ou o humano" >&2\n'
        "exit 1\n"
    ),
}
SUBCOMANDOS_DE_ESCRITA: tuple[str, ...] = (
    "commit", "push", "pull", "fetch", "reset", "checkout", "switch", "restore", "merge", "rebase", "stash", "branch",
    "tag", "cherry-pick", "revert", "am", "worktree", "update-ref", "symbolic-ref", "notes", "replace", "config",
    "remote", "gc", "prune", "filter-branch",
)
OPCOES_GLOBAIS_NEGADAS: tuple[str, ...] = ("-c", "-C", "--git-dir", "--work-tree", "--exec-path")
PADRAO_DO_REFLOG: re.Pattern[str] = re.compile(r"^\S+ \S+ .*?<(?P<email>[^>]*)> (?P<instante>\d+) [+-]\d{4}")


def instalar_trava(pasta: Path) -> dict[str, str]:
    """Grava os hooks da trava na pasta e devolve o ambiente que a liga numa sessão de agente."""
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in HOOKS_DA_TRAVA.items():
        hook = pasta / nome
        hook.write_text(conteudo, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
    return {
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": pasta.as_posix(),
        "GIT_COMMITTER_NAME": NOME_DO_COMMITTER_DO_AGENTE, "GIT_COMMITTER_EMAIL": EMAIL_DO_COMMITTER_DO_AGENTE,
    }


def regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]:
    """As regras `--disallowedTools` do git de escrita e das opções que trocam de repositório ou de configuração."""
    return tuple(f"{ferramenta}(git {item}:*)" for ferramenta in ferramentas for item in (*SUBCOMANDOS_DE_ESCRITA, *OPCOES_GLOBAIS_NEGADAS))


@dataclass(frozen=True)
class FotoDoGit:
    """O repositório antes de uma sessão de agente: as refs (fora a branch do Goal), os checkouts e a configuração."""

    area: Path
    comum: Path
    ramo_do_goal: str
    inicio: int
    refs: Mapping[str, str]
    checkouts: Mapping[str, str]
    configuracao: bytes


def fotografar(area: Path) -> FotoDoGit:
    """A foto do repositório da área, tirada logo antes da sessão."""
    git = GitDoGoal(area)
    comum = Path(git.rodar("rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    ramo = git.ramo_atual()
    return FotoDoGit(
        area=area, comum=comum, ramo_do_goal=ramo, inicio=int(time.time()) - 1, refs=_refs(git, ramo),
        checkouts=_checkouts(git, area), configuracao=_bytes(comum / "config"),
    )


def conferir_o_git(foto: FotoDoGit, *, guarda: Path) -> tuple[str, ...]:
    """O que mudou no git fora da branch do Goal sem ser o humano; desfaz o que dá e devolve o que achou."""
    git = GitDoGoal(foto.area)
    return (*_conferir_refs(git, foto), *_conferir_checkouts(git, foto), *_conferir_configuracao(foto, guarda))


def _refs(git: GitDoGoal, ramo_do_goal: str) -> dict[str, str]:
    """Cada ref do repositório e o objeto dela, fora a branch do Goal."""
    saida = git.rodar("for-each-ref", "--format=%(refname) %(objectname)")
    pares = (linha.rsplit(" ", 1) for linha in saida.splitlines() if " " in linha)
    return {nome: objeto for nome, objeto in pares if nome != f"refs/heads/{ramo_do_goal}"}


def _checkouts(git: GitDoGoal, area: Path) -> dict[str, str]:
    """Cada worktree do repositório, fora a área, e onde o HEAD dele está: a branch, ou o commit destacado."""
    checkouts: dict[str, str] = {}
    for bloco in git.rodar("worktree", "list", "--porcelain").split("\n\n"):
        campos = _campos_do_bloco(bloco)
        if campos.get("worktree") and Path(campos["worktree"]).resolve() != area.resolve():
            checkouts[campos["worktree"]] = campos.get("branch") or f"destacado em {campos.get('HEAD', '')[:12]}"
    return checkouts


def _campos_do_bloco(bloco: str) -> dict[str, str]:
    """As linhas `chave valor` de um bloco do `worktree list --porcelain`; a chave sem valor fica com vazio."""
    pares = (linha.partition(" ") for linha in bloco.splitlines() if linha.strip())
    return {chave: valor for chave, _, valor in pares}


def _bytes(caminho: Path) -> bytes:
    """O conteúdo do arquivo; vazio quando ele não existe."""
    return caminho.read_bytes() if caminho.is_file() else b""


def _humano_mexeu(reflog: Path, desde: int) -> bool:
    """O reflog tem entrada, desde o início da sessão, de quem não é o agente."""
    if not reflog.is_file():
        return False
    entradas = (PADRAO_DO_REFLOG.match(linha) for linha in reflog.read_text(encoding="utf-8", errors="replace").splitlines())
    return any(e is not None and int(e["instante"]) >= desde and e["email"] != EMAIL_DO_COMMITTER_DO_AGENTE for e in entradas)


def _conferir_refs(git: GitDoGoal, foto: FotoDoGit) -> list[str]:
    """As refs que mudaram sem o humano voltam ao que eram: a apagada é recriada, a criada é apagada."""
    depois = _refs(git, foto.ramo_do_goal)
    achados: list[str] = []
    for ref in sorted(set(foto.refs) | set(depois)):
        antes, agora = foto.refs.get(ref), depois.get(ref)
        if antes == agora or _humano_mexeu(foto.comum / "logs" / ref, foto.inicio):
            continue
        _voltar_ref(git, ref, antes)
        remota = "; se houve push, o que saiu da maquina nao se desfaz" if ref.startswith("refs/remotes/") else ""
        achados.append(f"{ref} {_mudanca(antes, agora)}; voltou ao que era{remota}")
    return achados


def _voltar_ref(git: GitDoGoal, ref: str, antes: str | None) -> None:
    """A ref volta ao objeto de antes; a que não existia é apagada."""
    if antes is None:
        git.rodar("update-ref", "-d", ref)
        return
    git.rodar("update-ref", ref, antes)


def _mudanca(antes: str | None, agora: str | None) -> str:
    """Como a ref mudou, em palavras."""
    if antes is None:
        return f"foi criada em {str(agora)[:12]}"
    if agora is None:
        return f"foi apagada (estava em {antes[:12]})"
    return f"saiu de {antes[:12]} para {agora[:12]}"


def _conferir_checkouts(git: GitDoGoal, foto: FotoDoGit) -> list[str]:
    """O checkout de outra pasta que trocou de branch sem o humano: relatado, não desfeito."""
    depois = _checkouts(git, foto.area)
    achados: list[str] = []
    for pasta, antes in foto.checkouts.items():
        agora = depois.get(pasta, "removido")
        if agora != antes and not _humano_mexeu(_reflog_do_head(pasta), foto.inicio):
            achados.append(f"o checkout {pasta} saiu de {antes} para {agora}; o orquestrador nao mexe nos arquivos dele")
    return achados


def _reflog_do_head(pasta: str) -> Path:
    """O reflog do HEAD de um worktree; um caminho que não existe quando o worktree sumiu."""
    if not Path(pasta).is_dir():
        return Path(pasta) / ".sem-reflog"
    feito = GitDoGoal(Path(pasta)).tentar("rev-parse", "--path-format=absolute", "--git-dir")
    return Path(feito.saida.strip()) / "logs" / "HEAD" if feito.codigo == 0 else Path(pasta) / ".sem-reflog"


def _conferir_configuracao(foto: FotoDoGit, guarda: Path) -> list[str]:
    """A configuração do repositório (remotos, hooks, identidade) volta à de antes; a que estava fica numa cópia."""
    caminho = foto.comum / "config"
    atual = _bytes(caminho)
    if atual == foto.configuracao:
        return []
    guarda.mkdir(parents=True, exist_ok=True)
    copia = guarda / f"config-mudada-{datetime.now():%Y%m%dT%H%M%S}"
    copia.write_bytes(atual)
    caminho.write_bytes(foto.configuracao)
    return [f"a configuracao do repositorio ({caminho}) mudou; voltou a de antes, e a mudada ficou em {copia}"]
