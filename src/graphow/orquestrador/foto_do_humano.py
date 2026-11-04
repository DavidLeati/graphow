"""A foto do repositório do humano em volta de cada sessão de papel: a camada da trava que não lê o comando.

O hook (orquestrador/git_no_comando.py) lê o texto do comando, e ler nunca
fecha tudo: o script que o agente grava com Write e roda com `bash x.sh` não
cita git, e o `git -C <repositório do humano> checkout -- .` dele apaga o
trabalho não commitado do humano por fora do clone, que é o que a
restauração (orquestrador/trava_do_git.py) cobre. Esta camada não depende do
comando. Antes de cada sessão de papel, o orquestrador fotografa o
repositório de onde o clone saiu: o HEAD, as refs, as entradas do índice
(`ls-files -s`) e o status (`status --porcelain=v2 -z`, os não rastreados um
a um), com o hash do conteúdo de cada arquivo que o status lista. Junto,
guarda uma salvaguarda das mudanças rastreadas, o commit de `git stash
create`, que só grava objetos. Depois da sessão, com a árvore de processos
dela já morta, refaz a foto. Se ela mudou, a parada vai ao livro-razão e o
laço para em FALHA com o motivo `repositorio_do_humano_mexido`, o que mudou,
o hash da salvaguarda e o `git stash apply` que a recupera.

Não há como saber quem mexeu: a mudança que o próprio humano faz no
repositório durante a sessão (um commit, uma edição, outro Goal que avança a
branch dele) também para o laço. É o lado seguro; o humano confere e roda o
Goal de novo.

A foto não escreve no repositório do humano. As leituras levam
`--no-optional-locks`, e o `status` não regrava o índice. O `stash create`
regrava o índice ao atualizar os dados de cada arquivo, e por isso roda
sobre uma cópia dele (`GIT_INDEX_FILE`); a foto compara as entradas do
índice, e não os bytes do arquivo. Só os objetos da salvaguarda entram no
repositório, soltos, e o `git gc` os apaga depois do prazo dele (duas
semanas, por padrão).

Limites: o arquivo não rastreado que a sessão apagou não tem salvaguarda (o
`stash create` só leva o rastreado; o git aceita `stash create -u`, mas lê o
`-u` como a mensagem do stash e deixa o não rastreado de fora); o ignorado
não entra na foto, nem a configuração e os hooks de `.git/`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from graphow.core.exceptions import GraphowError
from graphow.orquestrador.git_do_goal import EXECUTAVEL_DO_GIT, VARIAVEIS_DE_OUTRO_REPOSITORIO, GitDoGoal

MOTIVO_DA_PARADA: str = "repositorio_do_humano_mexido"
SEM_TRAVA_OPCIONAL: str = "--no-optional-locks"
MENSAGEM_DA_SALVAGUARDA: str = "graphow: salvaguarda do repositorio do humano antes da sessao"
# Quantos campos o registro do `status --porcelain=v2` tem antes do caminho, por tipo (mudado, renomeado, em conflito, solto).
CAMPOS_ANTES_DO_CAMINHO: Mapping[str, int] = {"1": 8, "2": 9, "u": 10, "?": 1}
LIMITE_DE_MUDANCAS_NA_PARADA: int = 20


@dataclass(frozen=True)
class FotoDoHumano:
    """O repositório do humano num instante: cada item (o HEAD, cada ref, entrada do índice e arquivo do status) e o valor.

    `salvaguarda` é o commit de `git stash create` da foto de antes da sessão; vazio sem mudança rastreada.
    """

    repositorio: Path
    itens: Mapping[str, str]
    salvaguarda: str = ""


@dataclass(frozen=True)
class HumanoMexido:
    """O que mudou no repositório do humano durante a sessão e a salvaguarda de antes dela."""

    repositorio: Path
    mudancas: tuple[str, ...]
    salvaguarda: str

    @property
    def recuperar(self) -> str:
        """O comando que devolve as mudanças rastreadas de antes da sessão; vazio sem salvaguarda."""
        return f'git -C "{self.repositorio}" stash apply {self.salvaguarda}' if self.salvaguarda else ""

    @property
    def resumo(self) -> tuple[str, ...]:
        """As primeiras mudanças e quantas sobram."""
        sobra = len(self.mudancas) - LIMITE_DE_MUDANCAS_NA_PARADA
        return (*self.mudancas[:LIMITE_DE_MUDANCAS_NA_PARADA], *([f"e mais {sobra}"] if sobra > 0 else []))


# Quem guarda no livro-razão o repositório do humano mexido: o papel, a fatia (vazia fora delas) e o que mudou.
RegistroDoHumanoMexido = Callable[[str, str, HumanoMexido], None]


class RepositorioDoHumanoMexido(GraphowError):
    """A sessão de papel mexeu no repositório do humano, ou ele mexeu durante ela: o laço para em FALHA."""


def foto_antes_da_sessao(repositorio: Path | None) -> FotoDoHumano | None:
    """A foto e a salvaguarda de antes da sessão; None sem repositório do humano a guardar."""
    if repositorio is None:
        return None
    return FotoDoHumano(repositorio, fotografar_o_humano(repositorio).itens, salvaguardar(repositorio))


def conferir_o_humano(antes: FotoDoHumano | None, papel: str, fatia: str, *, registrar: RegistroDoHumanoMexido | None = None) -> None:
    """Depois da sessão, a foto refeita; a que mudou vai ao livro-razão e para o laço (`RepositorioDoHumanoMexido`)."""
    if antes is None:
        return
    mudancas = diferencas(antes, fotografar_o_humano(antes.repositorio))
    if not mudancas:
        return
    mexido = HumanoMexido(antes.repositorio, mudancas, antes.salvaguarda)
    if registrar is not None:
        registrar(papel, fatia, mexido)
    raise RepositorioDoHumanoMexido(
        mensagem_da_parada(mexido, papel), {"repositorio": str(mexido.repositorio), "salvaguarda": mexido.salvaguarda or "nenhuma"}
    )


def mensagem_da_parada(mexido: HumanoMexido, papel: str) -> str:
    """O motivo, o que mudou, a salvaguarda e o comando que a recupera."""
    salvaguarda = (f"A salvaguarda das mudancas rastreadas de antes da sessao e o commit {mexido.salvaguarda}: recupere com "
                   f"`{mexido.recuperar}`." if mexido.salvaguarda else "Antes da sessao nao havia mudanca rastreada a salvaguardar.")
    return (f"{MOTIVO_DA_PARADA}: o repositorio do humano ({mexido.repositorio}) mudou durante a sessao do {papel}: "
            f"{'; '.join(mexido.resumo)}. {salvaguarda} Arquivo nao rastreado apagado nao tem salvaguarda. Se foi voce quem "
            "mexeu durante a sessao, confira e rode o Goal de novo; se nao, a sessao mexeu fora do clone do Goal, e o que ela "
            "fez la nao foi desfeito.")


def fotografar_o_humano(repositorio: Path) -> FotoDoHumano:
    """O HEAD, as refs, as entradas do índice e o status, com o hash do conteúdo de cada arquivo listado; sem escrever."""
    git = GitDoGoal(repositorio)
    cabeca = f"{_ler(git, 'symbolic-ref', '-q', 'HEAD').strip()} {_ler(git, 'rev-parse', '-q', '--verify', 'HEAD').strip()}"
    return FotoDoHumano(repositorio, {"HEAD": cabeca, **_refs(git), **_indice(git), **_status(git)})


def diferencas(antes: FotoDoHumano, depois: FotoDoHumano) -> tuple[str, ...]:
    """O que mudou de uma foto para a outra, item a item."""
    chaves = sorted(set(antes.itens) | set(depois.itens))
    return tuple(_diferenca(chave, antes.itens.get(chave), depois.itens.get(chave)) for chave in chaves
                 if antes.itens.get(chave) != depois.itens.get(chave))


def _diferenca(chave: str, antes: str | None, depois: str | None) -> str:
    """Um item que apareceu, sumiu ou mudou."""
    if antes is None:
        return f"{chave} apareceu ({depois})"
    if depois is None:
        return f"{chave} sumiu (era {antes})"
    return f"{chave}: {antes} -> {depois}"


def _ler(git: GitDoGoal, *argumentos: str) -> str:
    """A saída da leitura, sem trava opcional (o `status` não regrava o índice); vazia quando o git falha."""
    feito = git.tentar(SEM_TRAVA_OPCIONAL, *argumentos)
    return feito.saida if feito.codigo == 0 else ""


def _refs(git: GitDoGoal) -> dict[str, str]:
    """Cada ref e o objeto dela."""
    linhas = _ler(git, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    return {f"ref {nome}": objeto for nome, _, objeto in (linha.rpartition(" ") for linha in linhas) if nome}


def _indice(git: GitDoGoal) -> dict[str, str]:
    """Cada entrada do índice (`modo objeto estágio`), pelo caminho; o caminho em conflito tem uma por estágio."""
    registros = [registro.split("\t", 1) for registro in _ler(git, "ls-files", "-s", "-z").split("\x00") if "\t" in registro]
    return {f"indice {caminho}" + ("" if entrada.endswith(" 0") else f" [{entrada[-1]}]"): entrada for entrada, caminho in registros}


def _status(git: GitDoGoal) -> dict[str, str]:
    """Cada arquivo que o status lista (mudado, renomeado, em conflito, não rastreado): o tipo, o XY e o hash do conteúdo."""
    campos = iter(_ler(git, "status", "--porcelain=v2", "-z", "--untracked-files=all").split("\x00"))
    itens: dict[str, str] = {}
    for registro in campos:
        separados = registro.split(" ", CAMPOS_ANTES_DO_CAMINHO.get(registro[:1], 0))
        if registro.startswith("2 "):
            next(campos, "")
        if len(separados) > 1:
            itens[f"status {separados[-1]}"] = f"{' '.join(separados[:-1][:2])} {_conteudo(git.pasta / separados[-1])}"
    return itens


def _conteudo(caminho: Path) -> str:
    """O sha256 do conteúdo (do alvo, no link); `ausente` quando o arquivo não existe, `pasta` no submódulo."""
    if caminho.is_symlink():
        return "link " + hashlib.sha256(os.readlink(caminho).encode("utf-8")).hexdigest()
    if caminho.is_file():
        with caminho.open("rb") as arquivo:
            return hashlib.file_digest(arquivo, "sha256").hexdigest()
    return "pasta" if caminho.is_dir() else "ausente"


def salvaguardar(repositorio: Path) -> str:
    """O commit de `git stash create` com as mudanças rastreadas, sobre uma cópia do índice; vazio sem mudança ou sem commit."""
    indice = repositorio / GitDoGoal(repositorio).tentar("rev-parse", "--git-path", "index").saida.strip()
    if not indice.is_file():
        return ""
    ambiente = {nome: valor for nome, valor in os.environ.items() if nome.upper() not in VARIAVEIS_DE_OUTRO_REPOSITORIO}
    with tempfile.TemporaryDirectory(prefix="graphow-salvaguarda-") as pasta:
        try:
            shutil.copyfile(indice, Path(pasta) / "index")
            feito = subprocess.run([EXECUTAVEL_DO_GIT, "-C", str(repositorio), SEM_TRAVA_OPCIONAL, "stash", "create", MENSAGEM_DA_SALVAGUARDA],
                                   env={**ambiente, "GIT_INDEX_FILE": str(Path(pasta) / "index")}, capture_output=True, check=False)
        except OSError:
            return ""
    return feito.stdout.decode("utf-8", errors="replace").strip() if feito.returncode == 0 else ""
