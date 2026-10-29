"""Quando o `sed` e o `awk` rodam comando: a trava os trata como texto que ela não lê (orquestrador/git_no_comando.py).

O GNU sed roda o texto num shell pelo comando `e` (`1e git commit`, `$e`) e
pela flag `e` do `s` (`s/.*/git commit/e`); o awk, por `system(...)` e pelos
pipes (`print | "sh"`, `"cmd" | getline`). A busca é por esses sinais no
programa (as palavras soltas e as das opções que o trazem, `-e` e
`--expression` no sed), sem os valores das outras opções (`-F '|'` do awk
não conta); o programa que só se sabe ao rodar conta como se rodasse.
"""

from dataclasses import replace
import re

from graphow.orquestrador.leitura_do_shell import Palavra

SED_QUE_RODA: re.Pattern[str] = re.compile(r"(?:^|[^A-Za-z0-9_\\])[gpiImM0-9]*e(?:$|[\s;}])")
AWK_QUE_RODA: re.Pattern[str] = re.compile(r"system|\|")
OPCOES_COM_PROGRAMA_DO_SED: frozenset[str] = frozenset({"-e", "--expression"})
OPCOES_COM_VALOR_DO_SED: frozenset[str] = frozenset({"-f", "--file", "-l", "--line-length"})
OPCOES_COM_VALOR_DO_AWK: frozenset[str] = frozenset({"-F", "-v", "-f"})


def sed_roda_comando(argumentos: tuple[Palavra, ...]) -> bool:
    """O sed tem `e` no programa, ou um programa que só se sabe ao rodar."""
    scripts = _programa(argumentos, programa=OPCOES_COM_PROGRAMA_DO_SED, valor=OPCOES_COM_VALOR_DO_SED)
    return any(palavra.dinamica or SED_QUE_RODA.search(palavra.texto) for palavra in scripts)


def awk_roda_comando(argumentos: tuple[Palavra, ...]) -> bool:
    """O awk tem `system` ou `|` no programa, ou um programa que só se sabe ao rodar."""
    programas = _programa(argumentos, programa=frozenset(), valor=OPCOES_COM_VALOR_DO_AWK)
    return any(palavra.dinamica or AWK_QUE_RODA.search(palavra.texto) for palavra in programas)


def _programa(argumentos: tuple[Palavra, ...], *, programa: frozenset[str], valor: frozenset[str]) -> list[Palavra]:
    """As palavras com o programa: as soltas e as das opções que o trazem, sem os valores das outras opções."""
    achadas: list[Palavra] = []
    indice = 0
    while indice < len(argumentos):
        palavra = argumentos[indice]
        achadas += list(argumentos[indice + 1:indice + 2]) if palavra.texto in programa else []
        achadas += [palavra] if not palavra.texto.startswith("-") or palavra.dinamica else []
        achadas += [replace(palavra, texto=palavra.texto.split("=", 1)[1])] if palavra.texto.startswith("--expression=") else []
        indice += 2 if palavra.texto in programa | valor else 1
    return achadas
