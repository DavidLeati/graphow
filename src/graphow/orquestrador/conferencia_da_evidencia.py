"""A conferência da Evidence sobre código na leitura: os arquivos que ela afirma mudaram desde o commit dela?

A Evidence ancorada (kernel/ancora_da_evidencia.py) guarda o commit em que o
fato foi visto e os arquivos que ela afirma. Quem a lê pergunta ao git da área
do Goal, ou ao repositório do humano, o que mudou entre esse commit e a ponta,
e a Evidence sai num de três estados:

- `vigente`: nenhum dos arquivos que ela afirma mudou;
- `desatualizada`: algum mudou, e eles vêm na conferência;
- `sem_ancora`: a Evidence antiga, sem commit, ou o commit que não existe mais
  no repositório (a história reescrita e coletada, o clone recriado depois de
  um rebase), com o motivo.

O rebase da branch do Goal (orquestrador/registro_do_rebase.py) troca o hash
dos commits, e o commit da Evidence sai da história da ponta sem sumir do
clone. A conferência compara as árvores, e não a história: o que a base trouxe
para um arquivo da Evidence a deixa desatualizada, e o resto não. O motivo diz
que o commit saiu da história.

A revisão de risco julga a mudança fora de commit, em cima do HEAD: ela guarda
também a `arvore` revisada, e a conferência parte dela, para que o próprio
commit da fatia não a deixe desatualizada. A Evidence localizada num arquivo
fora de repositório git confere pelo `sha256` do conteúdo dele.

É uma leitura: um `git diff --name-only` por par de commits, sem renomeação
(o arquivo renomeado aparece pelo caminho antigo, que é o que a Evidence cita).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import PurePosixPath
from typing import Any

from graphow.core.orquestracao import ler_texto
from graphow.kernel.ancora_da_evidencia import CAMPO_COMMIT, CAMPO_SHA256, ancora_da_evidencia, arquivos_afirmados
from graphow.kernel.ancora_do_artifact import ANCORA_SHA256, PADRAO_DO_COMMIT
from graphow.kernel.localizacao import CAMPO_ARQUIVO
from graphow.orquestrador.git_do_goal import GitDoGoal

VIGENTE: str = "vigente"
DESATUALIZADA: str = "desatualizada"
SEM_ANCORA: str = "sem_ancora"
CAMPO_ARVORE: str = "arvore"


@dataclass(frozen=True)
class ConferenciaDaEvidencia:
    """O estado da Evidence na ponta, os arquivos dela que mudaram (na desatualizada) e o motivo, quando há."""

    estado: str
    arquivos: tuple[str, ...] = ()
    motivo: str = ""

    @property
    def vigente(self) -> bool:
        """A Evidence vale como fato na ponta."""
        return self.estado == VIGENTE


def conferir_evidencia(propriedades: Mapping[str, Any], git: GitDoGoal, ponta: str = "HEAD") -> ConferenciaDaEvidencia:
    """A Evidence conferida contra a ponta dada, no git dado (a área do Goal ou o repositório do humano)."""
    ancora = ancora_da_evidencia(propriedades)
    if ancora is None:
        commit = ler_texto(propriedades, CAMPO_COMMIT)
        motivo = f"'commit' {commit!r} nao e um hash do git" if commit else "a Evidence nao tem o commit em que foi vista"
        return ConferenciaDaEvidencia(SEM_ANCORA, motivo=motivo)
    if ancora == ANCORA_SHA256:
        return _conferir_o_conteudo(propriedades, git)
    commit = ler_texto(propriedades, CAMPO_COMMIT)
    arvore = ler_texto(propriedades, CAMPO_ARVORE)
    origem = arvore if PADRAO_DO_COMMIT.fullmatch(arvore) else commit
    if git.tentar("cat-file", "-e", f"{origem}^{{tree}}").codigo != 0:
        objeto = f"a arvore revisada {origem[:12]}" if origem == arvore else f"o commit {origem[:12]}"
        return ConferenciaDaEvidencia(SEM_ANCORA, motivo=f"{objeto} nao existe mais no repositorio: a historia foi reescrita ou o clone e outro")
    mudaram = _afirmados_que_mudaram(arquivos_afirmados(propriedades), arquivos_mudados(git, origem, ponta))
    fora = "" if git.e_ancestral(commit, ponta) else (f"o commit {commit[:12]} saiu da historia da ponta (rebase): conferido "
                                                      "pela diferenca entre as arvores")
    return ConferenciaDaEvidencia(DESATUALIZADA if mudaram else VIGENTE, mudaram, fora)


def arquivos_mudados(git: GitDoGoal, antes: str, depois: str) -> tuple[str, ...]:
    """Os caminhos que mudaram entre as duas árvores, como o git os escreve, o renomeado pelas duas pontas."""
    saida = git.rodar("diff", "--name-only", "-z", "--no-renames", antes, depois, "--")
    return tuple(caminho for caminho in saida.split("\0") if caminho)


def _afirmados_que_mudaram(afirmados: Sequence[str] | None, mudados: Sequence[str]) -> tuple[str, ...]:
    """Os arquivos afirmados que mudaram, como a Evidence os escreve; todos os mudados, quando ela fala do commit inteiro."""
    if afirmados is None:
        return tuple(mudados)
    no_diff = {_caminho_do_git(caminho) for caminho in mudados}
    return tuple(caminho for caminho in dict.fromkeys(afirmados) if _caminho_do_git(caminho) in no_diff)


def _caminho_do_git(caminho: str) -> str:
    """O caminho como o git o escreve: barras para a frente e sem o `./` do começo."""
    return str(PurePosixPath(caminho.strip().replace("\\", "/")))


def _conferir_o_conteudo(propriedades: Mapping[str, Any], git: GitDoGoal) -> ConferenciaDaEvidencia:
    """A Evidence localizada fora de repositório git: o `sha256` do arquivo na pasta ainda é o que ela guardou?"""
    arquivo = ler_texto(propriedades, CAMPO_ARQUIVO)
    caminho = git.pasta / arquivo
    if not caminho.is_file():
        return ConferenciaDaEvidencia(DESATUALIZADA, (arquivo,), f"{arquivo} nao existe mais na pasta")
    atual = hashlib.sha256(caminho.read_bytes()).hexdigest()
    mudou = atual != ler_texto(propriedades, CAMPO_SHA256).lower()
    return ConferenciaDaEvidencia(DESATUALIZADA if mudou else VIGENTE, (arquivo,) if mudou else ())
