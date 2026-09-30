"""O que o ramo base ganhou desde que o ramo do Goal saiu dele, perguntado ao git.

É a metade de `graphow base-colisoes` que roda processo: atualiza o ramo base
quando ele é de um remoto, acha o merge-base com o HEAD e lista os arquivos
que o ramo base acrescentou ou alterou desde então. O git roda com lista de
argumentos, sem shell, e o nome do ramo vem do grafo: um nome que começa por
`-` seria lido como opção, e é recusado antes de chegar ao git.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess

from graphow.api.colisoes_base import separar_remoto
from graphow.core.exceptions import GraphowError

EXECUTAVEL_DO_GIT: str = "git"
SEPARADOR_NULO: str = "\0"
# Acrescentado, copiado, alterado ou renomeado: o que o ramo base ganhou. A
# remoção não traz arquivo novo para colidir.
FILTRO_DO_QUE_O_RAMO_GANHOU: str = "--diff-filter=ACMR"
TAMANHO_DO_SHA_CURTO: int = 12


class FalhaDoGit(GraphowError):
    """O git não respondeu o que a conferência precisa: sem ele, ela não diz nada."""


class GitIndisponivel(FalhaDoGit):
    """O executável do git não rodou."""


class GitRecusou(FalhaDoGit):
    """O git rodou e saiu com erro; o contexto traz a saída de erro dele."""


@dataclass(frozen=True)
class ExecutorGit:
    """Roda o git dentro de um repositório e devolve a saída, ou recusa com o erro dele."""

    repositorio: Path

    def rodar(self, *argumentos: str) -> str:
        """A saída padrão do comando; `FalhaDoGit` com a saída de erro quando ele falha."""
        comando = [EXECUTAVEL_DO_GIT, "-C", str(self.repositorio), *argumentos]
        try:
            resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", check=False)
        except OSError as erro:
            raise GitIndisponivel("git indisponivel", {"erro": str(erro)}) from erro
        if resultado.returncode != 0:
            raise GitRecusou("git recusou o comando", {"comando": " ".join(argumentos), "erro": resultado.stderr.strip()})
        return resultado.stdout


@dataclass(frozen=True)
class ComparacaoComBase:
    """O merge-base com o ramo base e o que o ramo base ganhou desde ele."""

    merge_base: str
    arquivos: tuple[str, ...]
    aviso: str = ""


def comparar_com_ramo_base(git: ExecutorGit, ramo_base: str, *, buscar: bool) -> ComparacaoComBase:
    """Atualiza o ramo base se pedido, acha o merge-base com o HEAD e lista o que o ramo base ganhou.

    O fetch que falha, sem rede por exemplo, não derruba a conferência: ela
    segue com a cópia local do ramo remoto e devolve o aviso, porque conferir
    contra o que se tem ainda é melhor que não conferir.
    """
    _recusar_nome_de_opcao(ramo_base)
    aviso = _buscar(git, ramo_base) if buscar else ""
    _conferir_que_existe(git, ramo_base)
    merge_base = git.rodar("merge-base", "HEAD", ramo_base).strip()
    saida = git.rodar("diff", "--name-only", "-z", FILTRO_DO_QUE_O_RAMO_GANHOU, merge_base, ramo_base)
    arquivos = tuple(caminho for caminho in saida.split(SEPARADOR_NULO) if caminho)
    return ComparacaoComBase(merge_base=merge_base[:TAMANHO_DO_SHA_CURTO], arquivos=arquivos, aviso=aviso)


def _buscar(git: ExecutorGit, ramo_base: str) -> str:
    """`git fetch <remoto> <ramo>` quando o ramo base é de um remoto; o aviso quando o fetch falha."""
    remoto, ramo = separar_remoto(ramo_base, git.rodar("remote").split())
    if not remoto:
        return ""
    try:
        git.rodar("fetch", "--quiet", remoto, ramo)
    except GitRecusou as falha:
        motivo = (falha.contexto.get("erro") or falha.mensagem).splitlines()[0]
        return f"fetch de {remoto} {ramo} falhou ({motivo}); comparando com a copia local de {ramo_base}"
    return ""


def _conferir_que_existe(git: ExecutorGit, ramo_base: str) -> None:
    """O ramo base aponta para um commit neste repositório; senão, a recusa diz qual ramo faltou."""
    try:
        git.rodar("rev-parse", "--verify", "--quiet", f"{ramo_base}^{{commit}}")
    except GitRecusou as falha:
        raise FalhaDoGit("ramo base inexistente neste repositorio", {"ramo_base": ramo_base}) from falha


def _recusar_nome_de_opcao(ramo_base: str) -> None:
    """Nome de ramo vazio, ou com um trecho entre barras que começa por `-`, não chega ao git.

    O trecho conta porque, em `origin/-x`, é `-x` que vai sozinho ao fetch.
    """
    if not ramo_base or any(trecho.startswith("-") for trecho in ramo_base.split("/")):
        raise FalhaDoGit("ramo_base invalido", {"ramo_base": ramo_base})
