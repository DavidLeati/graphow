"""A foto do repositório do humano em volta de cada sessão de papel: a camada da trava que não lê o comando.

O hook (orquestrador/git_no_comando.py) lê o texto do comando, e ler nunca
fecha tudo: o script que o agente grava com Write e roda com `bash x.sh` não
cita git, e o `git -C <repositório do humano> checkout -- .` dele apaga o
trabalho não commitado do humano por fora do clone, que é o que a
restauração (orquestrador/trava_do_git.py) cobre. Esta camada não depende do
comando. Antes de cada sessão de papel, o orquestrador fotografa o
repositório de onde o clone saiu: o HEAD e o status (`status --branch
--porcelain=v2 -z`, os não rastreados um a um, com o objeto de cada
rastreado no HEAD e no índice), as refs, as entradas do índice (`ls-files
-s`), o hash do conteúdo de cada arquivo que o status lista e o hash da
configuração (`.git/config`) e de cada arquivo de `.git/hooks`. Junto, guarda
a salvaguarda: o commit de `git stash create` com as mudanças rastreadas e
uma árvore com os não rastreados, cada um como blob (`git hash-object -w`).
São três processos do git por foto quando o repositório está limpo; a
salvaguarda só roda quando há o que guardar. Depois da sessão, com a árvore
de processos dela já morta, a foto é refeita, e a conferência separa a perda
do avanço (orquestrador/conferencia_do_humano.py).

A foto não escreve no repositório do humano. As leituras levam
`--no-optional-locks`, e o `status` não regrava o índice. O `stash create`
regrava o índice ao atualizar os dados de cada arquivo, e por isso roda
sobre uma cópia dele (`GIT_INDEX_FILE`); a árvore dos não rastreados nasce
num índice vazio, também fora do do humano. Só os objetos da salvaguarda
entram no repositório, soltos, e o `git gc` os apaga depois do prazo dele
(duas semanas, por padrão).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from graphow.orquestrador.git_do_goal import EXECUTAVEL_DO_GIT, VARIAVEIS_DE_OUTRO_REPOSITORIO, GitDoGoal

SEM_TRAVA_OPCIONAL: str = "--no-optional-locks"
MENSAGEM_DA_SALVAGUARDA: str = "graphow: salvaguarda do repositorio do humano antes da sessao"
# Quantos campos o registro do `status --porcelain=v2` tem antes do caminho, por tipo (mudado, renomeado, em conflito, solto).
CAMPOS_ANTES_DO_CAMINHO: Mapping[str, int] = {"1": 8, "2": 9, "u": 10, "?": 1}
CABECALHO_DO_STATUS: str = "# branch."
NAO_RASTREADO: str = "?"
AUSENTE: str = "ausente"
PASTA: str = "pasta"
LINK: str = "link "
MODO_DO_SOLTO: str = "100644"


@dataclass(frozen=True)
class ArquivoListado:
    """Um arquivo que o status lista: o tipo do registro (1, 2, u ou ?), o XY e, no rastreado, o modo e o objeto no HEAD
    e o objeto no índice (vazio no caminho em conflito, que tem um por estágio)."""

    tipo: str
    xy: str = ""
    modo_no_head: str = ""
    no_head: str = ""
    no_indice: str = ""

    @property
    def entrada_do_head(self) -> str:
        """A entrada do índice igual à do HEAD (`modo objeto 0`), a que o `reset` ou o `checkout HEAD` devolvem."""
        return f"{self.modo_no_head} {self.no_head} 0"


@dataclass(frozen=True)
class Salvaguarda:
    """O commit de `git stash create` com as mudanças rastreadas e a árvore com os blobs dos não rastreados; vazios sem eles."""

    stash: str = ""
    soltos: str = ""


@dataclass(frozen=True)
class FotoDoHumano:
    """O repositório do humano num instante.

    `cabeca` é a branch e o commit do HEAD; `indice`, as entradas (`modo objeto estágio`) de cada caminho; `listados`, o
    que o status lista; `conteudos`, o sha256 de cada arquivo listado (e dos pedidos, na foto de depois); `do_git`, o
    da configuração e de cada hook. A `salvaguarda` só vem na foto de antes da sessão.
    """

    repositorio: Path
    cabeca: str
    refs: Mapping[str, str]
    indice: Mapping[str, tuple[str, ...]]
    listados: Mapping[str, ArquivoListado]
    conteudos: Mapping[str, str]
    do_git: Mapping[str, str]
    salvaguarda: Salvaguarda = Salvaguarda()


def foto_antes_da_sessao(repositorio: Path | None) -> FotoDoHumano | None:
    """A foto e a salvaguarda de antes da sessão; None sem repositório do humano a guardar."""
    if repositorio is None:
        return None
    foto = fotografar_o_humano(repositorio)
    return replace(foto, salvaguarda=Salvaguarda(_salvaguardar_rastreados(foto), _salvaguardar_soltos(foto)))


def fotografar_o_humano(repositorio: Path, tambem: Iterable[str] = ()) -> FotoDoHumano:
    """O HEAD, o status, as refs, o índice e a pasta do git, com o hash do conteúdo de cada arquivo listado e dos dados."""
    git = GitDoGoal(repositorio)
    cabeca, listados = _status(git)
    conteudos = {caminho: _conteudo(repositorio / caminho) for caminho in dict.fromkeys([*listados, *tambem])}
    return FotoDoHumano(repositorio, cabeca, _refs(git), _indice(git), listados, conteudos, _do_git(repositorio))


def _ler(git: GitDoGoal, *argumentos: str) -> str:
    """A saída da leitura, sem trava opcional (o `status` não regrava o índice); vazia quando o git falha."""
    feito = git.tentar(SEM_TRAVA_OPCIONAL, *argumentos)
    return feito.saida if feito.codigo == 0 else ""


def _status(git: GitDoGoal) -> tuple[str, dict[str, ArquivoListado]]:
    """A branch e o commit do HEAD (dos cabeçalhos do `--branch`) e cada arquivo listado (mudado, renomeado, em conflito,
    não rastreado), pelo caminho."""
    registros = iter(_ler(git, "status", "--branch", "--porcelain=v2", "-z", "--untracked-files=all").split("\x00"))
    cabecalhos: dict[str, str] = {}
    listados: dict[str, ArquivoListado] = {}
    for registro in registros:
        if registro.startswith(CABECALHO_DO_STATUS):
            chave, _, valor = registro.removeprefix(CABECALHO_DO_STATUS).partition(" ")
            cabecalhos[chave] = valor
            continue
        campos = registro.split(" ", CAMPOS_ANTES_DO_CAMINHO.get(registro[:1], 0))
        if registro.startswith("2 "):
            next(registros, "")
        if len(campos) > 1 and registro[:1] in CAMPOS_ANTES_DO_CAMINHO:
            listados[campos[-1]] = _listado(campos)
    return f"{cabecalhos.get('head', '')} {cabecalhos.get('oid', '')}", listados


def _listado(campos: Sequence[str]) -> ArquivoListado:
    """O registro do status já separado: no conflito, o HEAD é o estágio 2 (o nosso)."""
    if campos[0] == "u":
        return ArquivoListado(campos[0], campos[1], campos[4], campos[8])
    if campos[0] == NAO_RASTREADO:
        return ArquivoListado(NAO_RASTREADO)
    return ArquivoListado(campos[0], campos[1], campos[3], campos[6], campos[7])


def _refs(git: GitDoGoal) -> dict[str, str]:
    """Cada ref e o objeto dela."""
    linhas = _ler(git, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    return {nome: objeto for nome, _, objeto in (linha.rpartition(" ") for linha in linhas) if nome}


def _indice(git: GitDoGoal) -> dict[str, tuple[str, ...]]:
    """As entradas do índice (`modo objeto estágio`) de cada caminho; o caminho em conflito tem uma por estágio."""
    entradas: dict[str, tuple[str, ...]] = {}
    for registro in _ler(git, "ls-files", "-s", "-z").split("\x00"):
        entrada, separador, caminho = registro.partition("\t")
        if separador:
            entradas[caminho] = (*entradas.get(caminho, ()), entrada)
    return entradas


def _pastas_do_git(repositorio: Path) -> tuple[Path, Path]:
    """A pasta do git e a comum, iguais fora de worktree ligado: pelo `.git` do repositório, sem processo, ou pelo `rev-parse`."""
    ponto = repositorio / ".git"
    if ponto.is_dir():
        return ponto, ponto
    pastas = _ler(GitDoGoal(repositorio), "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir").splitlines()
    return (Path(pastas[0]), Path(pastas[1])) if len(pastas) == 2 else (ponto, ponto)


def _do_git(repositorio: Path) -> dict[str, str]:
    """O hash da configuração e de cada arquivo de hooks da pasta comum: um `core.hooksPath` ou um hook plantado conta."""
    comum = _pastas_do_git(repositorio)[1]
    hooks = sorted(arquivo for arquivo in (comum / "hooks").rglob("*") if arquivo.is_file()) if (comum / "hooks").is_dir() else []
    return {f".git/{arquivo.relative_to(comum).as_posix()}": _conteudo(arquivo) for arquivo in (comum / "config", *hooks)}


def _conteudo(caminho: Path) -> str:
    """O sha256 do conteúdo (do alvo, no link); `ausente` quando o arquivo não existe, `pasta` no submódulo."""
    if caminho.is_symlink():
        return LINK + hashlib.sha256(os.readlink(caminho).encode("utf-8")).hexdigest()
    if caminho.is_file():
        with caminho.open("rb") as arquivo:
            return hashlib.file_digest(arquivo, "sha256").hexdigest()
    return PASTA if caminho.is_dir() else AUSENTE


def soltos_da_salvaguarda(foto: FotoDoHumano) -> tuple[str, ...]:
    """Os não rastreados que a árvore da salvaguarda guarda: o arquivo comum (o link e a pasta ficam de fora)."""
    return tuple(caminho for caminho, listado in foto.listados.items() if listado.tipo == NAO_RASTREADO and "\n" not in caminho
                 and foto.conteudos.get(caminho, AUSENTE) not in (AUSENTE, PASTA) and not foto.conteudos[caminho].startswith(LINK))


def _salvaguardar_rastreados(foto: FotoDoHumano) -> str:
    """O commit de `git stash create`, sobre uma cópia do índice; vazio sem mudança rastreada (sem processo) ou sem commit."""
    if all(listado.tipo == NAO_RASTREADO for listado in foto.listados.values()):
        return ""
    with tempfile.TemporaryDirectory(prefix="graphow-salvaguarda-") as pasta:
        try:
            shutil.copyfile(_pastas_do_git(foto.repositorio)[0] / "index", Path(pasta) / "index")
        except OSError:
            return ""
        return _git(foto.repositorio, ("stash", "create", MENSAGEM_DA_SALVAGUARDA), indice=Path(pasta) / "index") or ""


def _salvaguardar_soltos(foto: FotoDoHumano) -> str:
    """A árvore com cada não rastreado como blob (`hash-object -w`, os bytes como estão), montada num índice vazio."""
    soltos = soltos_da_salvaguarda(foto)
    entrada = "".join(f"{caminho}\n" for caminho in soltos)
    blobs = (_git(foto.repositorio, ("hash-object", "-w", "--no-filters", "--stdin-paths"), entrada=entrada) or "").split() if soltos else []
    if not soltos or len(blobs) != len(soltos):
        return ""
    entradas = "".join(f"{MODO_DO_SOLTO} {blob}\t{caminho}\x00" for blob, caminho in zip(blobs, soltos, strict=True))
    with tempfile.TemporaryDirectory(prefix="graphow-salvaguarda-") as pasta:
        if _git(foto.repositorio, ("update-index", "-z", "--index-info"), entrada=entradas, indice=Path(pasta) / "index") is None:
            return ""
        return _git(foto.repositorio, ("write-tree",), indice=Path(pasta) / "index") or ""


def _git(repositorio: Path, argumentos: Sequence[str], *, entrada: str = "", indice: Path | None = None) -> str | None:
    """O git da salvaguarda no repositório do humano, com a entrada e o índice dados; a saída, ou None quando ele falha."""
    ambiente = {nome: valor for nome, valor in os.environ.items() if nome.upper() not in VARIAVEIS_DE_OUTRO_REPOSITORIO}
    if indice is not None:
        ambiente["GIT_INDEX_FILE"] = str(indice)
    try:
        feito = subprocess.run([EXECUTAVEL_DO_GIT, "-C", str(repositorio), SEM_TRAVA_OPCIONAL, *argumentos],
                               input=entrada.encode("utf-8"), env=ambiente, capture_output=True, check=False)
    except OSError:
        return None
    return feito.stdout.decode("utf-8", errors="replace").strip() if feito.returncode == 0 else None
