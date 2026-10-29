"""O hook PreToolUse da trava do git: o Claude Code o chama antes de cada comando Bash da sessão de agente.

O Claude Code passa na entrada padrão o JSON do evento, com `tool_name` e
`tool_input.command`. O comando que a trava recusa (orquestrador/
git_no_comando.py) sai com código 2 e o motivo no stderr, que o agente lê
como o motivo da recusa. É a forma que a documentação do Claude Code dá como
bloqueio antes das regras de permissão, vale em `bypassPermissions` e não
depende de o Claude Code ler um JSON de saída. A entrada que não se lê
também sai com 2: a trava recusa o que não entende. A ferramenta que não é o
Bash passa, porque o hook só olha comando de shell.

A linha de comando do hook (orquestrador/trava_do_git.py) roda o Python com
`-I` e põe na frente do caminho de importação a pasta do pacote que o
orquestrador roda: nem a pasta do clone, que o agente escreve, nem o
PYTHONPATH escolhem que módulo responde.
"""

import json
import sys
from typing import BinaryIO

from graphow.orquestrador.git_no_comando import LIBERADO, Decisao, decidir

CODIGO_DE_RECUSA: int = 2
FERRAMENTA_DO_SHELL: str = "Bash"


def decisao_da_entrada(texto: str) -> Decisao:
    """A decisão sobre o evento do PreToolUse; a entrada que não se lê é recusada."""
    try:
        evento = json.loads(texto)
    except ValueError:
        return Decisao(False, "a entrada do hook nao e JSON; a trava recusa o que nao le")
    if not isinstance(evento, dict) or not isinstance(evento.get("tool_name"), str):
        return Decisao(False, "o evento do hook veio sem tool_name; a trava recusa o que nao le")
    if evento["tool_name"] != FERRAMENTA_DO_SHELL:
        return LIBERADO
    entrada = evento.get("tool_input")
    comando = entrada.get("command") if isinstance(entrada, dict) else None
    if not isinstance(comando, str):
        return Decisao(False, "o evento do Bash veio sem tool_input.command; a trava recusa o que nao le")
    try:
        return decidir(comando)
    except RecursionError:
        return Decisao(False, "comando aninhado demais para a trava ler")


def responder(entrada: BinaryIO | None = None, erro: BinaryIO | None = None) -> int:
    """Lê o evento da entrada padrão e devolve o código de saída: 0 passa, 2 recusa com o motivo no stderr."""
    bruto = (entrada or sys.stdin.buffer).read()
    decisao = decisao_da_entrada(bruto.decode("utf-8", errors="replace"))
    if decisao.permitido:
        return 0
    saida = erro or sys.stderr.buffer
    saida.write(f"graphow: {decisao.motivo}\n".encode("utf-8", errors="replace"))
    saida.flush()
    return CODIGO_DE_RECUSA


if __name__ == "__main__":
    raise SystemExit(responder())
