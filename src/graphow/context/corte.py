"""Escada de degradação da vista sob pressão de orçamento, em uma tabela só.

O comportamento anterior era um laço que descartava seções inteiras da menos
para a mais importante. Numa sessão grande isso apagava a lista de vizinhos —
a única coisa que diz ao agente o que pedir a seguir — antes de tocar em
qualquer conteúdo secundário. A escada abaixo torna a política de renúncia
legível: primeiro o apoio, depois o detalhe, e só então a vizinhança encolhe,
mantendo ao menos um exemplar de cada tipo. Ver achado A-08.
"""

from dataclasses import dataclass, field

from graphow.context.secoes import PrioridadeRetencao

# Quantos vizinhos por tipo sobrevivem em cada degrau de aperto.
LIMITES_DE_VIZINHOS_POR_TIPO: tuple[int, ...] = (8, 4, 2, 1)


@dataclass(frozen=True)
class PlanoDeCorte:
    """Um degrau da escada: o que se abre mão e quanto a vizinhança encolhe."""

    prioridades_descartadas: frozenset[PrioridadeRetencao] = field(default_factory=frozenset)
    limite_de_vizinhos: int | None = None

    @property
    def houve_corte(self) -> bool:
        """Indica se algo foi omitido, para o aviso de truncagem no texto."""
        return bool(self.prioridades_descartadas) or self.limite_de_vizinhos is not None


_APOIO: frozenset[PrioridadeRetencao] = frozenset({PrioridadeRetencao.APOIO})
_MAIS_DECISOES: frozenset[PrioridadeRetencao] = _APOIO | {PrioridadeRetencao.DECISOES}
_MAIS_BLOQUEIOS: frozenset[PrioridadeRetencao] = _MAIS_DECISOES | {PrioridadeRetencao.BLOQUEIOS}
_MAIS_NAVEGACAO: frozenset[PrioridadeRetencao] = _MAIS_BLOQUEIOS | {PrioridadeRetencao.NAVEGACAO}
_TUDO_MENOS_O_ALVO: frozenset[PrioridadeRetencao] = _MAIS_NAVEGACAO | {PrioridadeRetencao.RESTRICOES}


def montar_escada_de_corte() -> tuple[PlanoDeCorte, ...]:
    """Consulta pura: os degraus, do texto mais completo ao mais enxuto."""
    degraus_por_descarte = (
        PlanoDeCorte(),
        PlanoDeCorte(prioridades_descartadas=_APOIO),
        PlanoDeCorte(prioridades_descartadas=_MAIS_DECISOES),
        PlanoDeCorte(prioridades_descartadas=_MAIS_BLOQUEIOS),
    )
    degraus_por_reducao = tuple(
        PlanoDeCorte(prioridades_descartadas=_MAIS_BLOQUEIOS, limite_de_vizinhos=limite)
        for limite in LIMITES_DE_VIZINHOS_POR_TIPO
    )
    # As restrições invioláveis são as últimas a cair: um vizinho perdido se
    # reencontra por busca, uma Constraint ignorada vira trabalho invalidado.
    ultimos_recursos = (
        PlanoDeCorte(prioridades_descartadas=_MAIS_NAVEGACAO),
        PlanoDeCorte(prioridades_descartadas=_TUDO_MENOS_O_ALVO),
    )
    return degraus_por_descarte + degraus_por_reducao + ultimos_recursos
