"""Escada de degradação da vista sob pressão de orçamento, em uma tabela só.

O comportamento anterior era um laço que descartava seções inteiras da menos
para a mais importante. Numa sessão grande isso apagava a lista de vizinhos —
a única coisa que diz ao agente o que pedir a seguir — antes de tocar em
qualquer conteúdo secundário. A escada abaixo torna a política de renúncia
legível: primeiro o contexto, depois a memória encolhe para a afirmação, depois
o apoio e o detalhe, e só então a vizinhança encolhe, mantendo ao menos um
exemplar de cada tipo.

A memória encolhe cedo de propósito. Com vinte aprendizados promovidos num
projeto, a escada descartava as decisões e as evidências da própria tarefa
antes de tocar nos aprendizados, que continuavam inteiros: o executor perdia o
que governa o trabalho para manter o como aplicar de lições que nem casavam
com ele. A afirmação fica em todos os degraus até o da navegação; o resto
volta por `expandir_no`.
"""

from dataclasses import dataclass, field

from graphow.context.secoes import PrioridadeRetencao

# Quantos vizinhos por tipo sobrevivem em cada degrau de aperto.
LIMITES_DE_VIZINHOS_POR_TIPO: tuple[int, ...] = (8, 4, 2, 1)


@dataclass(frozen=True)
class PlanoDeCorte:
    """Um degrau da escada: o que se abre mão, se a memória vai resumida e quanto a vizinhança encolhe."""

    prioridades_descartadas: frozenset[PrioridadeRetencao] = field(default_factory=frozenset)
    limite_de_vizinhos: int | None = None
    # Os grupos que declaram a forma curta de suas linhas passam a usá-la: hoje,
    # os aprendizados aplicáveis, que ficam só com a afirmação e as marcas.
    memoria_resumida: bool = False

    @property
    def houve_corte(self) -> bool:
        """Indica se algo foi omitido, para o aviso de truncagem no texto."""
        return bool(self.prioridades_descartadas) or self.limite_de_vizinhos is not None or self.memoria_resumida


_CONTEXTO: frozenset[PrioridadeRetencao] = frozenset({PrioridadeRetencao.CONTEXTO})
_APOIO: frozenset[PrioridadeRetencao] = _CONTEXTO | {PrioridadeRetencao.APOIO}
_MAIS_DECISOES: frozenset[PrioridadeRetencao] = _APOIO | {PrioridadeRetencao.DECISOES}
_MAIS_BLOQUEIOS: frozenset[PrioridadeRetencao] = _MAIS_DECISOES | {PrioridadeRetencao.BLOQUEIOS}
# A memória cai junto da navegação, e depois dela nada: o fechamento de uma
# sessão e os aprendizados aplicáveis são o que impede re-decidir.
_MAIS_NAVEGACAO: frozenset[PrioridadeRetencao] = _MAIS_BLOQUEIOS | {
    PrioridadeRetencao.NAVEGACAO,
    PrioridadeRetencao.MEMORIA,
}
_TUDO_MENOS_O_ALVO: frozenset[PrioridadeRetencao] = _MAIS_NAVEGACAO | {PrioridadeRetencao.RESTRICOES}


def montar_escada_de_corte() -> tuple[PlanoDeCorte, ...]:
    """Consulta pura: os degraus, do texto mais completo ao mais enxuto."""
    degraus_por_descarte = (
        PlanoDeCorte(),
        PlanoDeCorte(prioridades_descartadas=_CONTEXTO),
        # A memória vai para a afirmação antes de a vista perder o apoio e as
        # decisões que governam o alvo.
        PlanoDeCorte(prioridades_descartadas=_CONTEXTO, memoria_resumida=True),
        PlanoDeCorte(prioridades_descartadas=_APOIO, memoria_resumida=True),
        PlanoDeCorte(prioridades_descartadas=_MAIS_DECISOES, memoria_resumida=True),
        PlanoDeCorte(prioridades_descartadas=_MAIS_BLOQUEIOS, memoria_resumida=True),
    )
    degraus_por_reducao = tuple(
        PlanoDeCorte(prioridades_descartadas=_MAIS_BLOQUEIOS, limite_de_vizinhos=limite, memoria_resumida=True)
        for limite in LIMITES_DE_VIZINHOS_POR_TIPO
    )
    # As restrições invioláveis são as últimas a cair: um vizinho perdido se
    # reencontra por busca, uma Constraint ignorada vira trabalho invalidado.
    ultimos_recursos = (
        PlanoDeCorte(prioridades_descartadas=_MAIS_NAVEGACAO, memoria_resumida=True),
        PlanoDeCorte(prioridades_descartadas=_TUDO_MENOS_O_ALVO, memoria_resumida=True),
    )
    return degraus_por_descarte + degraus_por_reducao + ultimos_recursos
