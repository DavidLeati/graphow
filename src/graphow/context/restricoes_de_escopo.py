"""A restrição como a vista a mostra: com o id, o `tipo` e os critérios de aceite à frente.

Critério de aceite e fronteira são Constraint (`core/escopo.py`). A Task emergente
cita o critério que atende pelo id do nó, e o agente só pode citar o que lê: por
isso cada linha leva o id e a marca do `tipo`. Os critérios vêm primeiro e a
fronteira logo depois, para o Goal ficar legível de cima para baixo; o resto das
restrições segue a ordem em que foi descoberto.
"""

from collections.abc import Sequence

from graphow.context.secoes import (
    anotar_ordem,
    anotar_proveniencia,
    em_uma_linha,
    formatar_no_em_linha,
    formatar_propriedades,
    marcar_nao_confiavel,
)
from graphow.core.escopo import CAMPO_TIPO_CONSTRAINT, CONSTRAINT_CRITERIO_ACEITE, CONSTRAINT_FRONTEIRA
from graphow.core.models import NoGrafo

_POSICAO_POR_TIPO: dict[str, int] = {CONSTRAINT_CRITERIO_ACEITE: 0, CONSTRAINT_FRONTEIRA: 1}
_POSICAO_DAS_DEMAIS: int = 2


def tipo_da_restricao(no: NoGrafo) -> str:
    """O `tipo` declarado na Constraint, sem espaços; vazio quando ela não declara."""
    return em_uma_linha(no.obter_propriedade(CAMPO_TIPO_CONSTRAINT, "") or "")


def ordenar_restricoes(restricoes: Sequence[NoGrafo]) -> tuple[NoGrafo, ...]:
    """Critérios de aceite, depois a fronteira, depois as demais; a ordem de descoberta se mantém dentro de cada faixa."""
    return tuple(sorted(restricoes, key=lambda no: _POSICAO_POR_TIPO.get(tipo_da_restricao(no), _POSICAO_DAS_DEMAIS)))


def formatar_restricao(no: NoGrafo) -> str:
    """A restrição com id, `tipo` e as propriedades que sobram, em uma linha."""
    propriedades = {chave: valor for chave, valor in no.propriedades.items() if chave != CAMPO_TIPO_CONSTRAINT}
    corpo = f"{em_uma_linha(no.rotulo)}: {formatar_propriedades(propriedades)}"
    return f"{_cabeca(no)} {corpo}{anotar_ordem(no)}{anotar_proveniencia(no)}"


def formatar_restricao_curta(no: NoGrafo) -> str:
    """A forma resumida, que ainda carrega o id e o `tipo` para a citação."""
    tipo = tipo_da_restricao(no)
    if not tipo:
        return formatar_no_em_linha(no)
    return f"{_cabeca(no)} {em_uma_linha(no.rotulo)}{anotar_ordem(no)}{anotar_proveniencia(no)}"


def _cabeca(no: NoGrafo) -> str:
    """`- [id] (tipo)` quando a Constraint declara o tipo; `- [id]` quando não."""
    tipo = tipo_da_restricao(no)
    marca = f" ({tipo})" if tipo else ""
    return f"- [{em_uma_linha(no.id)}]{marca}{marcar_nao_confiavel(no)}"
