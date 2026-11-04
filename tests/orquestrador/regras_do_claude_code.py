"""Como o Claude Code casa uma regra `Bash(prefixo:*)` do `--disallowedTools` com um comando, para os testes da trava.

Pela documentação de permissões do Claude Code (code.claude.com/docs/en/permissions):
- `Bash(git branch:*)` é o mesmo que `Bash(git branch *)`: casa `git branch`
  sozinho e `git branch <qualquer coisa>`; o espaço antes do `*` conta
  (`git branchx` não casa);
- o comando é quebrado em subcomandos nos separadores `&&`, `||`, `;`, `|`,
  `|&`, `&` e quebra de linha, e a regra de negar vale para qualquer um deles,
  inclusive dentro de subshell, de substituição de comando e de corpo de
  `for`/`if`;
- antes de casar, saem da frente os embrulhos `timeout`, `time`, `nice`,
  `nohup`, `stdbuf`, `command` (não `command -v`), `builtin`, `noglob` e o
  `xargs` sem opção; e a regra de negar passa por cima de qualquer
  atribuição `NOME=valor` na frente;
- não casa o mesmo programa por outro caminho (`/usr/bin/git`, `sh -c '...'`,
  `git 'push'`).
Esta leitura erra para o lado de casar mais: tira as aspas (o Claude Code
compara o texto como foi escrito), junta as palavras com um espaço e não
distingue caixa. Um comando que ela não casa, o Claude Code também não casa.
"""

from graphow.orquestrador.leitura_do_shell import PALAVRAS_RESERVADAS, ComandoSimples, ler_shell

PREFIXO_DA_REGRA: str = "Bash("
SUFIXO_DA_REGRA: str = ":*)"
EMBRULHOS_SEM_ARGUMENTO: frozenset[str] = frozenset({"nohup", "builtin", "noglob"})
# Os embrulhos com opções na frente do programa, e as opções deles que levam valor.
OPCOES_COM_VALOR: dict[str, frozenset[str]] = {
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
    "time": frozenset({"-f", "--format", "-o", "--output"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "stdbuf": frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}),
}


def prefixos(regras: tuple[str, ...]) -> tuple[str, ...]:
    """O prefixo de cada regra `Bash(prefixo:*)`."""
    assert all(regra.startswith(PREFIXO_DA_REGRA) and regra.endswith(SUFIXO_DA_REGRA) for regra in regras), regras
    return tuple(regra[len(PREFIXO_DA_REGRA):-len(SUFIXO_DA_REGRA)] for regra in regras)


def regras_que_casam(comando: str, regras: tuple[str, ...]) -> list[str]:
    """As regras `Bash(prefixo:*)` que o Claude Code aplicaria ao comando (alguma casa com um subcomando dele)."""
    subcomandos = subcomandos_comparados(comando)
    return [regra for regra, prefixo in zip(regras, prefixos(regras), strict=True)
            if any(_casa(subcomando, prefixo.lower()) for subcomando in subcomandos)]


def subcomandos_comparados(comando: str) -> list[str]:
    """O texto de cada subcomando, sem atribuições nem embrulhos na frente, como a regra o compara."""
    leitura = ler_shell(comando)
    textos = [_texto(simples) for simples in leitura.comandos]
    for interno in leitura.substituicoes:
        textos += subcomandos_comparados(interno)
    return [texto for texto in textos if texto]


def _casa(subcomando: str, prefixo: str) -> bool:
    """`prefixo:*` casa o subcomando igual ao prefixo ou que começa por ele seguido de espaço."""
    return subcomando == prefixo or subcomando.startswith(prefixo + " ")


def _texto(simples: ComandoSimples) -> str:
    """As palavras do comando simples depois de tirar da frente as atribuições, as palavras reservadas e os embrulhos."""
    inicio = 0
    while inicio < len(simples.palavras) and (simples.palavras[inicio].atribuicao or simples.palavras[inicio].texto in PALAVRAS_RESERVADAS):
        inicio += 1
    palavras = [palavra.texto for palavra in simples.palavras[inicio:]]
    anterior: list[str] = []
    while palavras != anterior:
        anterior, palavras = palavras, _sem_embrulho(palavras)
    return " ".join(palavras).lower()


def _sem_embrulho(palavras: list[str]) -> list[str]:
    """As palavras sem o embrulho da frente (e as opções dele); as mesmas quando não há embrulho."""
    if not palavras:
        return palavras
    nome, resto = palavras[0], palavras[1:]
    if nome in EMBRULHOS_SEM_ARGUMENTO or (nome == "command" and resto[:1] not in (["-v"], ["-V"])):
        return resto
    if nome == "xargs":
        return resto if resto and not resto[0].startswith("-") else palavras
    if nome not in OPCOES_COM_VALOR:
        return palavras
    while resto and resto[0].startswith("-"):
        resto = resto[2:] if resto[0] in OPCOES_COM_VALOR[nome] else resto[1:]
    return resto[1:] if nome == "timeout" else resto
