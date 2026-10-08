"""As leituras inteiras da política de governança: domínio, padrão e qual valor é o mais restritivo.

`max_correcoes` e as leituras do escopo governado não se decidem por papel: o
valor é um número. Cada uma declara aqui o domínio e o padrão, para validar a
configuração, descrever a recusa e compor a política mais restritiva num lugar
só. As chaves são os valores do enum `Gesto`, em texto, para este módulo não
importar `governanca.py`, que o importa.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

MAX_CORRECOES_MINIMO: int = 0
MAX_CORRECOES_MAXIMO: int = 5

# K: quantas Tasks emergentes uma raiz de cadeia gera antes de o desvio disparar.
LIMIAR_DESVIO_POR_RAIZ_MINIMO: int = 1
LIMIAR_DESVIO_POR_RAIZ_MAXIMO: int = 50
# M: quantas Tasks emergentes o Goal acumula, desde o último zero, antes de disparar.
LIMIAR_DESVIO_POR_GOAL_MINIMO: int = 1
LIMIAR_DESVIO_POR_GOAL_MAXIMO: int = 200
# Teto de Tasks emergentes até um `responder_desvio`; 0 desliga a recusa.
TETO_EXPANSAO_MINIMO: int = 0
TETO_EXPANSAO_MAXIMO: int = 500


@dataclass(frozen=True)
class LeituraInteira:
    """Domínio fechado de um inteiro da política; `zero_desliga` marca o 0 como "sem limite"."""

    minimo: int
    maximo: int
    padrao: int
    zero_desliga: bool = False

    def aceita(self, valor: Any) -> bool:
        """Inteiro dentro do domínio, sem aceitar booleano como número."""
        return isinstance(valor, int) and not isinstance(valor, bool) and self.minimo <= valor <= self.maximo

    def descrever(self) -> str:
        """O domínio em texto, para a mensagem de recusa."""
        return f"um inteiro de {self.minimo} a {self.maximo}"

    def mais_restritivo(self, valores: Sequence[int]) -> int:
        """O menor valor; com `zero_desliga`, o menor positivo, porque 0 não limita nada."""
        if not self.zero_desliga:
            return min(valores)
        positivos = [valor for valor in valores if valor > 0]
        return min(positivos) if positivos else 0


LEITURAS_INTEIRAS: Mapping[str, LeituraInteira] = MappingProxyType({
    "max_correcoes": LeituraInteira(MAX_CORRECOES_MINIMO, MAX_CORRECOES_MAXIMO, padrao=2),
    "limiar_desvio_por_raiz": LeituraInteira(
        LIMIAR_DESVIO_POR_RAIZ_MINIMO, LIMIAR_DESVIO_POR_RAIZ_MAXIMO, padrao=3
    ),
    "limiar_desvio_por_goal": LeituraInteira(
        LIMIAR_DESVIO_POR_GOAL_MINIMO, LIMIAR_DESVIO_POR_GOAL_MAXIMO, padrao=5
    ),
    "teto_expansao": LeituraInteira(TETO_EXPANSAO_MINIMO, TETO_EXPANSAO_MAXIMO, padrao=0, zero_desliga=True),
})
