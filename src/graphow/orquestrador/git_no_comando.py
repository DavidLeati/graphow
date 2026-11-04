"""A decisão da trava do git sobre um comando Bash do agente: só as leituras do git passam.

É função pura sobre o texto do comando (orquestrador/leitura_do_shell.py o
quebra em comandos simples). Cada invocação de git é achada onde estiver:
- depois de `&&`, `||`, `;`, `|`, num subshell, num `case`, numa substituição
  (`$(...)`, crase), dentro de `bash -c`/`sh -c`, de `cmd /c`, de `eval`,
  `alias`, `trap`, do heredoc que um shell lê e do `find -exec`;
- com prefixo de variável, chamada por `env`, `command`, `exec`, `xargs`,
  `timeout`, `coproc`, `wsl`, `npx -c`/`npm exec` e afins, por caminho
  absoluto, como `git.exe`, em maiúsculas ou como `git-<sub>`.
Quais argumentos do git passam é de orquestrador/leituras_do_git.py. O que
roda texto que a trava não lê é opaco: o shell que lê da entrada padrão, de
`/dev/stdin`, de `/dev/fd/*` ou de `<(...)`, o `source` deles, o PowerShell, o
`sed` com `e`, o `awk` com `system` ou `|`, o programa ou o argumento de
executor que só se sabe ao rodar (`"$PY"`, `timeout $T`). O comando com um
opaco é recusado se cita a palavra git como comando, aspas à parte. Recusa
também o texto que não fecha, o `bash -c` cujo texto só se sabe ao rodar, o
shell que lê de um pipe e o `hash -p` que dá outro nome a git, shell ou
executor. Script em arquivo e interpretador (`python -c`, `node -e`) ficam
fora: para eles valem as outras camadas da trava.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import chain
import re

from graphow.orquestrador.leitura_do_shell import PALAVRAS_RESERVADAS, ComandoIlegivel, ComandoSimples, Palavra, ler_shell
from graphow.orquestrador.leituras_do_git import LEITURAS_EM_TEXTO, motivo_do_git
from graphow.orquestrador.sed_e_awk import awk_roda_comando, sed_roda_comando

PROGRAMAS_DO_GIT: frozenset[str] = frozenset({"git"})
SHELLS: frozenset[str] = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash", "mksh", "fish"})
# Programas que rodam outro programa: o git ou o shell achado nos argumentos deles é invocação.
EXECUTORES: frozenset[str] = frozenset({
    "env", "exec", "nohup", "time", "nice", "timeout", "sudo", "doas", "xargs", "stdbuf", "ionice", "setsid", "watch",
    "strace", "ltrace", "flock", "chronic", "unbuffer", "winpty", "taskset", "chrt", "start", "builtin", "busybox",
    "parallel", "caffeinate", "coproc", "wsl",
})
# Os que entregam o argumento a um shell (`watch 'git commit'`, `flock arq -c 'git push'`).
EXECUTORES_PELO_SHELL: frozenset[str] = frozenset({"watch", "flock", "parallel"})
# Programas comuns: achados nos argumentos de um executor, são o programa que ele roda (`xargs grep -n git`).
PROGRAMAS_COMUNS: frozenset[str] = frozenset({
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "cat", "head", "tail", "wc", "sort", "uniq", "cut", "tr", "ls", "echo",
    "printf", "python", "python3", "py", "pytest", "node", "rm", "cp", "mv", "mkdir", "touch", "test", "diff", "jq",
    "make", "cargo", "go", "uv", "pip", "ruff", "mypy", "tee", "du", "stat", "file", "basename", "dirname", "realpath",
})
SUFIXOS_DE_EXECUTAVEL: tuple[str, ...] = (".exe", ".cmd", ".bat", ".com")
OPCOES_DO_SHELL_COM_VALOR: frozenset[str] = frozenset({"-o", "+o", "-O", "+O", "--rcfile", "--init-file"})
FIM_DO_EXEC_DO_FIND: frozenset[str] = frozenset({";", "+"})
# O arquivo que é a entrada padrão: o script lido dele é texto que a trava não vê.
DA_ENTRADA: re.Pattern[str] = re.compile(r"-|/dev/stdin|/dev/fd/\d+|/proc/[^/]+/fd/\d+")
LIMITE_DE_ANINHAMENTO: int = 8
# A palavra git como comando: não colada a letra, dígito, `_`, `.` ou `-` antes; depois, espaço, fim, `.exe` ou
# o que encerra palavra no shell (`$(echo git)`, `git;`, `git|`).
PALAVRA_GIT: re.Pattern[str] = re.compile(r"(?<![\w.-])git(?=[\s;&|()<>`}]|$|\.exe)")


@dataclass(frozen=True)
class Decisao:
    """Se o comando passa e, quando não passa, o motivo que vai ao agente.

    `opaco` é o texto que a trava não leu num trecho liberado; `decidir` o
    recusa quando o comando cita git.
    """

    permitido: bool
    motivo: str = ""
    opaco: str = ""


LIBERADO: Decisao = Decisao(True)


@dataclass(frozen=True)
class _Chamada:
    """Um programa a decidir: as palavras a partir do nome dele e o que veio na frente e na entrada."""

    palavras: tuple[Palavra, ...]
    atribuicoes: tuple[Palavra, ...] = ()
    entrada: str | None = None
    entrada_dinamica: bool = False
    profundidade: int = 0

    @property
    def argumentos(self) -> tuple[Palavra, ...]:
        """As palavras depois do nome do programa."""
        return self.palavras[1:]

    @property
    def programa(self) -> str:
        """O nome do programa chamado."""
        return nome_do_programa(self.palavras[0].texto)


def decidir(comando: str) -> Decisao:
    """Se o comando Bash passa pela trava do git: só as leituras do git passam, e o que não se lê é recusado."""
    decisao = _decidir_texto(comando, 0)
    if not decisao.permitido:
        return decisao
    if decisao.opaco and cita_git(comando):
        return _recusa(f"{decisao.opaco}, e o comando cita git")
    return LIBERADO


def cita_git(texto: str) -> bool:
    """O texto tem a palavra `git` como comando, sem contar aspas (`g"i"t` cita).

    Início de palavra (ou de nome depois de `/` ou `\\`), seguida de espaço,
    fim, `.exe` ou do que encerra palavra no shell: `git commit`,
    `/usr/bin/git`, `C:\\Git\\cmd\\git.exe`, `$(echo git)`. Pedaço
    de nome de arquivo não cita (`test_git_do_goal.py`, `test_digits.py`,
    `.gitignore`). A barra invertida conta tirada (`g\\it`) e como pasta.
    """
    sem_aspas = re.sub(r"[\"']", "", texto).lower()
    return any(PALAVRA_GIT.search(variante) for variante in (sem_aspas.replace("\\", ""), sem_aspas.replace("\\", "/")))


def nome_do_programa(texto: str) -> str:
    """O nome do programa sem a pasta, em minúsculas e sem `.exe` (o Windows não distingue caixa)."""
    base = re.split(r"[\\/]", texto)[-1].lower()
    return next((base[:-len(sufixo)] for sufixo in SUFIXOS_DE_EXECUTAVEL if base.endswith(sufixo)), base)


def _recusa(motivo: str) -> Decisao:
    """A recusa, com o lembrete de quem commita e do que passa."""
    return Decisao(False, f"{motivo}. O agente nao escreve no git: quem commita e o orquestrador. "
                          f"Passam so as leituras ({LEITURAS_EM_TEXTO}).")


def _opaco(motivo: str) -> Decisao:
    """O trecho liberado com texto que a trava não lê."""
    return Decisao(True, opaco=motivo)


def _juntar(decisoes: Iterable[Decisao]) -> Decisao:
    """A primeira recusa da sequência; sem recusa, o primeiro opaco, ou a liberação."""
    achada = LIBERADO
    for decisao in decisoes:
        if not decisao.permitido:
            return decisao
        achada = achada if achada.opaco else decisao
    return achada


def _decidir_texto(texto: str, profundidade: int) -> Decisao:
    """Lê o texto como comando e decide cada substituição e cada comando simples dele."""
    if profundidade > LIMITE_DE_ANINHAMENTO:
        return _recusa("comando aninhado demais para a trava ler")
    try:
        leitura = ler_shell(texto)
    except (ComandoIlegivel, RecursionError) as erro:
        return _recusa(f"a trava nao conseguiu ler o comando ({erro}) e recusa o que nao le")
    substituicoes = (_decidir_texto(interno, profundidade + 1) for interno in leitura.substituicoes)
    comandos = (_decidir_comando(comando, profundidade) for comando in leitura.comandos)
    return _juntar(chain(substituicoes, comandos))


def _decidir_comando(comando: ComandoSimples, profundidade: int) -> Decisao:
    """Um comando simples, com a entrada que o heredoc ou o here-string dão a ele."""
    chamada = _Chamada(comando.palavras, (), comando.entrada, comando.entrada_dinamica, profundidade)
    return _decidir_chamada(chamada)


def _decidir_chamada(chamada: _Chamada) -> Decisao:
    """Tira as palavras reservadas e as atribuições da frente e decide pelo programa que sobra."""
    inicio = 0
    while inicio < len(chamada.palavras) and _vai_na_frente(chamada.palavras[inicio]):
        inicio += 1
    na_frente, resto = chamada.palavras[:inicio], chamada.palavras[inicio:]
    chamada = replace(chamada, palavras=resto, atribuicoes=(*chamada.atribuicoes, *(p for p in na_frente if p.atribuicao)))
    if not resto:
        return LIBERADO
    if resto[0].dinamica:
        return _opaco(f"o nome do programa so se sabe ao rodar ({resto[0].texto or '$(...)'})")
    if chamada.programa.startswith("git-"):
        return _git(replace(chamada, palavras=(Palavra("git"), Palavra(chamada.programa[4:]), *resto[1:])))
    tratador = TRATADORES.get(chamada.programa)
    return tratador(chamada) if tratador else LIBERADO


def _vai_na_frente(palavra: Palavra) -> bool:
    """A atribuição `NOME=valor` e a palavra reservada (`if`, `then`, `!`, `{`...) vêm antes do programa."""
    return palavra.atribuicao or (palavra.texto in PALAVRAS_RESERVADAS and not palavra.dinamica)


def _git(chamada: _Chamada) -> Decisao:
    """A invocação do git: passa só a leitura, sem variável que troque repositório, configuração ou programa."""
    perigosas = [p.nome_atribuido for p in chamada.atribuicoes if _variavel_perigosa(p.nome_atribuido)]
    if perigosas:
        return _recusa(f"git com {perigosas[0]}=... na frente: a variavel troca repositorio, configuracao ou programa")
    motivo = motivo_do_git(chamada.argumentos)
    return _recusa(motivo) if motivo else LIBERADO


def _variavel_perigosa(nome: str) -> bool:
    """`GIT_*` (repositório, configuração, pager, editor) e `PATH` (qual git roda)."""
    return nome.upper().startswith("GIT_") or nome.upper() == "PATH"


def _da_entrada(palavra: Palavra) -> bool:
    """O script que vem da entrada padrão, de `/dev/fd/*` ou que só se sabe ao rodar (`<(...)`, `$F`)."""
    return palavra.dinamica or bool(DA_ENTRADA.fullmatch(palavra.texto))


def _shell(chamada: _Chamada) -> Decisao:
    """`bash -c "..."` lê o texto; `bash arquivo` fica fora; o script da entrada é opaco; o heredoc é lido."""
    argumentos, indice, letras = chamada.argumentos, 0, ""
    while indice < len(argumentos) and argumentos[indice].texto[:1] in ("-", "+"):
        opcao = argumentos[indice].texto
        letras += "" if opcao.startswith("--") else opcao[1:]
        indice += 2 if opcao in OPCOES_DO_SHELL_COM_VALOR else 1
    if "c" in letras:
        return _texto_dado(argumentos[indice:indice + 1], chamada, "o shell -c")
    if indice < len(argumentos) and "s" not in letras:
        return _opaco("o shell le o script da entrada padrao ou de um <(...)") if _da_entrada(argumentos[indice]) else LIBERADO
    if chamada.entrada is None or chamada.entrada_dinamica:
        return _recusa("o shell le os comandos da entrada padrao, que a trava nao ve")
    return _decidir_texto(chamada.entrada, chamada.profundidade + 1)


def _source(chamada: _Chamada) -> Decisao:
    """`source arquivo` fica fora, como `bash arquivo`; o da entrada padrão ou de `<(...)` é opaco."""
    primeiro = chamada.argumentos[:1]
    if not primeiro:
        return _recusa("source sem arquivo")
    return _opaco("o source le da entrada padrao ou de um <(...)") if _da_entrada(primeiro[0]) else LIBERADO


def _texto_dado(palavras: tuple[Palavra, ...], chamada: _Chamada, quem: str) -> Decisao:
    """As palavras juntas como um comando a ler; sem elas, ou com valor que só se sabe ao rodar, a recusa."""
    if not palavras:
        return _recusa(f"{quem} sem comando")
    if any(palavra.dinamica for palavra in palavras):
        return _recusa(f"o comando de {quem} so se sabe ao rodar")
    return _decidir_texto(" ".join(palavra.texto for palavra in palavras), chamada.profundidade + 1)


def _cmd(chamada: _Chamada) -> Decisao:
    """`cmd /c ...`: o que vem depois das opções é lido como comando."""
    argumentos = chamada.argumentos
    inicio = next((i for i, p in enumerate(argumentos) if p.texto[:1] not in ("-", "/")), len(argumentos))
    resto = argumentos[inicio:]
    if any(caractere in p.texto for p in resto for caractere in "^%"):
        return _recusa("cmd com ^ ou %: a trava nao le o que o cmd expande")
    if not resto:
        return LIBERADO if chamada.entrada is None else _recusa("o shell le os comandos da entrada padrao")
    return _texto_dado(resto, chamada, "cmd")


def _powershell(chamada: _Chamada) -> Decisao:
    """O texto do PowerShell não se lê como Bash (`iex`, `&`, `Start-Process`): é opaco; o codificado, recusado."""
    if any(_codificado(p.texto) for p in chamada.argumentos if p.texto[:1] in ("-", "/")):
        return _recusa("powershell -EncodedCommand: a trava nao le o comando codificado")
    return _opaco("o comando do PowerShell, que a trava nao le")


def _codificado(opcao: str) -> bool:
    """`-EncodedCommand` do PowerShell, abreviado ou não (`-e`, `-ec`, `-enc`...), com `-` ou `/`."""
    minusculo = "-" + opcao.lower()[1:]
    return minusculo == "-ec" or (len(minusculo) > 1 and "-encodedcommand".startswith(minusculo))


def _executor(chamada: _Chamada) -> Decisao:
    """O programa que roda outro: o programa achado nos argumentos é decidido dali em diante, e a varredura para."""
    decisoes: list[Decisao] = []
    for indice in range(len(chamada.argumentos)):
        decisao, achou_o_programa = _argumento_do_executor(chamada, indice)
        decisoes.append(decisao)
        if achou_o_programa or not decisao.permitido:
            break
    return _juntar(decisoes)


def _argumento_do_executor(chamada: _Chamada, indice: int) -> tuple[Decisao, bool]:
    """A decisão de um argumento do executor e se ele é o programa que o executor roda."""
    argumentos = chamada.argumentos
    palavra = argumentos[indice]
    if palavra.atribuicao:
        return LIBERADO, False
    if palavra.dinamica:
        return _opaco(f"{chamada.programa} com argumento que so se sabe ao rodar"), False
    nome = nome_do_programa(palavra.texto)
    if nome in PROGRAMAS_COMUNS or nome in TRATADORES or nome.startswith("git-"):
        antes = tuple(p for p in argumentos[:indice] if p.atribuicao)
        return _decidir_chamada(replace(chamada, palavras=argumentos[indice:], atribuicoes=(*chamada.atribuicoes, *antes))), True
    texto = _texto_que_o_executor_roda(chamada, indice)
    return (LIBERADO if texto is None else _decidir_texto(texto, chamada.profundidade + 1)), False


def _texto_que_o_executor_roda(chamada: _Chamada, indice: int) -> str | None:
    """O argumento que o executor entrega inteiro a um shell: o de `env -S` e os de `watch`, `flock -c`, `parallel`.

    Os outros executores passam o argumento como argumento: o `-c "..."` de
    um `python` embrulhado por `timeout` não é comando de shell.
    """
    programa, argumentos = chamada.programa, chamada.argumentos
    texto, anterior = argumentos[indice].texto, argumentos[indice - 1].texto if indice else ""
    if programa == "env" and anterior in ("-S", "--split-string"):
        return texto
    if programa == "env" and texto.startswith(("-S", "--split-string=")):
        return re.sub(r"^(-S|--split-string=)", "", texto)
    if programa in EXECUTORES_PELO_SHELL and any(espaco in texto for espaco in " \t\n;&|"):
        return texto
    return None


def _npx(chamada: _Chamada) -> Decisao:
    """`npx -c 'texto'` (`--call`) roda o texto num shell; fora dele, o npx é executor."""
    argumentos = chamada.argumentos
    textos = [argumentos[i + 1:i + 2] for i, p in enumerate(argumentos) if p.texto in ("-c", "--call")]
    textos += [(replace(p, texto=p.texto.split("=", 1)[1]),) for p in argumentos if p.texto.startswith("--call=")]
    return _juntar(chain((_texto_dado(texto, chamada, "npx -c") for texto in textos), (_executor(chamada),)))


def _npm(chamada: _Chamada) -> Decisao:
    """`npm exec` e `npm x` (e os do pnpm e do yarn) rodam como o `npx`."""
    inicio = next((i for i, p in enumerate(chamada.argumentos) if p.texto in ("exec", "x", "dlx")), None)
    return LIBERADO if inicio is None else _npx(replace(chamada, palavras=chamada.argumentos[inicio:]))


def _hash(chamada: _Chamada) -> Decisao:
    """`hash -p caminho nome` dá ao programa outro nome: recusado quando ele é git, shell ou executor."""
    argumentos = chamada.argumentos
    alvos = [argumentos[i + 1] for i, p in enumerate(argumentos[:-1]) if p.texto == "-p"]
    if any(alvo.dinamica for alvo in alvos):
        return _opaco("hash -p de um programa que so se sabe ao rodar")
    decididos = [alvo.texto for alvo in alvos if nome_do_programa(alvo.texto) in TRATADORES or
                 nome_do_programa(alvo.texto).startswith("git-")]
    return _recusa(f"hash -p da outro nome a {decididos[0]}, que a trava decide pelo nome") if decididos else LIBERADO


def _sed(chamada: _Chamada) -> Decisao:
    """O sed com `e` (ou com script que só se sabe ao rodar) roda texto num shell: é opaco."""
    return _opaco("o sed com e roda o texto num shell") if sed_roda_comando(chamada.argumentos) else LIBERADO


def _awk(chamada: _Chamada) -> Decisao:
    """O awk com `system` ou `|` (ou com programa que só se sabe ao rodar) roda comando: é opaco."""
    return _opaco("o awk com system ou | roda comando") if awk_roda_comando(chamada.argumentos) else LIBERADO


def _command(chamada: _Chamada) -> Decisao:
    """`command -v git` só procura o programa; `command git ...` o roda."""
    primeiro = chamada.argumentos[:1]
    return LIBERADO if primeiro and primeiro[0].texto in ("-v", "-V") else _executor(chamada)


def _eval(chamada: _Chamada) -> Decisao:
    """`eval` junta os argumentos e roda como comando."""
    return _texto_dado(chamada.argumentos, chamada, "eval") if chamada.argumentos else LIBERADO


def _alias(chamada: _Chamada) -> Decisao:
    """`alias g='git commit'`: o valor de cada alias é lido como comando."""
    valores = (palavra.texto.split("=", 1)[1] for palavra in chamada.argumentos if "=" in palavra.texto)
    return _juntar(_decidir_texto(valor, chamada.profundidade + 1) for valor in valores)


def _trap(chamada: _Chamada) -> Decisao:
    """`trap 'comando' SINAL`: o comando é lido como comando."""
    primeiro = chamada.argumentos[:1]
    if not primeiro or primeiro[0].texto.startswith("-"):
        return LIBERADO
    return _texto_dado(primeiro, chamada, "trap")


def _find(chamada: _Chamada) -> Decisao:
    """`find ... -exec programa ... ;`: cada programa do `-exec` é decidido."""
    argumentos = chamada.argumentos
    inicios = [i + 1 for i, p in enumerate(argumentos) if p.texto in ("-exec", "-execdir", "-ok", "-okdir")]
    programas = (replace(chamada, palavras=_ate_o_fim_do_exec(argumentos[i:])) for i in inicios)
    return _juntar(_decidir_chamada(programa) for programa in programas)


def _ate_o_fim_do_exec(palavras: tuple[Palavra, ...]) -> tuple[Palavra, ...]:
    """As palavras do `-exec` até o `;` ou o `+` que o fecham."""
    fim = next((i for i, p in enumerate(palavras) if p.texto in FIM_DO_EXEC_DO_FIND), len(palavras))
    return palavras[:fim]


TRATADORES: Mapping[str, Callable[[_Chamada], Decisao]] = {
    **{programa: _git for programa in PROGRAMAS_DO_GIT},
    **{programa: _shell for programa in SHELLS},
    **{programa: _executor for programa in EXECUTORES},
    "cmd": _cmd, "powershell": _powershell, "pwsh": _powershell, "command": _command, "eval": _eval, "alias": _alias,
    "trap": _trap, "find": _find, "source": _source, ".": _source, "hash": _hash, "npx": _npx, "bunx": _npx, "pnpx": _npx,
    "npm": _npm, "pnpm": _npm, "yarn": _npm, "sed": _sed, "gsed": _sed, "awk": _awk, "gawk": _awk, "mawk": _awk,
    "nawk": _awk,
}
