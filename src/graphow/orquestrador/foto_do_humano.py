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
-s`), o hash do conteúdo de cada arquivo que o status lista e o hash de
cada arquivo que muda o que o git roda (orquestrador/arquivos_do_git.py: a
configuração, os includes, os hooks, o exclude e o reflog do stash), com a
lista deles tirada do `git config --list --show-origin`. Junto, guarda a
salvaguarda (orquestrador/salvaguarda_do_humano.py), numa pasta do estado do
Goal: o commit de `git stash create` com as mudanças rastreadas e uma árvore
com os não rastreados, cada um como blob (`git hash-object -w`). São
quatro processos do git na foto de antes e três na de depois quando o
repositório está limpo; a salvaguarda só roda quando há o que guardar. Depois
da sessão, com a árvore de processos dela já morta, a conferência lê de novo
os arquivos do git, sem processo, e só então refaz a foto e separa a perda do
avanço (orquestrador/conferencia_do_humano.py).

A foto não escreve no repositório do humano. Todo git dela roda sem
fsmonitor, sem hooks e sem trava opcional (orquestrador/git_da_foto.py), e o
`status` não regrava o índice. O `stash create` regrava o índice ao
atualizar os dados de cada arquivo, e por isso roda sobre uma cópia dele
(`GIT_INDEX_FILE`); a árvore dos não rastreados nasce num índice vazio,
também fora do do humano; e os objetos da salvaguarda vão para a pasta dela.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from graphow.orquestrador.arquivos_do_git import (
    AUSENTE,
    LINK,
    PASTA,
    ArquivosDoGit,
    arquivos_do_git,
    conteudo_do_arquivo,
    ler_os_arquivos_do_git,
)
from graphow.orquestrador.git_da_foto import git_da_foto
from graphow.orquestrador.salvaguarda_do_humano import PedidoDeSalvaguarda, Salvaguarda, salvaguardar

# Quantos campos o registro do `status --porcelain=v2` tem antes do caminho, por tipo (mudado, renomeado, em conflito, solto).
CAMPOS_ANTES_DO_CAMINHO: Mapping[str, int] = {"1": 8, "2": 9, "u": 10, "?": 1}
CABECALHO_DO_STATUS: str = "# branch."
NAO_RASTREADO: str = "?"


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
class FotoDoHumano:
    """O repositório do humano num instante.

    `cabeca` é a branch e o commit do HEAD; `indice`, as entradas (`modo objeto estágio`) de cada caminho; `listados`, o
    que o status lista; `conteudos`, o sha256 de cada arquivo listado (e dos pedidos, na foto de depois); `do_git`, o
    de cada arquivo que muda o git, pelo nome, e `vigia`, a lista deles, que a foto de antes tira da configuração e a
    conferência de depois relê. A `salvaguarda` só vem na foto de antes da sessão.
    """

    repositorio: Path
    cabeca: str
    refs: Mapping[str, str]
    indice: Mapping[str, tuple[str, ...]]
    listados: Mapping[str, ArquivoListado]
    conteudos: Mapping[str, str]
    do_git: Mapping[str, str]
    vigia: ArquivosDoGit
    salvaguarda: Salvaguarda = Salvaguarda()


def foto_antes_da_sessao(repositorio: Path | None, *, salvaguarda: Path | None = None) -> FotoDoHumano | None:
    """A foto de antes da sessão e, com a pasta dada, a salvaguarda nela; None sem repositório do humano a guardar."""
    if repositorio is None:
        return None
    foto = fotografar_o_humano(repositorio)
    if salvaguarda is None:
        return foto
    rastreado = any(listado.tipo != NAO_RASTREADO for listado in foto.listados.values())
    pedido = PedidoDeSalvaguarda(repositorio, foto.vigia.pasta_do_git / "index", foto.vigia.comum / "objects",
                                 foto.cabeca.rpartition(" ")[2], rastreado, soltos_da_salvaguarda(foto))
    return replace(foto, salvaguarda=salvaguardar(pedido, salvaguarda))


def fotografar_o_humano(repositorio: Path, tambem: Iterable[str] = (), *, vigia: ArquivosDoGit | None = None) -> FotoDoHumano:
    """Os arquivos do git (da lista dada, ou da tirada agora da configuração), o HEAD, o status, as refs e o índice, com o
    hash do conteúdo de cada arquivo listado e dos pedidos."""
    vigia = vigia or arquivos_do_git(repositorio, *_pastas_do_git(repositorio))
    do_git = ler_os_arquivos_do_git(vigia)
    cabeca, listados = _status(repositorio)
    conteudos = {caminho: conteudo_do_arquivo(repositorio / caminho) for caminho in dict.fromkeys([*listados, *tambem])}
    return FotoDoHumano(repositorio, cabeca, _refs(repositorio), _indice(repositorio), listados, conteudos, do_git, vigia)


def _ler(repositorio: Path, *argumentos: str) -> str:
    """A saída da leitura pelo git da foto; vazia quando o git falha."""
    return git_da_foto(repositorio, argumentos) or ""


def _status(repositorio: Path) -> tuple[str, dict[str, ArquivoListado]]:
    """A branch e o commit do HEAD (dos cabeçalhos do `--branch`) e cada arquivo listado (mudado, renomeado, em conflito,
    não rastreado), pelo caminho."""
    registros = iter(_ler(repositorio, "status", "--branch", "--porcelain=v2", "-z", "--untracked-files=all").split("\x00"))
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


def _refs(repositorio: Path) -> dict[str, str]:
    """Cada ref e o objeto dela."""
    linhas = _ler(repositorio, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    return {nome: objeto for nome, _, objeto in (linha.rpartition(" ") for linha in linhas) if nome}


def _indice(repositorio: Path) -> dict[str, tuple[str, ...]]:
    """As entradas do índice (`modo objeto estágio`) de cada caminho; o caminho em conflito tem uma por estágio."""
    entradas: dict[str, tuple[str, ...]] = {}
    for registro in _ler(repositorio, "ls-files", "-s", "-z").split("\x00"):
        entrada, separador, caminho = registro.partition("\t")
        if separador:
            entradas[caminho] = (*entradas.get(caminho, ()), entrada)
    return entradas


def _pastas_do_git(repositorio: Path) -> tuple[Path, Path]:
    """A pasta do git e a comum, iguais fora de worktree ligado: pelo `.git` do repositório, sem processo, ou pelo `rev-parse`."""
    ponto = repositorio / ".git"
    if ponto.is_dir():
        return ponto, ponto
    pastas = _ler(repositorio, "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir").splitlines()
    return (Path(pastas[0]), Path(pastas[1])) if len(pastas) == 2 else (ponto, ponto)


def soltos_da_salvaguarda(foto: FotoDoHumano) -> tuple[str, ...]:
    """Os não rastreados que a árvore da salvaguarda guarda: o arquivo comum (o link e a pasta ficam de fora)."""
    return tuple(caminho for caminho, listado in foto.listados.items() if listado.tipo == NAO_RASTREADO and "\n" not in caminho
                 and foto.conteudos.get(caminho, AUSENTE) not in (AUSENTE, PASTA) and not foto.conteudos[caminho].startswith(LINK))

