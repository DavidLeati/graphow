"""O que o stream-json de uma sessão `claude -p` diz dela: quem é, o que respondeu e quanto custou.

O stream é uma linha JSON por evento. O `system/init` traz a sessão e o modelo;
o `result`, no fim, traz o texto final, o erro, o custo, os turnos, a duração e
o `modelUsage`, que soma os tokens da sessão e dos subagentes dela por modelo.
O `usage` do mesmo evento conta só a sessão principal, e por isso não serve de
total.

Dois cuidados que os logs do laboratório mostraram. Uma sessão retomada com
`--resume` herda o custo e o `modelUsage` da anterior: o `result` de cada
invocação traz o acumulado da sessão, não o da invocação. E a leitura é
defensiva: linha que não é JSON é ignorada, e o stream sem `result` (processo
morto, tempo esgotado) devolve leitura sem resultado, em vez de números
inventados.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
import json
from typing import Any

TIPO_RESULTADO: str = "result"
TIPO_SISTEMA: str = "system"
SUBTIPO_INICIO: str = "init"
CHAVES_DO_MODEL_USAGE: Mapping[str, str] = {
    "entrada": "inputTokens",
    "saida": "outputTokens",
    "cache_leitura": "cacheReadInputTokens",
    "cache_criacao": "cacheCreationInputTokens",
}


@dataclass(frozen=True)
class UsoDeTokens:
    """Tokens nas quatro categorias que o Claude Code conta; o total é a soma delas."""

    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_criacao: int = 0

    @property
    def total(self) -> int:
        """Entrada, saída e as duas de cache somadas: a medida de tokens da bancada."""
        return self.entrada + self.saida + self.cache_leitura + self.cache_criacao

    def somar(self, outro: "UsoDeTokens") -> "UsoDeTokens":
        """Categoria a categoria."""
        return UsoDeTokens(
            entrada=self.entrada + outro.entrada,
            saida=self.saida + outro.saida,
            cache_leitura=self.cache_leitura + outro.cache_leitura,
            cache_criacao=self.cache_criacao + outro.cache_criacao,
        )

    def em_dicionario(self) -> dict[str, int]:
        """As categorias e o total, para gravar em JSON."""
        return {
            "entrada": self.entrada,
            "saida": self.saida,
            "cache_leitura": self.cache_leitura,
            "cache_criacao": self.cache_criacao,
            "total": self.total,
        }


@dataclass(frozen=True)
class ResultadoDoStream:
    """Um evento `result`: o fim de uma invocação do `claude -p`."""

    session_id: str
    texto: str
    is_error: bool
    subtipo: str
    custo_usd: float
    turnos: int
    duracao_ms: int | None
    tokens_por_modelo: Mapping[str, UsoDeTokens] = field(default_factory=dict)

    @property
    def tokens(self) -> UsoDeTokens:
        """O `modelUsage` somado entre os modelos."""
        total = UsoDeTokens()
        for uso in self.tokens_por_modelo.values():
            total = total.somar(uso)
        return total


@dataclass(frozen=True)
class LeituraDoStream:
    """A sessão que o stream abriu e o último resultado dela, quando houve um."""

    session_id: str = ""
    modelo: str = ""
    resultado: ResultadoDoStream | None = None


def eventos_do_stream(linhas: Iterable[str]) -> Iterator[Mapping[str, Any]]:
    """Cada linha que é um objeto JSON; o resto (vazia, truncada, texto solto) fica de fora."""
    for linha in linhas:
        evento = _carregar(linha)
        if evento:
            yield evento


def ler_stream(linhas: Iterable[str]) -> LeituraDoStream:
    """A sessão do `system/init` e o último `result` do stream."""
    session_id, modelo, resultado = "", "", None
    for evento in eventos_do_stream(linhas):
        if _eh_inicio(evento):
            session_id = session_id or str(evento.get("session_id") or "")
            modelo = modelo or str(evento.get("model") or "")
        if evento.get("type") == TIPO_RESULTADO:
            resultado = ler_resultado(evento)
    return LeituraDoStream(session_id=session_id or (resultado.session_id if resultado else ""), modelo=modelo, resultado=resultado)


def ler_resultado(evento: Mapping[str, Any]) -> ResultadoDoStream:
    """Os campos de um evento `result` que a bancada usa, com o que faltar zerado."""
    return ResultadoDoStream(
        session_id=str(evento.get("session_id") or ""),
        texto=str(evento.get("result") or ""),
        is_error=bool(evento.get("is_error")),
        subtipo=str(evento.get("subtype") or ""),
        custo_usd=_numero(evento.get("total_cost_usd")),
        turnos=int(_numero(evento.get("num_turns"))),
        duracao_ms=_inteiro_ou_nada(evento.get("duration_ms")),
        tokens_por_modelo=_tokens_por_modelo(evento.get("modelUsage")),
    )


def _tokens_por_modelo(valor: object) -> dict[str, UsoDeTokens]:
    """O `modelUsage` de cada modelo nas quatro categorias."""
    if not isinstance(valor, dict):
        return {}
    return {
        str(modelo): UsoDeTokens(**{campo: int(_numero(uso.get(chave))) for campo, chave in CHAVES_DO_MODEL_USAGE.items()})
        for modelo, uso in valor.items()
        if isinstance(uso, dict)
    }


def _eh_inicio(evento: Mapping[str, Any]) -> bool:
    """O `system/init` que abre a invocação."""
    return evento.get("type") == TIPO_SISTEMA and evento.get("subtype") == SUBTIPO_INICIO


def _carregar(linha: str) -> Mapping[str, Any]:
    """Uma linha como objeto JSON; o que não é objeto vira vazio."""
    try:
        valor = json.loads(linha)
    except json.JSONDecodeError:
        return {}
    return valor if isinstance(valor, dict) else {}


def _numero(valor: object) -> float:
    """Número do evento; ausente, booleano ou texto contam zero."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return 0.0
    return float(valor)


def _inteiro_ou_nada(valor: object) -> int | None:
    """A duração relatada, quando o evento a traz."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return int(valor)
