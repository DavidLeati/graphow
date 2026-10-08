"""Composição da política de um nó contido por mais de um Projeto: em cada gesto, a mais restritiva.

Separada de `governanca.py` para esse módulo caber no limite do arquivo. Nenhum
Projeto puxa a política permissiva de outro: o humano vence o árbitro e o
executor, `estrito` vence `ilimitado` e as leituras inteiras valem o menor número.
"""

from collections.abc import Mapping, Sequence

from graphow.core.governanca import (
    GESTOS_INTEIROS,
    PREFIXO_ORIGEM_PROJETO_RESTRITIVO,
    VALOR_ESTRITO,
    VALOR_HUMANO,
    Gesto,
    PoliticaGovernanca,
    ValorDeGesto,
)
from graphow.core.leituras_inteiras import LEITURAS_INTEIRAS


def _mais_restritivo(gesto: Gesto, valores: Sequence[ValorDeGesto]) -> ValorDeGesto:
    """O valor que menos entrega do gesto: humano, estrito ou o menor número das leituras inteiras.

    Na `acao_externa`, o humano vence o executor, como vence o árbitro nos gestos por papel.
    Nas leituras inteiras vale o menor número; no `teto_expansao`, o menor positivo (0 desliga).
    """
    if gesto in GESTOS_INTEIROS:
        return LEITURAS_INTEIRAS[gesto.value].mais_restritivo([int(valor) for valor in valores])
    restritivo = VALOR_ESTRITO if gesto == Gesto.ESTRUTURA else VALOR_HUMANO
    return restritivo if restritivo in valores else valores[0]


def _projeto_que_restringiu(
    gesto: Gesto,
    valor: ValorDeGesto,
    politicas: Sequence[tuple[str, PoliticaGovernanca]],
) -> str:
    """Origem `projeto:<id>` do primeiro Projeto, em ordem de id, cujo valor é o vencedor."""
    id_projeto = next(id_projeto for id_projeto, politica in politicas if politica.valor(gesto) == valor)
    return f"{PREFIXO_ORIGEM_PROJETO_RESTRITIVO}{id_projeto}"


def compor_mais_restritiva(politicas_por_projeto: Mapping[str, PoliticaGovernanca]) -> PoliticaGovernanca:
    """Política que vale para um nó contido por mais de um Projeto: em cada gesto, a mais restritiva.

    O humano vence o árbitro e o executor, `estrito` vence `ilimitado` e nas leituras
    inteiras vale o menor número (no `teto_expansao`, o menor positivo). A origem do gesto
    aponta o Projeto que o restringiu, e no empate o de menor id: a resposta não depende da ordem do mapa. Com um Projeto
    só, é a política dele, sem mudar nem as origens.
    """
    if not politicas_por_projeto:
        raise ValueError("Compor a política mais restritiva exige ao menos um Projeto")
    ordenadas = sorted(politicas_por_projeto.items())
    if len(ordenadas) == 1:
        return ordenadas[0][1]
    valores = {
        gesto: _mais_restritivo(gesto, [politica.valor(gesto) for _, politica in ordenadas]) for gesto in Gesto
    }
    origens = {gesto: _projeto_que_restringiu(gesto, valor, ordenadas) for gesto, valor in valores.items()}
    return PoliticaGovernanca(valores, origens)
