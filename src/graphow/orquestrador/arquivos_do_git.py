"""Os arquivos que mudam o que o git do humano roda, lidos em bytes, sem processo nenhum.

A conferência de depois da sessão (orquestrador/conferencia_do_humano.py)
começa por eles, antes de qualquer git no repositório do humano. O
`core.fsmonitor` que a sessão planta no `.git/config` rodaria no `git
status` da própria foto, fora do job da sessão, e o script devolveria o
config antes de a foto o ler. Se algum desses arquivos mudou, o laço para
sem rodar mais git ali.

São eles:
- a configuração local (`.git/config`) e a da worktree (`config.worktree`);
- a global (`GIT_CONFIG_GLOBAL`, ou `~/.gitconfig` e a do XDG);
- cada arquivo em que a foto de antes achou alguma chave, e cada caminho de
  `include.path` e `includeIf.<condição>.path`, inclusive o que ainda não
  existe, relativo ao arquivo que o inclui;
- os hooks: a pasta `.git/hooks` e a do `core.hooksPath` que o humano já usa
  (relativa à raiz da árvore), lidas inteiras;
- o `.git/info/exclude`, que esconderia da foto seguinte o não rastreado que
  a sessão seguinte apaga;
- o reflog do stash, onde ficam as entradas antigas (o `stash drop
  stash@{1}` não muda `refs/stash`).
A lista sai da foto de antes, pelo `git config --list --show-origin -z`, que
só lê. Mudança do humano num desses arquivos durante a sessão também para o
laço: é o lado seguro.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from graphow.orquestrador.git_da_foto import CHAVE_DOS_HOOKS, git_da_foto

AUSENTE: str = "ausente"
PASTA: str = "pasta"
LINK: str = "link "
ORIGEM_DE_ARQUIVO: str = "file"
CHAVE_DO_INCLUDE: str = "include.path"
PREFIXO_DO_INCLUDE_CONDICIONAL: str = "includeif."
SUFIXO_DO_INCLUDE_CONDICIONAL: str = ".path"


@dataclass(frozen=True)
class ArquivosDoGit:
    """O que a foto vigia no repositório do humano: os arquivos (existam ou não) e as pastas de hooks, lidas inteiras.

    `pasta_do_git` é a do worktree (a do índice e do `config.worktree`); `comum`, a de objetos, refs e hooks; as duas
    são a mesma fora de worktree ligado.
    """

    repositorio: Path
    pasta_do_git: Path
    comum: Path
    arquivos: tuple[Path, ...] = ()
    pastas: tuple[Path, ...] = ()


def arquivos_do_git(repositorio: Path, pasta_do_git: Path, comum: Path) -> ArquivosDoGit:
    """A lista da foto de antes: os arquivos fixos, os da configuração (origens e includes) e as pastas dos hooks."""
    configuracao = list(_chaves_de_arquivo(repositorio, git_da_foto(repositorio, ("config", "--list", "--show-origin", "-z")) or ""))
    origens = (arquivo for arquivo, _, _ in configuracao)
    includes = (_resolvido(valor, arquivo.parent) for arquivo, chave, valor in configuracao if _e_include(chave))
    hooks = [_resolvido(valor, repositorio) for _, chave, valor in configuracao if chave == CHAVE_DOS_HOOKS.lower() and valor]
    fixos = (comum / "config", pasta_do_git / "config.worktree", comum / "info" / "exclude", comum / "logs" / "refs" / "stash")
    return ArquivosDoGit(repositorio, pasta_do_git, comum, _sem_repetir((*fixos, *_globais(), *origens, *includes)),
                         _sem_repetir((comum / "hooks", *hooks[-1:])))


def ler_os_arquivos_do_git(vigia: ArquivosDoGit) -> dict[str, str]:
    """O sha256 de cada arquivo vigiado (`ausente` quando não existe) e de cada arquivo das pastas, pelo nome que a parada
    mostra; só leitura de arquivo, sem processo."""
    das_pastas = (arquivo for pasta in vigia.pastas if pasta.is_dir() for arquivo in sorted(pasta.rglob("*")) if arquivo.is_file())
    return {_nome(arquivo, vigia): conteudo_do_arquivo(arquivo) for arquivo in (*vigia.arquivos, *das_pastas)}


def conteudo_do_arquivo(caminho: Path) -> str:
    """O sha256 do conteúdo (do alvo, no link); `ausente` quando o arquivo não existe, `pasta` no submódulo."""
    if caminho.is_symlink():
        return LINK + hashlib.sha256(os.readlink(caminho).encode("utf-8")).hexdigest()
    if caminho.is_file():
        with caminho.open("rb") as arquivo:
            return hashlib.file_digest(arquivo, "sha256").hexdigest()
    return PASTA if caminho.is_dir() else AUSENTE


def _chaves_de_arquivo(repositorio: Path, saida: str) -> Iterator[tuple[Path, str, str]]:
    """Cada chave que veio de arquivo (e não do `-c`): o arquivo, a chave e o valor. O `-z` dá `origem NUL chave LF valor NUL`."""
    partes = saida.split("\x00")
    for origem, entrada in zip(partes[0::2], partes[1::2], strict=False):
        tipo, _, caminho = origem.partition(":")
        if tipo == ORIGEM_DE_ARQUIVO and caminho:
            chave, _, valor = entrada.partition("\n")
            yield repositorio / caminho, chave.lower(), valor


def _e_include(chave: str) -> bool:
    """`include.path` ou `includeIf.<condição>.path`."""
    return chave == CHAVE_DO_INCLUDE or (chave.startswith(PREFIXO_DO_INCLUDE_CONDICIONAL) and chave.endswith(SUFIXO_DO_INCLUDE_CONDICIONAL))


def _resolvido(valor: str, base: Path) -> Path:
    """O caminho da configuração como o git o lê: `~/` na casa do usuário, o relativo a partir da base."""
    return _casa() / valor[2:] if valor.startswith("~/") else base / valor


def _globais() -> tuple[Path, ...]:
    """A configuração global onde o git a procura: `GIT_CONFIG_GLOBAL`, ou `~/.gitconfig` e `git/config` do XDG."""
    if os.environ.get("GIT_CONFIG_GLOBAL"):
        return (Path(os.environ["GIT_CONFIG_GLOBAL"]),)
    xdg = Path(os.environ["XDG_CONFIG_HOME"]) if os.environ.get("XDG_CONFIG_HOME") else _casa() / ".config"
    return _casa() / ".gitconfig", xdg / "git" / "config"


def _casa() -> Path:
    """A casa do usuário para o git: `HOME`, ou a do sistema."""
    return Path(os.environ["HOME"]) if os.environ.get("HOME") else Path.home()


def _sem_repetir(caminhos: Iterable[Path]) -> tuple[Path, ...]:
    """Os caminhos absolutos, cada um uma vez (no Windows, sem diferença de caixa)."""
    vistos: dict[str, Path] = {}
    for caminho in caminhos:
        absoluto = Path(os.path.abspath(caminho))
        vistos.setdefault(os.path.normcase(absoluto), absoluto)
    return tuple(vistos.values())


def _nome(arquivo: Path, vigia: ArquivosDoGit) -> str:
    """O nome na parada: `.git/...` dentro da pasta comum do git, relativo dentro do repositório, absoluto fora dos dois."""
    for base, prefixo in ((vigia.comum, ".git/"), (vigia.repositorio, "")):
        if arquivo.is_relative_to(base):
            return prefixo + arquivo.relative_to(base).as_posix()
    return arquivo.as_posix()
