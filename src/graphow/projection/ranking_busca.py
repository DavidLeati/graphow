"""Ordenação e corte dos resultados de busca textual no grafo.

A busca já devolvia linhas esqueléticas — id, tipo, rótulo e posição no log, sem
descrição nem histórico. O que faltava era limite e ordem: `buscar("a")` devolvia
os 191 nós do grafo em 8.137 tokens, e `buscar("dados")` devolvia 34 em 1.447.

Ordem e corte andam juntos de propósito. A ordem anterior era a de inserção do
dicionário de nós, que não é ordem nenhuma: cortar em cinco ali devolveria cinco
resultados arbitrários, e o agente perderia o que procurava sem ficar sabendo —
pior do que a lista inteira cara. Por isso o corte só existe depois do ranking, e
a resposta sempre diz quantos foram encontrados no total.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, StatusTask, TipoNo

LIMITE_PADRAO_DE_RESULTADOS: int = 5
LIMITE_MAXIMO_DE_RESULTADOS: int = 50

# Um nó nestes estados raramente é o que a busca procura, mas continua achável:
# ele desce no ranking, nunca é filtrado. Decisão "adotada" fica de fora da lista
# de propósito — uma decisão em vigor é o resultado mais relevante que existe.
STATUS_ENCERRADOS: frozenset[str] = frozenset(
    {
        StatusTask.CONCLUIDO.value,
        StatusQuestion.RESPONDIDA.value,
        StatusQuestion.DESCARTADA.value,
    }
)

CASOU_NO_ROTULO: str = "rotulo"
CASOU_NAS_PROPRIEDADES: str = "propriedades"

# Palavras que aparecem em qualquer título e não dizem de que ele trata.
PALAVRAS_VAZIAS: frozenset[str] = frozenset(
    {
        "para", "pelo", "pela", "pelos", "pelas", "como", "mais", "menos", "sobre", "entre",
        "este", "esta", "isto", "esse", "essa", "isso", "aquele", "aquela", "seus", "suas",
        "onde", "qual", "quais", "quando", "porque", "ainda", "mesmo", "cada", "toda", "todo",
        "todos", "todas", "umas", "sem", "com", "dos", "das", "nos", "nas", "por", "que",
    }
)
TAMANHO_MINIMO_DE_PALAVRA: int = 4

_FORMA_PALAVRA_INTEIRA: int = 0
_FORMA_PREFIXO: int = 1
_FORMA_SUBSTRING: int = 2
_FORMA_SEM_CASAMENTO: int = 3


@dataclass(frozen=True)
class CriterioBusca:
    """Parâmetros imutáveis de uma consulta textual ao grafo."""

    termo: str
    tipos: tuple[TipoNo, ...] = field(default_factory=tuple)
    limite: int = LIMITE_PADRAO_DE_RESULTADOS

    @property
    def termo_normalizado(self) -> str:
        """Termo em caixa baixa e sem espaços nas pontas, como o índice compara."""
        return self.termo.strip().lower()

    @property
    def limite_efetivo(self) -> int:
        """Limite saneado: ao menos um resultado, no máximo o teto da ferramenta."""
        return max(1, min(self.limite, LIMITE_MAXIMO_DE_RESULTADOS))


@dataclass(frozen=True)
class ResultadoRanqueado:
    """Um nó encontrado, com onde o termo casou nele."""

    no: NoGrafo
    onde_casou: str

    def em_dicionario(self) -> dict[str, object]:
        """Linha esquelética de resultado, sem descrição nem metadados."""
        return {
            "id": self.no.id,
            "tipo": self.no.tipo.value,
            "rotulo": self.no.rotulo,
            "seq_criacao": self.no.ordem.seq_criacao,
            "casou_em": self.onde_casou,
        }


@dataclass(frozen=True)
class ResultadoDaBusca:
    """Página de resultados já ordenada, com o total do qual ela foi tirada."""

    itens: tuple[ResultadoRanqueado, ...]
    total_encontrado: int

    @property
    def truncado(self) -> bool:
        """Indica que há mais resultados além dos exibidos."""
        return self.total_encontrado > len(self.itens)

    def em_dicionario(self) -> dict[str, object]:
        """Resposta completa: o que veio, quanto existe e se foi cortado."""
        return {
            "total": self.total_encontrado,
            "exibidos": len(self.itens),
            "truncado": self.truncado,
            "resultados": [item.em_dicionario() for item in self.itens],
        }


def ranquear(nos: Sequence[NoGrafo], criterio: CriterioBusca) -> ResultadoDaBusca:
    """Ordena os nós por relevância ao termo e corta no limite pedido."""
    candidatos = [
        item for item in (_avaliar(no, criterio.termo_normalizado) for no in nos) if item is not None
    ]
    ordenados = sorted(candidatos, key=lambda item: item[0])
    itens = tuple(ResultadoRanqueado(no=no, onde_casou=onde) for _, no, onde in ordenados)
    return ResultadoDaBusca(
        itens=itens[: criterio.limite_efetivo],
        total_encontrado=len(itens),
    )


def _avaliar(no: NoGrafo, termo: str) -> tuple[tuple[int, int, int, int, str], NoGrafo, str] | None:
    """Chave de ordenação do nó, ou None quando o termo não casa nele.

    A chave é inteira e determinística de ponta a ponta: nada de pontuação em
    ponto flutuante, para que a mesma busca devolva a mesma ordem sempre.
    """
    forma_rotulo = _forma_do_casamento(no.rotulo.lower(), termo)
    if forma_rotulo != _FORMA_SEM_CASAMENTO:
        return ((0, forma_rotulo, _faixa_de_status(no), -no.ordem.seq_atualizacao, no.id), no, CASOU_NO_ROTULO)
    forma_props = _forma_do_casamento(_texto_das_propriedades(no), termo)
    if forma_props == _FORMA_SEM_CASAMENTO:
        return None
    return ((1, forma_props, _faixa_de_status(no), -no.ordem.seq_atualizacao, no.id), no, CASOU_NAS_PROPRIEDADES)


def _texto_das_propriedades(no: NoGrafo) -> str:
    """Concatena os valores das propriedades para a comparação textual."""
    return " ".join(str(valor) for valor in no.propriedades.values()).lower()


def _forma_do_casamento(texto: str, termo: str) -> int:
    """Quão exato foi o encontro: palavra inteira, prefixo de palavra ou pedaço."""
    if not termo:
        return _FORMA_SEM_CASAMENTO
    palavras = _palavras(texto)
    if termo in palavras:
        return _FORMA_PALAVRA_INTEIRA
    if any(palavra.startswith(termo) for palavra in palavras):
        return _FORMA_PREFIXO
    if termo in texto:
        return _FORMA_SUBSTRING
    return _FORMA_SEM_CASAMENTO


def _palavras(texto: str) -> frozenset[str]:
    """Quebra o texto em palavras, tratando tudo que não é alfanumérico como espaço."""
    separado = "".join(caractere if caractere.isalnum() else " " for caractere in texto)
    return frozenset(separado.split())


def palavras_significativas(texto: str) -> frozenset[str]:
    """Palavras do texto que dizem de que ele trata: sem as curtas, as vazias e os números."""
    return frozenset(
        palavra
        for palavra in _palavras(texto.lower())
        if len(palavra) >= TAMANHO_MINIMO_DE_PALAVRA and palavra not in PALAVRAS_VAZIAS and not palavra.isdigit()
    )


def contar_palavras_casadas(no: NoGrafo, palavras: frozenset[str]) -> int:
    """Quantas das palavras aparecem inteiras no rótulo ou nas propriedades do nó."""
    texto = f"{no.rotulo.lower()} {_texto_das_propriedades(no)}"
    return len(palavras & _palavras(texto))


def _faixa_de_status(no: NoGrafo) -> int:
    """Aberto primeiro, sem status no meio, encerrado por último."""
    status = no.obter_propriedade("status")
    if status is None:
        return 1
    return 2 if str(status) in STATUS_ENCERRADOS else 0
