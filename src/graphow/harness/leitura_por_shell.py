"""Os caminhos que um comando de shell lê, tirados do texto do comando por heurística conservadora.

A primeira linha de base mostrou executores com um caminho lido pelo Read e
57 saídas de ferramenta acima de 2.000 caracteres: eles leem pelo Bash (`cat`,
`sed -n`, `grep`) e pelo PowerShell (`Get-Content`). Sem isto, a medição de
leituras fora do alvo não via a maior parte das leituras.

O texto do comando é livre, e o falso positivo é pior que a omissão: um padrão
do grep contado como arquivo inventaria leitura fora do alvo. Por isso só se
reconhecem poucos leitores (`cat`, `head`, `tail`, `less`, `wc`, `sed`, `grep`,
`rg`, `Get-Content`, `gc`, `type`, `Select-String -Path`), só se colhe o token
que parece caminho (tem barra ou extensão), nunca flag, nunca o que tem curinga,
variável ou substituição, e nunca o que vem depois de um redirecionamento.
Pipes, `;`, `&&` e `||` separam comandos; no grep, no rg e no sed o primeiro
argumento posicional é o padrão ou o script, e argumento entre aspas não conta.
O `sed -i` edita e fica de fora. Comando que não se tokeniza não dá nada, e
do heredoc em diante (`<<`) nada se colhe: o corpo é texto, não comando.
"""

from collections.abc import Iterator
import re
import shlex

LEITORES_SIMPLES: frozenset[str] = frozenset({"cat", "head", "tail", "less", "wc", "get-content", "gc", "type"})
# No grep, no rg e no sed o primeiro posicional é padrão ou script, não arquivo.
LEITORES_COM_PADRAO: frozenset[str] = frozenset({"grep", "rg", "sed"})
LEITOR_POR_PARAMETRO: str = "select-string"
PARAMETROS_DE_CAMINHO: frozenset[str] = frozenset({"-path", "-literalpath"})
# Flags cujo valor é o padrão: com elas, todo posicional é arquivo.
FLAGS_DE_PADRAO: frozenset[str] = frozenset({"-e", "-f", "--regexp", "--file", "--expression"})
FLAGS_DE_EDICAO: frozenset[str] = frozenset({"-i", "--in-place"})
SEPARADORES: frozenset[str] = frozenset({";", "|", "||", "&&", "&", "(", ")"})
ASPAS: str = "\"'"
CARACTERES_DE_REDIRECIONAMENTO: str = "<>&"
# O corpo do heredoc é texto, não comando; dali em diante nada se colhe.
MARCA_DE_HEREDOC: str = "<<"
PARECE_CAMINHO = re.compile(r"[/\\]|^[^.\s][^\s]*\.[A-Za-z0-9]{1,8}$")
NAO_E_CAMINHO = re.compile(r"[*?$`=<>{}]|^-|^\d+$|^/dev/|^[a-z]+://", re.IGNORECASE)


def caminhos_lidos_no_comando(comando: str) -> tuple[str, ...]:
    """Os caminhos que os leitores reconhecidos do comando leem, na ordem; vazio na dúvida."""
    caminhos: list[str] = []
    for linha in comando.split(MARCA_DE_HEREDOC)[0].splitlines():
        caminhos.extend(caminho for segmento in _segmentos(linha) for caminho in _caminhos_do_segmento(segmento))
    return tuple(caminhos)


def _segmentos(linha: str) -> Iterator[list[str]]:
    """Os comandos simples da linha, cada um cortado no primeiro redirecionamento."""
    lexico = shlex.shlex(linha, posix=False, punctuation_chars=True)
    lexico.whitespace_split = True
    try:
        tokens = list(lexico)
    except ValueError:
        return
    atual: list[str] = []
    for token in [*tokens, ";"]:
        if token in SEPARADORES:
            yield _ate_o_redirecionamento(atual)
            atual = []
        else:
            atual.append(token)


def _ate_o_redirecionamento(tokens: list[str]) -> list[str]:
    """Os tokens antes do primeiro `>`, `>>`, `2>` ou `<`: o que vem depois é destino, não leitura."""
    corte = next((indice for indice, token in enumerate(tokens) if _eh_redirecionamento(token)), len(tokens))
    fim = corte - 1 if corte < len(tokens) and corte > 0 and tokens[corte - 1].isdigit() else corte
    return tokens[:fim]


def _eh_redirecionamento(token: str) -> bool:
    """O token só de pontuação com `<` ou `>`: `>`, `>>`, `>&`, `&>`, `<`."""
    return set(token) <= set(CARACTERES_DE_REDIRECIONAMENTO) and bool(set(token) & set("<>"))


def _caminhos_do_segmento(tokens: list[str]) -> tuple[str, ...]:
    """Os caminhos lidos por um comando simples, conforme o leitor."""
    if not tokens:
        return ()
    leitor = re.split(r"[/\\]", tokens[0])[-1].lower()
    argumentos = tokens[1:]
    if leitor in LEITORES_SIMPLES:
        return _caminhos(_sem_aspas(token) for token in argumentos)
    if leitor == LEITOR_POR_PARAMETRO:
        return _caminhos(_sem_aspas(valor) for parametro, valor in zip(argumentos, argumentos[1:]) if parametro.lower() in PARAMETROS_DE_CAMINHO)
    if leitor in LEITORES_COM_PADRAO and not FLAGS_DE_EDICAO & {argumento.lower() for argumento in argumentos}:
        return _caminhos(_arquivos_depois_do_padrao(argumentos))
    return ()


def _arquivos_depois_do_padrao(argumentos: list[str]) -> list[str]:
    """Os posicionais depois do padrão; sem flag de padrão, o primeiro posicional é o padrão."""
    posicionais = [argumento for argumento in argumentos if not argumento.startswith("-")]
    tem_flag_de_padrao = any(argumento.split("=")[0] in FLAGS_DE_PADRAO for argumento in argumentos)
    arquivos = posicionais if tem_flag_de_padrao else posicionais[1:]
    return [arquivo for arquivo in arquivos if arquivo[0] not in ASPAS]


def _caminhos(tokens: Iterator[str] | list[str]) -> tuple[str, ...]:
    """Os tokens que parecem caminho e não têm nada que os desminta."""
    return tuple(token for token in tokens if token and PARECE_CAMINHO.search(token) and not NAO_E_CAMINHO.search(token))


def _sem_aspas(token: str) -> str:
    """O token sem as aspas que o envolvem; o que não está entre aspas fica como está."""
    if len(token) >= 2 and token[0] in ASPAS and token[-1] == token[0]:
        return token[1:-1]
    return token
