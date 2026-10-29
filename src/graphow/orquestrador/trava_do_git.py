"""A trava do git nas sessões de agente: as regras, o ambiente e a restauração do clone depois de cada sessão.

O agente trabalha no clone do Goal (orquestrador/git_do_goal.py), que não
divide ref, configuração nem hook com o repositório do humano: o que ele fizer
no git fica no clone, e o repositório do humano só muda pelo orquestrador.
Dentro do clone, o agente não escreve no git; quem commita é o orquestrador.
São quatro camadas, em profundidade:

0. O hook PreToolUse (orquestrador/hook_do_git.py), que a sessão recebe por
   `--settings`, lê cada comando Bash inteiro e recusa o git de escrita
   disfarçado, que as regras da camada 1 deixam passar: `FOO=1 git commit`,
   `cd x && git add .`, `env git push`, `/usr/bin/git`, `(git commit)`,
   `bash -c "git ..."`.
1. As regras de ferramenta (`--disallowedTools`) negam o git de escrita, o
   `git -c` e o `git -C` (com eles, `git -C . commit` e
   `git -c core.hooksPath=<vazia> commit` passavam pelas outras regras).
   Casam por prefixo do comando: o disfarce escapa delas.
2. O ambiente da sessão aponta `core.hooksPath` para uma pasta com o hook
   `reference-transaction`, que aborta toda atualização de ref, e o
   `pre-push`, que recusa todo push. O `git -c` na linha de comando vence o
   ambiente: por isso a primeira camada o nega, e a terceira existe.
3. O clone é do orquestrador. Antes de cada sessão ele guarda as refs e a
   configuração do clone; depois, deixa o clone como estava: a branch do Goal
   volta ao commit de antes (o commit que escapou volta à árvore, com
   `reset --soft`), a ref que o agente apagou ou moveu volta, a que ele criou
   (branch, tag, stash, remota) some, a configuração volta à de antes e os
   hooks somem. Não há quem adivinhar: no clone, só o agente mexe durante a
   sessão. O que foi desfeito vira observação, e a sessão não é reprovada.

Nada fora do clone é conferido nem desfeito: o que o humano fizer no
repositório dele durante a sessão fica como ele deixou.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

from graphow.orquestrador.git_do_goal import GitDoGoal, limpar_rastros_do_clone, restaurar_head

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
    "remote", "gc", "prune", "filter-branch", "update-index", "sparse-checkout", "read-tree",
)
OPCOES_GLOBAIS_NEGADAS: tuple[str, ...] = ("-c", "-C", "--git-dir", "--work-tree", "--exec-path")
MODULO_DO_HOOK: str = "graphow.orquestrador.hook_do_git"
ARQUIVO_DO_HOOK: str = "settings-da-trava.json"
TEMPO_LIMITE_DO_HOOK_S: int = 30
# A pasta `src` (ou site-packages) de onde este graphow foi importado: o hook roda este mesmo código.
RAIZ_DO_PACOTE: Path = Path(__file__).resolve().parents[2]


def instalar_trava(pasta: Path) -> dict[str, str]:
    """Grava os hooks da trava na pasta e devolve o ambiente que a liga numa sessão de agente."""
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in HOOKS_DA_TRAVA.items():
        hook = pasta / nome
        hook.write_text(conteudo, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": pasta.as_posix()}


def configuracao_do_hook(python: str = sys.executable, raiz: Path = RAIZ_DO_PACOTE) -> dict[str, Any]:
    """O settings do Claude Code que liga o hook PreToolUse da trava a cada comando Bash.

    Forma exec (`command` e `args`, sem shell no meio para citar caminho).
    `-I` tira do caminho de importação a pasta corrente (o clone, que o agente
    escreve), o PYTHONPATH e o site do usuário; a raiz do pacote entra na
    frente, e responde o módulo do graphow que monta a sessão, não o que o
    venv instalou. `onFailure: block` recusa o comando quando o hook nem
    sobe ou estoura o tempo, em vez de deixá-lo passar.
    """
    codigo = (f"import sys; sys.path.insert(0, {str(raiz)!r}); "
              f"from {MODULO_DO_HOOK} import responder; raise SystemExit(responder())")
    hook = {"type": "command", "command": python, "args": ["-I", "-c", codigo],
            "timeout": TEMPO_LIMITE_DO_HOOK_S, "onFailure": "block"}
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [hook]}]}}


def gravar_hook_da_trava(pasta: Path) -> Path:
    """Grava o settings do hook na pasta de estado do Goal e devolve o caminho, que vai no `--settings` da sessão."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / ARQUIVO_DO_HOOK
    caminho.write_text(json.dumps(configuracao_do_hook(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return caminho


def regras_que_negam_git(ferramentas: Sequence[str]) -> tuple[str, ...]:
    """As regras `--disallowedTools` do git de escrita e das opções que trocam de repositório ou de configuração."""
    return tuple(f"{ferramenta}(git {item}:*)" for ferramenta in ferramentas for item in (*SUBCOMANDOS_DE_ESCRITA, *OPCOES_GLOBAIS_NEGADAS))


@dataclass(frozen=True)
class FotoDoClone:
    """O clone antes de uma sessão de agente: a branch do HEAD, as refs e a configuração."""

    area: Path
    ramo: str
    refs: Mapping[str, str]
    configuracao: bytes

    @property
    def ref_do_ramo(self) -> str:
        """A ref da branch do Goal."""
        return f"refs/heads/{self.ramo}"


def fotografar_clone(area: Path) -> FotoDoClone:
    """A foto do clone, tirada logo antes da sessão."""
    git = GitDoGoal(area)
    return FotoDoClone(area=area, ramo=git.ramo_atual(), refs=_refs(git), configuracao=_bytes(area / ".git" / "config"))


def restaurar_o_clone(foto: FotoDoClone) -> str:
    """Deixa o clone como a foto: a branch do Goal, as outras refs, a configuração e os hooks; diz o que desfez."""
    git = GitDoGoal(foto.area)
    esperado = foto.refs[foto.ref_do_ramo]
    feitos = [_recriar_ramo(git, foto.ref_do_ramo, esperado), restaurar_head(foto.area, foto.ramo, esperado)]
    feitos += _voltar_as_outras_refs(git, foto)
    feitos.append(_voltar_a_configuracao(foto))
    limpar_rastros_do_clone(foto.area)
    return "; ".join(feito for feito in feitos if feito)


def _refs(git: GitDoGoal) -> dict[str, str]:
    """Cada ref do clone e o objeto dela."""
    saida = git.rodar("for-each-ref", "--format=%(refname) %(objectname)")
    pares = (linha.rsplit(" ", 1) for linha in saida.splitlines() if " " in linha)
    return dict(pares)


def _bytes(caminho: Path) -> bytes:
    """O conteúdo do arquivo; vazio quando ele não existe."""
    return caminho.read_bytes() if caminho.is_file() else b""


def _recriar_ramo(git: GitDoGoal, ref: str, esperado: str) -> str:
    """A branch do Goal que o agente apagou volta no commit de antes, para o HEAD voltar a ela."""
    if git.tentar("rev-parse", "--verify", "--quiet", ref).codigo == 0:
        return ""
    git.rodar("update-ref", ref, esperado)
    return f"o agente apagou {ref}; ela voltou a {esperado[:12]}"


def _voltar_as_outras_refs(git: GitDoGoal, foto: FotoDoClone) -> list[str]:
    """Fora a branch do Goal, cada ref volta ao que era: a que o agente criou some, a que ele moveu ou apagou volta."""
    depois = _refs(git)
    feitos: list[str] = []
    for ref in sorted((set(foto.refs) | set(depois)) - {foto.ref_do_ramo}):
        antes, agora = foto.refs.get(ref), depois.get(ref)
        if antes != agora:
            feitos.append(_voltar_ref(git, ref, antes))
    return feitos


def _voltar_ref(git: GitDoGoal, ref: str, antes: str | None) -> str:
    """A ref volta ao objeto de antes; a que não existia é apagada."""
    if antes is None:
        git.rodar("update-ref", "--no-deref", "-d", ref)
        return f"o agente criou {ref}; ela foi apagada"
    git.rodar("update-ref", "--no-deref", ref, antes)
    return f"o agente mexeu em {ref}; ela voltou a {antes[:12]}"


def _voltar_a_configuracao(foto: FotoDoClone) -> str:
    """A configuração do clone (remotos, hooks, identidade) volta à de antes da sessão."""
    caminho = foto.area / ".git" / "config"
    if _bytes(caminho) == foto.configuracao:
        return ""
    caminho.write_bytes(foto.configuracao)
    return "o agente mudou a configuracao do clone; ela voltou a de antes"
