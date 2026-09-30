"""A linha `Cota: 5h <n>%, semana <n>%` que a raiz escreve, lida de volta da transcrição.

A raiz lê o uso do plano depois de cada rodada e nada disso ficava gravado: a
análise de um goal real refez a conta à mão, rodada por rodada. A raiz não
escreve no grafo, e é bom que continue assim. Ela passa a escrever a leitura
em texto, no despacho do condutor e na mensagem em que para o laço, e o harness,
que já lê as transcrições, grava os números no Run.

O formato é de gente, então a leitura é tolerante: o `%` é opcional, a vírgula
decimal vale, e os espaços e a caixa não importam.
"""

from dataclasses import dataclass
import re

PADRAO_DA_COTA: re.Pattern[str] = re.compile(
    r"cota\s*:\s*\**\s*5\s*h\s*(?P<cinco_horas>\d+(?:[.,]\d+)?)\s*%?\s*[,;]\s*"
    r"semana\w*\s*(?P<semanal>\d+(?:[.,]\d+)?)\s*%?",
    re.IGNORECASE,
)
MARCAS_DA_COTA: tuple[str, ...] = ("Cota", "cota", "COTA")
# As chaves no Run são o prefixo mais o momento: cota_5h_inicio, cota_semanal_fim.
PREFIXO_COTA_5H: str = "cota_5h_"
PREFIXO_COTA_SEMANAL: str = "cota_semanal_"
MOMENTO_DO_DESPACHO: str = "inicio"
MOMENTO_DA_PARADA: str = "fim"


@dataclass(frozen=True)
class CotaDeclarada:
    """Os percentuais da janela de 5 horas e da semanal, como a raiz os leu."""

    cinco_horas: float
    semanal: float

    def em_propriedades(self, momento: str) -> dict[str, float]:
        """As propriedades do Run para o momento dado: `inicio` no despacho, `fim` na parada."""
        return {f"{PREFIXO_COTA_5H}{momento}": self.cinco_horas, f"{PREFIXO_COTA_SEMANAL}{momento}": self.semanal}


def ultima_cota(texto: str) -> CotaDeclarada | None:
    """A última linha de cota do texto; None quando ele não traz nenhuma."""
    achadas = list(PADRAO_DA_COTA.finditer(texto))
    if not achadas:
        return None
    ultima = achadas[-1]
    return CotaDeclarada(cinco_horas=_numero(ultima["cinco_horas"]), semanal=_numero(ultima["semanal"]))


def _numero(texto: str) -> float:
    """O percentual como número; inteiro quando não tem casa decimal, para o Run ler como a raiz escreveu."""
    valor = float(texto.replace(",", "."))
    return int(valor) if valor.is_integer() else valor
