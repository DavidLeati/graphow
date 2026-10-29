"""A decisão da trava do git sobre um comando Bash do agente: só as leituras do git passam.

É função pura sobre o texto do comando (orquestrador/leitura_do_shell.py o
quebra em comandos simples). Cada invocação de git é achada onde estiver:
- depois de `&&`, `||`, `;`, `|`, num subshell, numa substituição (`$(...)`,
  crase), dentro de `bash -c`/`sh -c`, de `cmd /c`, de `powershell -Command`,
  de `eval`, `alias`, `trap`, do heredoc que um shell lê e do `find -exec`;
- com prefixo de variável, chamada por `env`, `command`, `exec`, `xargs`,
  `timeout` e afins, por caminho absoluto, como `git.exe` ou em maiúsculas.
Passam só `status`, `diff`, `log`, `show`, `blame`, `ls-files` e `rev-parse`,
com as opções delas, e com as opções globais que não trocam configuração nem
programa (`-C`, `--no-pager`...). `git -c`, `--config-env` e `--exec-path`
são recusados, como a variável `GIT_*` ou `PATH` na frente do git: com eles,
até uma leitura roda o programa que o agente escolher. Recusa também o que
não lê: texto que não fecha, programa cujo nome só se sabe ao rodar, shell
que lê comandos da entrada padrão. Script em arquivo e interpretador (`python
-c`, `node -e`) ficam fora: para eles valem as outras camadas da trava.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import chain
import re

from graphow.orquestrador.leitura_do_shell import ComandoIlegivel, ComandoSimples, Palavra, ler_shell

LEITURAS_DO_GIT: tuple[str, ...] = ("status", "diff", "log", "show", "blame", "ls-files", "rev-parse")
OPCOES_GLOBAIS_COM_VALOR: frozenset[str] = frozenset({"-C", "--git-dir", "--work-tree", "--namespace", "--super-prefix"})
OPCOES_GLOBAIS_SEM_VALOR: frozenset[str] = frozenset({
    "--no-pager", "-p", "--paginate", "-P", "--bare", "--no-replace-objects", "--no-lazy-fetch", "--literal-pathspecs",
    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks", "--no-advice",
})
PROGRAMAS_DO_GIT: frozenset[str] = frozenset({"git"})
SHELLS: frozenset[str] = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash", "mksh", "fish"})
SHELLS_DO_WINDOWS: frozenset[str] = frozenset({"cmd", "powershell", "pwsh"})
# Programas que rodam outro programa: o git ou o shell achado nos argumentos deles é invocação.
EXECUTORES: frozenset[str] = frozenset({
    "env", "exec", "nohup", "time", "nice", "timeout", "sudo", "doas", "xargs", "stdbuf", "ionice", "setsid", "watch",
    "strace", "ltrace", "flock", "chronic", "unbuffer", "winpty", "taskset", "chrt", "start", "builtin", "busybox",
    "parallel", "caffeinate",
})
# Os que entregam o argumento a um shell (`watch 'git commit'`, `flock arq -c 'git push'`).
EXECUTORES_PELO_SHELL: frozenset[str] = frozenset({"watch", "flock", "parallel"})
PALAVRAS_RESERVADAS: frozenset[str] = frozenset({"!", "{", "}", "if", "then", "else", "elif", "fi", "do", "done",
                                                 "while", "until", "function"})
SUFIXOS_DE_EXECUTAVEL: tuple[str, ...] = (".exe", ".cmd", ".bat", ".com")
OPCOES_DO_SHELL_COM_VALOR: frozenset[str] = frozenset({"-o", "+o", "-O", "+O", "--rcfile", "--init-file"})
FIM_DO_EXEC_DO_FIND: frozenset[str] = frozenset({";", "+"})
LIMITE_DE_ANINHAMENTO: int = 8
LEITURAS_EM_TEXTO: str = ", ".join(LEITURAS_DO_GIT)


@dataclass(frozen=True)
class Decisao:
    """Se o comando passa e, quando não passa, o motivo que vai ao agente."""

    permitido: bool
    motivo: str = ""


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


def decidir(comando: str) -> Decisao:
    """Se o comando Bash passa pela trava do git: só as leituras do git passam, e o que não se lê é recusado."""
    return _decidir_texto(comando, 0)


def nome_do_programa(texto: str) -> str:
    """O nome do programa sem a pasta, em minúsculas e sem `.exe` (o Windows não distingue caixa)."""
    base = re.split(r"[\\/]", texto)[-1].lower()
    return next((base[:-len(sufixo)] for sufixo in SUFIXOS_DE_EXECUTAVEL if base.endswith(sufixo)), base)


def _recusa(motivo: str) -> Decisao:
    """A recusa, com o lembrete de quem commita e do que passa."""
    return Decisao(False, f"{motivo}. O agente nao escreve no git: quem commita e o orquestrador. "
                          f"Passam so as leituras ({LEITURAS_EM_TEXTO}).")


def _primeira_recusa(decisoes: Iterable[Decisao]) -> Decisao:
    """A primeira recusa da sequência, ou a liberação quando nenhuma recusa."""
    return next((decisao for decisao in decisoes if not decisao.permitido), LIBERADO)


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
    return _primeira_recusa(chain(substituicoes, comandos))


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
        return _recusa(f"o nome do programa so se sabe ao rodar ({resto[0].texto or '$(...)'})")
    tratador = TRATADORES.get(nome_do_programa(resto[0].texto))
    return tratador(chamada) if tratador else LIBERADO


def _vai_na_frente(palavra: Palavra) -> bool:
    """A atribuição `NOME=valor` e a palavra reservada (`if`, `then`, `!`, `{`...) vêm antes do programa."""
    return palavra.atribuicao or (palavra.texto in PALAVRAS_RESERVADAS and not palavra.dinamica)


def _git(chamada: _Chamada) -> Decisao:
    """A invocação do git: passa só a leitura, sem variável que troque repositório, configuração ou programa."""
    perigosas = [p.nome_atribuido for p in chamada.atribuicoes if _variavel_perigosa(p.nome_atribuido)]
    if perigosas:
        return _recusa(f"git com {perigosas[0]}=... na frente: a variavel troca repositorio, configuracao ou programa")
    subcomando, motivo = _subcomando_do_git(chamada.argumentos)
    if subcomando is None:
        return _recusa(motivo)
    if subcomando.dinamica:
        return _recusa("o subcomando do git so se sabe ao rodar")
    if subcomando.texto in LEITURAS_DO_GIT:
        return LIBERADO
    return _recusa(f"git {subcomando.texto} recusado")


def _variavel_perigosa(nome: str) -> bool:
    """`GIT_*` (repositório, configuração, pager, editor) e `PATH` (qual git roda)."""
    return nome.upper().startswith("GIT_") or nome.upper() == "PATH"


def _subcomando_do_git(argumentos: tuple[Palavra, ...]) -> tuple[Palavra | None, str]:
    """O subcomando depois das opções globais; sem ele, o motivo da recusa."""
    indice = 0
    while indice < len(argumentos):
        palavra = argumentos[indice]
        opcao = palavra.texto.split("=", 1)[0]
        if palavra.dinamica:
            return None, "opcao do git que so se sabe ao rodar"
        if not palavra.texto.startswith("-"):
            return palavra, ""
        if palavra.texto.startswith("-c") or opcao in ("--config-env", "--exec-path"):
            return None, f"git {palavra.texto}: a opcao troca a configuracao ou o programa do git"
        if opcao not in OPCOES_GLOBAIS_COM_VALOR | OPCOES_GLOBAIS_SEM_VALOR:
            return None, f"git {palavra.texto}: opcao que a trava nao libera"
        indice += 2 if palavra.texto in OPCOES_GLOBAIS_COM_VALOR else 1
    return None, "git sem subcomando"


def _shell(chamada: _Chamada) -> Decisao:
    """`bash -c "..."` lê o texto; `bash arquivo` fica fora; o shell que lê a entrada padrão só com heredoc."""
    argumentos, indice, com_c = chamada.argumentos, 0, False
    while indice < len(argumentos) and argumentos[indice].texto[:1] in ("-", "+"):
        opcao = argumentos[indice].texto
        com_c = com_c or (not opcao.startswith("--") and "c" in opcao[1:])
        indice += 2 if opcao in OPCOES_DO_SHELL_COM_VALOR else 1
    if com_c:
        return _texto_dado(argumentos[indice:indice + 1], chamada, "o shell -c")
    if indice < len(argumentos):
        return LIBERADO
    if chamada.entrada is None or chamada.entrada_dinamica:
        return _recusa("o shell le os comandos da entrada padrao, que a trava nao ve")
    return _decidir_texto(chamada.entrada, chamada.profundidade + 1)


def _texto_dado(palavras: tuple[Palavra, ...], chamada: _Chamada, quem: str) -> Decisao:
    """As palavras juntas como um comando a ler; sem elas, ou com valor que só se sabe ao rodar, a recusa."""
    if not palavras:
        return _recusa(f"{quem} sem comando")
    if any(palavra.dinamica for palavra in palavras):
        return _recusa(f"o comando de {quem} so se sabe ao rodar")
    return _decidir_texto(" ".join(palavra.texto for palavra in palavras), chamada.profundidade + 1)


def _shell_do_windows(chamada: _Chamada) -> Decisao:
    """`cmd /c ...`, `powershell -Command ...`: o que vem depois das opções é lido como comando."""
    argumentos = chamada.argumentos
    inicio = next((i for i, p in enumerate(argumentos) if p.texto[:1] not in ("-", "/")), len(argumentos))
    if any(_codificado(p.texto) for p in argumentos[:inicio]):
        return _recusa("powershell -EncodedCommand: a trava nao le o comando codificado")
    resto = argumentos[inicio:]
    if any(caractere in p.texto for p in resto for caractere in "^%"):
        return _recusa("cmd com ^ ou %: a trava nao le o que o cmd expande")
    if not resto:
        return LIBERADO if chamada.entrada is None else _recusa("o shell le os comandos da entrada padrao")
    return _texto_dado(resto, chamada, nome_do_programa(chamada.palavras[0].texto))


def _codificado(opcao: str) -> bool:
    """`-EncodedCommand` do PowerShell, abreviado ou não (`-e`, `-ec`, `-enc`...)."""
    minusculo = opcao.lower()
    return minusculo == "-ec" or (len(minusculo) > 1 and "-encodedcommand".startswith(minusculo))


def _executor(chamada: _Chamada) -> Decisao:
    """O programa que roda outro: o git ou o shell achado nos argumentos é decidido dali em diante."""
    argumentos = chamada.argumentos
    for indice in range(len(argumentos)):
        decisao = _argumento_do_executor(chamada, indice)
        if decisao is not None:
            return decisao
    return LIBERADO


def _argumento_do_executor(chamada: _Chamada, indice: int) -> Decisao | None:
    """A decisão que um argumento do executor dá; None quando a varredura segue."""
    argumentos = chamada.argumentos
    palavra = argumentos[indice]
    if palavra.atribuicao:
        return None
    if palavra.dinamica:
        return _recusa(f"{nome_do_programa(chamada.palavras[0].texto)} com argumento que so se sabe ao rodar")
    if nome_do_programa(palavra.texto) in PROGRAMAS_DO_GIT | SHELLS | SHELLS_DO_WINDOWS:
        antes = tuple(p for p in argumentos[:indice] if p.atribuicao)
        return _decidir_chamada(replace(chamada, palavras=argumentos[indice:], atribuicoes=(*chamada.atribuicoes, *antes)))
    texto = _texto_que_o_executor_roda(chamada, indice)
    if texto is None:
        return None
    decisao = _decidir_texto(texto, chamada.profundidade + 1)
    return None if decisao.permitido else decisao


def _texto_que_o_executor_roda(chamada: _Chamada, indice: int) -> str | None:
    """O argumento que o executor entrega inteiro a um shell: o de `env -S` e os de `watch`, `flock -c`, `parallel`.

    Os outros executores passam o argumento como argumento: o `-c "..."` de
    um `python` embrulhado por `timeout` não é comando de shell.
    """
    programa, argumentos = nome_do_programa(chamada.palavras[0].texto), chamada.argumentos
    texto, anterior = argumentos[indice].texto, argumentos[indice - 1].texto if indice else ""
    if programa == "env" and anterior in ("-S", "--split-string"):
        return texto
    if programa == "env" and texto.startswith(("-S", "--split-string=")):
        return re.sub(r"^(-S|--split-string=)", "", texto)
    if programa in EXECUTORES_PELO_SHELL and any(espaco in texto for espaco in " \t\n;&|"):
        return texto
    return None


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
    return _primeira_recusa(_decidir_texto(valor, chamada.profundidade + 1) for valor in valores)


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
    return _primeira_recusa(_decidir_chamada(programa) for programa in programas)


def _ate_o_fim_do_exec(palavras: tuple[Palavra, ...]) -> tuple[Palavra, ...]:
    """As palavras do `-exec` até o `;` ou o `+` que o fecham."""
    fim = next((i for i, p in enumerate(palavras) if p.texto in FIM_DO_EXEC_DO_FIND), len(palavras))
    return palavras[:fim]


TRATADORES: Mapping[str, Callable[[_Chamada], Decisao]] = {
    **{programa: _git for programa in PROGRAMAS_DO_GIT},
    **{programa: _shell for programa in SHELLS},
    **{programa: _shell_do_windows for programa in SHELLS_DO_WINDOWS},
    **{programa: _executor for programa in EXECUTORES},
    "command": _command,
    "eval": _eval,
    "alias": _alias,
    "trap": _trap,
    "find": _find,
}
