"""O diff das correções que vai à conferência: o resumo de todos os arquivos, o corpo do código primeiro e o aviso do corte.

Na revisão da T2e, o diff ia cortado em 8000 caracteres, na ordem alfabética
do git e sem aviso: num caso real, de 26 arquivos chegaram 3, porque `docs/` e
o README ocupavam o espaço antes de `src/`. Agora vai primeiro o `--stat`
inteiro, com todos os arquivos, e depois o corpo de cada um, até o limite:
`src/` e os testes antes do resto, `docs/` e o README por último. O arquivo
que não cabe inteiro vai cortado, e o aviso diz qual foi e quais ficaram de
fora, com o comando que os mostra.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import re

from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.git_do_goal import GitDoGoal

# Quanto do corpo do diff vai à conferência; o resumo vai inteiro.
LIMITE_DO_CORPO: int = 8000
# O `--stat` com o caminho inteiro (sem o `...` do git) e o gráfico de `+-` curto.
RESUMO_SEM_ABREVIAR: tuple[str, ...] = ("--stat=1000,900", "--stat-graph-width=20")
PASTAS_DE_TESTE: frozenset[str] = frozenset({"tests", "test", "__tests__", "spec"})
# O arquivo de teste fora das pastas de teste: `test_x.py`, `x_test.go`, `x.test.ts`, `x.spec.js`.
NOME_DE_TESTE: re.Pattern[str] = re.compile(r"^test_|[._-](test|spec)\.[^.]+$")


@dataclass(frozen=True)
class CorpoDoDiff:
    """O corpo que coube no limite, o arquivo cortado no meio e os que ficaram de fora."""

    texto: str
    cortado: str = ""
    fora: tuple[str, ...] = ()


def diff_das_correcoes(git: GitDoGoal, antes: str, slug: str) -> str:
    """O resumo e o corpo do diff do commit da verificação anterior até o atual, sem o documento do Goal; vazio sem o commit de antes."""
    if not antes:
        return ""
    alcance = (f"{antes}..HEAD", "--", ".", f":(exclude){caminho_do_documento(slug)}")
    resumo = git.tentar("diff", *RESUMO_SEM_ABREVIAR, *alcance).saida.rstrip()
    if not resumo:
        return ""
    nomes = [nome for nome in git.tentar("diff", "--name-only", "-z", *alcance).saida.split("\0") if nome]
    return _texto(antes, resumo, _corpo(git, antes, sorted(nomes, key=prioridade_no_diff)))


def prioridade_no_diff(caminho: str) -> int:
    """A ordem do arquivo no corpo: `src/`, os testes, o resto e, por último, `docs/` e o README."""
    partes = caminho.lower().split("/")
    if partes[0] == "docs" or partes[-1].startswith("readme"):
        return 3
    if partes[0] == "src":
        return 0
    return 1 if PASTAS_DE_TESTE & set(partes[:-1]) or NOME_DE_TESTE.search(partes[-1]) else 2


def _corpo(git: GitDoGoal, antes: str, arquivos: Sequence[str]) -> CorpoDoDiff:
    """O diff de cada arquivo, na ordem, até o limite: o que não cabe inteiro vai cortado, e os seguintes ficam de fora."""
    partes: list[str] = []
    restante = LIMITE_DO_CORPO
    for indice, caminho in enumerate(arquivos):
        diff = git.tentar("diff", f"{antes}..HEAD", "--", f":(literal){caminho}").saida
        if len(diff) > restante:
            return CorpoDoDiff("".join((*partes, diff[:restante])), caminho, tuple(arquivos[indice + 1:]))
        partes.append(diff)
        restante -= len(diff)
    return CorpoDoDiff("".join(partes))


def _texto(antes: str, resumo: str, corpo: CorpoDoDiff) -> str:
    """O resumo, o corpo e, quando o limite cortou, o aviso do que não veio e de como vê-lo."""
    curto = antes[:12]
    linhas = [f"Resumo, com todos os arquivos (`git diff --stat {curto}..HEAD`):", f"```\n{resumo}\n```",
              "Corpo, com `src/` e os testes antes do resto, e `docs/` e o README por ultimo:",
              f"```diff\n{corpo.texto.rstrip()}\n```"]
    if corpo.cortado:
        fora = f"; ficaram de fora: {', '.join(corpo.fora)}" if corpo.fora else ""
        linhas.append(f"Aviso: o corpo vai ate {LIMITE_DO_CORPO} caracteres. O diff de {corpo.cortado} foi cortado no meio{fora}. "
                      f"Veja o que falta com `git diff {curto}..HEAD -- <arquivo>`.")
    return "\n".join(linhas)
