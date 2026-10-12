"""Os comandos que uma sessão rodou de fato, lidos do stream, contra os que ela declarou na saída.

O verificador devolve em `comandos` o que rodou, com o código e um trecho da
saída, mas isso é autodeclarado. O stream da sessão traz cada chamada da
ferramenta Bash (`tool_use` com `input.command`); o comando declarado tem de
aparecer numa delas, comparado com os espaços normalizados (o declarado pode
ser parte de uma chamada maior, como `cd x && <comando> | tail`). O que não
aparece reprova a saída, que volta à mesma sessão uma vez, como o JSON que não
confere com o schema.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path
import re

from graphow.sessoes.leitura_stream import eventos_do_stream
from graphow.sessoes.sessao_claude import ResultadoDeSessao

FERRAMENTA_DO_SHELL: str = "Bash"
PROMPT_DO_SHELL: re.Pattern[str] = re.compile(r"^\$\s+")


def comandos_bash(caminho: Path) -> tuple[str, ...]:
    """Os comandos de cada chamada da ferramenta Bash no stream, na ordem; vazio sem stream."""
    if not caminho.is_file():
        return ()
    with caminho.open(encoding="utf-8", errors="replace") as stream:
        comandos = [_comandos_do_evento(evento) for evento in eventos_do_stream(stream)]
    return tuple(comando for comando in comandos if comando)


def _comandos_do_evento(evento: object) -> str:
    """O comando da chamada Bash do evento `assistant`; vazio quando o evento não chama o Bash."""
    mensagem = evento.get("message") if isinstance(evento, dict) and evento.get("type") == "assistant" else None
    conteudo = mensagem.get("content") if isinstance(mensagem, dict) else None
    chamadas = [item for item in conteudo or [] if isinstance(item, dict) and item.get("type") == "tool_use"]
    comandos = [str((item.get("input") or {}).get("command", "")) for item in chamadas if item.get("name") == FERRAMENTA_DO_SHELL]
    return "\n".join(comando for comando in comandos if comando.strip())


def _normalizado(comando: str) -> str:
    """O comando sem o prompt do shell e com os espaços reduzidos a um."""
    return " ".join(PROMPT_DO_SHELL.sub("", comando.strip()).split())


def comandos_nao_rodados(declarados: Iterable[str], resultados: Sequence[ResultadoDeSessao]) -> tuple[str, ...]:
    """Os comandos declarados que não aparecem em chamada Bash nenhuma das invocações dadas."""
    rodados = [_normalizado(comando) for resultado in resultados for comando in comandos_bash(resultado.arquivo_stream)]
    return tuple(
        declarado for declarado in declarados
        if _normalizado(declarado) and not any(_normalizado(declarado) in rodado for rodado in rodados)
    )


def problema_dos_comandos(faltando: Sequence[str]) -> tuple[str, ...]:
    """O que volta à sessão quando ela declarou comando que não rodou."""
    if not faltando:
        return ()
    lista = "; ".join(f"`{comando}`" for comando in faltando)
    return (
        f"estes comandos declarados em 'comandos' nao aparecem nas chamadas Bash desta sessao: {lista}. "
        "Declare cada comando exatamente como o rodou, ou rode-o antes de declarar",
    )
