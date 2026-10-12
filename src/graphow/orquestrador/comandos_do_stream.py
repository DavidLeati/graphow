"""Os comandos que uma sessão rodou de fato, lidos do stream: o comando, o código de saída e um trecho do que imprimiu.

O verificador declarava em `comandos` o que tinha rodado, e o orquestrador
conferia cada um contra as chamadas Bash do stream. Na bancada, as quatro
retomadas do verificador da agenda (22% do custo dele) foram todas por isso:
ele abreviava o comando declarado com reticências. O desenho mudou: o
orquestrador deriva do próprio stream cada chamada da ferramenta Bash
(`tool_use` com `input.command`) e o resultado dela (`tool_result`: o código
vem do `Exit code N` do erro, e zero sem erro), e grava isso na verificação;
o verificador não declara mais comando nenhum. A conferência por declaração
segue aqui para quem ainda a use.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re

from graphow.sessoes.leitura_stream import eventos_do_stream
from graphow.sessoes.sessao_claude import ResultadoDeSessao

FERRAMENTA_DO_SHELL: str = "Bash"
PROMPT_DO_SHELL: re.Pattern[str] = re.compile(r"^\$\s+")
CODIGO_DE_SAIDA: re.Pattern[str] = re.compile(r"^Exit code (-?\d+)\s*")
LIMITE_DO_TRECHO_DA_CHAMADA: int = 600


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


@dataclass(frozen=True)
class ChamadaBash:
    """Uma chamada da ferramenta Bash, como o stream a mostra: o comando, o código de saída e o fim do que ela imprimiu."""

    comando: str
    codigo: int
    saida: str


def chamadas_bash(caminhos: Iterable[Path]) -> tuple[ChamadaBash, ...]:
    """Cada chamada Bash dos streams dados, na ordem, com o resultado que veio para ela."""
    chamadas: list[ChamadaBash] = []
    for caminho in caminhos:
        if caminho.is_file():
            with caminho.open(encoding="utf-8", errors="replace") as stream:
                chamadas += _chamadas_do_stream(list(eventos_do_stream(stream)))
    return tuple(chamadas)


def _chamadas_do_stream(eventos: Sequence[object]) -> list[ChamadaBash]:
    """As chamadas Bash de um stream, casadas com o `tool_result` de cada uma pelo id."""
    pedidas = [item for evento in eventos for item in _blocos(evento, "assistant", "tool_use") if item.get("name") == FERRAMENTA_DO_SHELL]
    resultados = {str(item.get("tool_use_id")): item for evento in eventos for item in _blocos(evento, "user", "tool_result")}
    return [_chamada(str((item.get("input") or {}).get("command", "")), resultados.get(str(item.get("id")))) for item in pedidas]


def _blocos(evento: object, tipo: str, bloco: str) -> list[dict]:
    """Os blocos do tipo dado no conteúdo da mensagem do evento."""
    mensagem = evento.get("message") if isinstance(evento, dict) and evento.get("type") == tipo else None
    conteudo = mensagem.get("content") if isinstance(mensagem, dict) else None
    return [item for item in conteudo or [] if isinstance(item, dict) and item.get("type") == bloco] if isinstance(conteudo, list) else []


def _chamada(comando: str, resultado: dict | None) -> ChamadaBash:
    """A chamada com o código de saída e o trecho do resultado; sem resultado, código -1."""
    if resultado is None:
        return ChamadaBash(comando, -1, "")
    conteudo = resultado.get("content")
    texto = conteudo if isinstance(conteudo, str) else " ".join(str(c.get("text", "")) for c in conteudo or [] if isinstance(c, dict))
    codigo = 0
    if resultado.get("is_error"):
        achado = CODIGO_DE_SAIDA.match(texto)
        codigo = int(achado.group(1)) if achado else 1
        texto = CODIGO_DE_SAIDA.sub("", texto, count=1)
    return ChamadaBash(comando, codigo, texto.replace("\r\n", "\n")[-LIMITE_DO_TRECHO_DA_CHAMADA:])


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
