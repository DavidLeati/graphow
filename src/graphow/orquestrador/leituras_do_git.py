"""Quais invocações do git a trava deixa o agente rodar: só as leituras, com as opções que não gravam nem rodam nada.

É a parte da decisão do hook (orquestrador/git_no_comando.py) que olha os
argumentos de um git já achado no comando. Passam:
- as leituras inteiras: `status`, `diff`, `log`, `show`, `blame`, `ls-files`,
  `rev-parse`, `grep`, `ls-tree`, `rev-list`, `merge-base`, `cat-file`;
- as que leem só em parte: `branch` que lista (`--show-current`, `-a`, `-v`,
  `--list` com padrões...), `stash list` e `stash show`, `remote` e
  `remote -v`;
- as opções globais que não trocam configuração nem programa (`-C`,
  `--no-pager`...) e `-c` só com chave inofensiva (`core.quotepath`,
  `color.*`); nunca `core.pager`, `core.fsmonitor`, `core.hooksPath`,
  `alias.*` nem `*.command`, que rodam o programa que o agente escolher.
Nas leituras, `--output` (que grava o arquivo que o agente der, até um ref
dentro de `.git/`, sem transação nenhuma) e o `-O` do `git grep` (que abre os
arquivos num programa) são recusados, abreviados ou não.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from graphow.orquestrador.leitura_do_shell import Palavra

LEITURAS_DO_GIT: tuple[str, ...] = ("status", "diff", "log", "show", "blame", "ls-files", "rev-parse", "grep", "ls-tree",
                                    "rev-list", "merge-base", "cat-file")
LEITURAS_EM_TEXTO: str = ", ".join(LEITURAS_DO_GIT) + ", branch que lista, stash list/show e remote -v"
OPCOES_GLOBAIS_COM_VALOR: frozenset[str] = frozenset({"-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"})
OPCOES_GLOBAIS_SEM_VALOR: frozenset[str] = frozenset({
    "--no-pager", "-p", "--paginate", "-P", "--bare", "--no-replace-objects", "--no-lazy-fetch", "--literal-pathspecs",
    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks", "--no-advice",
})
OPCOES_DE_LISTAR_BRANCH: frozenset[str] = frozenset({
    "--show-current", "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "--list", "-l", "--color", "--no-color",
    "--column", "--no-column", "--sort", "--format", "--abbrev", "--no-abbrev", "-i", "--ignore-case", "--omit-empty",
})
# As opções de leitura que gravam arquivo ou rodam programa, e o menor prefixo que o git aceita como abreviação delas.
OPCOES_QUE_GRAVAM: tuple[tuple[str, int], ...] = (("--output", 4), ("--open-files-in-pager", 4))


@dataclass(frozen=True)
class _Subcomando:
    """O subcomando achado depois das opções globais e o que vem depois dele."""

    nome: str
    argumentos: tuple[Palavra, ...]


def motivo_do_git(argumentos: tuple[Palavra, ...]) -> str:
    """Por que a trava recusa o git com estes argumentos; vazio quando é leitura que passa."""
    subcomando = _subcomando(argumentos)
    if isinstance(subcomando, str):
        return subcomando
    if subcomando.nome in LEITURAS_DO_GIT:
        return _opcao_que_grava(subcomando)
    parcial = LEITURAS_EM_PARTE.get(subcomando.nome)
    if parcial is None or not parcial(subcomando.argumentos):
        return f"git {subcomando.nome} recusado"
    return _opcao_que_grava(subcomando)


def _subcomando(argumentos: tuple[Palavra, ...]) -> _Subcomando | str:
    """O subcomando depois das opções globais; sem ele, o motivo da recusa."""
    indice = 0
    while indice < len(argumentos):
        palavra = argumentos[indice]
        if palavra.dinamica:
            return "opcao ou subcomando do git que so se sabe ao rodar"
        if not palavra.texto.startswith("-"):
            return _Subcomando(palavra.texto, argumentos[indice + 1:])
        passo = _opcao_global(argumentos, indice)
        if isinstance(passo, str):
            return passo
        indice += passo
    return "git sem subcomando"


def _opcao_global(argumentos: tuple[Palavra, ...], indice: int) -> int | str:
    """Quantas palavras a opção global ocupa; o motivo, quando ela troca a configuração ou o programa do git."""
    texto = argumentos[indice].texto
    if texto == "-c":
        chave = argumentos[indice + 1] if indice + 1 < len(argumentos) else None
        inofensiva = chave is not None and not chave.dinamica and chave_inofensiva(chave.texto)
        return 2 if inofensiva else f"git -c {chave.texto if chave else ''}: a opcao troca a configuracao ou o programa do git"
    opcao = texto.split("=", 1)[0]
    if texto.startswith("-c") or opcao in ("--config-env", "--exec-path"):
        return f"git {texto}: a opcao troca a configuracao ou o programa do git"
    if opcao not in OPCOES_GLOBAIS_COM_VALOR | OPCOES_GLOBAIS_SEM_VALOR:
        return f"git {texto}: opcao que a trava nao libera"
    return 2 if texto in OPCOES_GLOBAIS_COM_VALOR else 1


def chave_inofensiva(atribuicao: str) -> bool:
    """A chave do `git -c chave=valor` só muda a saída: `core.quotepath` ou `color.*` (nenhum `*.command`)."""
    chave = atribuicao.split("=", 1)[0].lower()
    return chave == "core.quotepath" or (chave.startswith("color.") and not chave.endswith(".command"))


def _opcao_que_grava(subcomando: _Subcomando) -> str:
    """O motivo da leitura com `--output` (ou o `-O` do grep), abreviada ou não; vazio sem ela."""
    for palavra in subcomando.argumentos:
        opcao = palavra.texto.split("=", 1)[0]
        grava = any(opcao == longa or (len(opcao) >= minimo and longa.startswith(opcao)) for longa, minimo in OPCOES_QUE_GRAVAM)
        if grava or (subcomando.nome == "grep" and _o_maiusculo(opcao)):
            return f"git {subcomando.nome} {palavra.texto}: a opcao grava arquivo ou roda programa"
    return ""


def _o_maiusculo(opcao: str) -> bool:
    """O `-O` do `git grep`, sozinho ou junto de outras letras (`-nO`, `-Ovim`)."""
    return opcao.startswith("-") and not opcao.startswith("--") and "O" in opcao


def _branch_que_lista(argumentos: tuple[Palavra, ...]) -> bool:
    """`git branch` só com opções de listar; nome solto só com `--list` ou `-l`, em que ele é padrão."""
    textos = [palavra.texto for palavra in argumentos]
    if any(palavra.dinamica for palavra in argumentos):
        return False
    opcoes = [texto.split("=", 1)[0] for texto in textos if texto.startswith("-")]
    soltos = len(textos) - len(opcoes)
    return all(opcao in OPCOES_DE_LISTAR_BRANCH for opcao in opcoes) and (not soltos or bool({"--list", "-l"} & set(opcoes)))


def _stash_que_lista(argumentos: tuple[Palavra, ...]) -> bool:
    """`git stash list` e `git stash show`."""
    return bool(argumentos) and not argumentos[0].dinamica and argumentos[0].texto in ("list", "show")


def _remote_que_lista(argumentos: tuple[Palavra, ...]) -> bool:
    """`git remote` e `git remote -v`."""
    return all(not palavra.dinamica and palavra.texto in ("-v", "--verbose") for palavra in argumentos)


LEITURAS_EM_PARTE: Mapping[str, Callable[[tuple[Palavra, ...]], bool]] = {"branch": _branch_que_lista, "stash": _stash_que_lista, "remote": _remote_que_lista}
