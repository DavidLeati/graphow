"""A salvaguarda do repositório do humano, guardada fora dele: a recuperação sobrevive a um `git gc --prune=now`.

Antes de cada sessão de papel, a foto (orquestrador/foto_do_humano.py) guarda
o que a sessão poderia apagar: as mudanças rastreadas e os não rastreados.
Antes, os objetos ficavam soltos no repositório do humano, e a sessão que
fazia `checkout -- .` e depois `gc --prune=now` levava junto a salvaguarda.
Agora eles vão para uma pasta no estado do Goal (`salvaguarda-do-humano`, ao
lado do clone e fora dele), um repositório bare, e a foto não grava objeto no
do humano:
- o rastreado vai pelo `git stash create`, sobre uma cópia do índice
  (`GIT_INDEX_FILE`), com `GIT_OBJECT_DIRECTORY` na pasta e o humano como
  alternate (o `objects/info/alternates` dela). Os objetos novos nascem ali.
  O blob que o `git add` do humano já gravou existe no repositório dele, e
  o redirecionamento não o copia: o `reset --hard` o deixa solto, e o `gc`
  o poda. Por isso o `pack-objects --revs` copia para a pasta o que o stash
  alcança e o HEAD não;
- os não rastreados vão como blob, com a árvore deles, para um diretório de
  objetos da pasta sem alternate (`soltos`). O git não vê o humano dali, e o
  solto igual a um objeto dele (a cópia de um rastreado) é gravado de novo,
  sem tocar no objeto do humano.
A recuperação traz os objetos ao humano com `git fetch` da pasta, pelo hash,
e então roda o `stash apply` e o `restore --source`. Os três são git puro,
sem variável de ambiente nem redireção, e valem no Git Bash, no PowerShell e
no cmd. A pasta não é apagada quando o laço para, nem em FALHA: só quando o
Goal fecha (orquestrador/verificacao_do_goal.py), e não se uma Note de perda
a cita; essa fica para o `recuperar` dela, e o humano a apaga quando quiser.
O conteúdo de antes de um arquivo que a sessão mudou sem perda (o avanço) se
vê sem tocar no humano, com `git -C <pasta> show <hash>:<caminho>`
(`comandos_para_ver`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from graphow.orquestrador.git_da_foto import git_da_foto

PASTA_DA_SALVAGUARDA: str = "salvaguarda-do-humano"
PASTA_DOS_SOLTOS: str = "soltos"
MENSAGEM_DA_SALVAGUARDA: str = "graphow: salvaguarda do repositorio do humano antes da sessao"
MODO_DO_SOLTO: str = "100644"
# O fetch pelo hash, sem ref, também no protocolo v0.
CONFIGURACAO_DA_PASTA: str = "[uploadpack]\n\tallowAnySHA1InWant = true\n"


@dataclass(frozen=True)
class Salvaguarda:
    """O commit de `git stash create` com as mudanças rastreadas, a árvore com os blobs dos não rastreados e a pasta que os
    guarda; vazios sem eles."""

    stash: str = ""
    soltos: str = ""
    pasta: str = ""


@dataclass(frozen=True)
class PedidoDeSalvaguarda:
    """O que guardar do repositório do humano: o arquivo do índice e a pasta de objetos dele, o commit do HEAD, se há
    mudança rastreada e os não rastreados (caminhos relativos)."""

    repositorio: Path
    indice: Path
    objetos: Path
    head: str
    rastreado: bool
    soltos: tuple[str, ...]


def salvaguardar(pedido: PedidoDeSalvaguarda, pasta: Path) -> Salvaguarda:
    """A salvaguarda na pasta, fora do repositório do humano; vazia, sem processo, quando não há o que guardar."""
    if not pedido.rastreado and not pedido.soltos:
        return Salvaguarda()
    if not _preparar_a_pasta(pasta, pedido.objetos):
        return Salvaguarda()
    return Salvaguarda(_rastreados(pedido, pasta), _soltos(pedido, pasta), str(pasta))


def comandos_de_recuperacao(repositorio: Path, salvaguarda: Salvaguarda, soltos: Sequence[str]) -> tuple[str, ...]:
    """O `fetch` que traz da pasta os objetos, o `stash apply` do rastreado e o `restore` dos não rastreados que sumiram."""
    objetos = [objeto for objeto in (salvaguarda.stash, salvaguarda.soltos if soltos else "") if objeto]
    if not objetos or not salvaguarda.pasta:
        return ()
    humano, caminhos = f'git -C "{repositorio}"', " ".join(f'"{caminho}"' for caminho in soltos)
    aplicar = [f"{humano} stash apply {salvaguarda.stash}"] if salvaguarda.stash else []
    devolver = [f"{humano} restore --source={salvaguarda.soltos} -- {caminhos}"] if salvaguarda.soltos and soltos else []
    return f'{humano} fetch --no-tags "{Path(salvaguarda.pasta).as_posix()}" {" ".join(objetos)}', *aplicar, *devolver


def comandos_para_ver(salvaguarda: Salvaguarda, rastreados: Sequence[str], soltos: Sequence[str]) -> tuple[str, ...]:
    """O `git show` que mostra, da pasta da salvaguarda e sem tocar no repositório do humano, o conteúdo de antes de cada
    arquivo: o rastreado no commit do stash, o não rastreado na árvore dos soltos (a pasta vê os objetos do humano)."""
    if not salvaguarda.pasta:
        return ()
    mostrar = f'git -C "{Path(salvaguarda.pasta).as_posix()}" show'
    pares = [*((salvaguarda.stash, caminho) for caminho in rastreados), *((salvaguarda.soltos, caminho) for caminho in soltos)]
    return tuple(f'{mostrar} "{objeto}:{caminho}"' for objeto, caminho in pares if objeto and '"' not in caminho)


def _preparar_a_pasta(pasta: Path, objetos_do_humano: Path) -> bool:
    """O repositório bare da pasta (criado na primeira vez), o diretório dos soltos e o alternate para o humano."""
    if not (pasta / "HEAD").is_file():
        pasta.parent.mkdir(parents=True, exist_ok=True)
        if git_da_foto(pasta.parent, ("init", "-q", "--bare", "--template=", str(pasta))) is None:
            return False
        with (pasta / "config").open("a", encoding="utf-8", newline="\n") as configuracao:
            configuracao.write(CONFIGURACAO_DA_PASTA)
    (pasta / PASTA_DOS_SOLTOS).mkdir(exist_ok=True)
    alternates = pasta / "objects" / "info" / "alternates"
    linhas = f"{objetos_do_humano.as_posix()}\n{(pasta / PASTA_DOS_SOLTOS).as_posix()}\n".encode("utf-8")
    alternates.parent.mkdir(parents=True, exist_ok=True)
    if not alternates.is_file() or alternates.read_bytes() != linhas:
        alternates.write_bytes(linhas)
    return True


def _rastreados(pedido: PedidoDeSalvaguarda, pasta: Path) -> str:
    """O commit de `git stash create` com os objetos na pasta, e o pack do que ele alcança e o HEAD não; vazio sem ele."""
    if not pedido.rastreado:
        return ""
    with tempfile.TemporaryDirectory(prefix="graphow-salvaguarda-") as temporaria:
        indice = Path(temporaria) / "index"
        try:
            shutil.copyfile(pedido.indice, indice)
        except OSError:
            return ""
        ambiente = {"GIT_INDEX_FILE": str(indice), "GIT_OBJECT_DIRECTORY": str(pasta / "objects")}
        stash = _git(pedido.repositorio, ("stash", "create", MENSAGEM_DA_SALVAGUARDA), ambiente) or ""
    if stash:
        _git(pasta, ("pack-objects", "-q", "--revs", str(pasta / "objects" / "pack" / "pack")), entrada=f"{stash}\n^{pedido.head}\n")
    return stash


def _soltos(pedido: PedidoDeSalvaguarda, pasta: Path) -> str:
    """A árvore com cada não rastreado como blob (`hash-object -w`, os bytes como estão), no diretório sem alternate."""
    if not pedido.soltos:
        return ""
    objetos = {"GIT_OBJECT_DIRECTORY": str(pasta / PASTA_DOS_SOLTOS)}
    entrada = "".join(f"{caminho}\n" for caminho in pedido.soltos)
    blobs = (_git(pedido.repositorio, ("hash-object", "-w", "--no-filters", "--stdin-paths"), objetos, entrada=entrada) or "").split()
    if len(blobs) != len(pedido.soltos):
        return ""
    entradas = "".join(f"{MODO_DO_SOLTO} {blob}\t{caminho}\x00" for blob, caminho in zip(blobs, pedido.soltos, strict=True))
    with tempfile.TemporaryDirectory(prefix="graphow-salvaguarda-") as temporaria:
        ambiente = {**objetos, "GIT_INDEX_FILE": str(Path(temporaria) / "index")}
        if _git(pedido.repositorio, ("update-index", "-z", "--index-info"), ambiente, entrada=entradas) is None:
            return ""
        return _git(pedido.repositorio, ("write-tree",), ambiente) or ""


def _git(pasta: Path, argumentos: Sequence[str], ambiente: Mapping[str, str] | None = None, *, entrada: str = "") -> str | None:
    """O git da salvaguarda, com o ambiente e a entrada dados; a saída sem as bordas, ou None quando ele falha."""
    saida = git_da_foto(pasta, argumentos, entrada=entrada.encode("utf-8"), ambiente=ambiente)
    return None if saida is None else saida.strip()
