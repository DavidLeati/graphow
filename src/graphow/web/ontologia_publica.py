"""Vocabulário da ontologia publicado para a interface, lido das tabelas do kernel.

A tela oferece tipos de aresta ao ligar dois nós e status ao editar um. Uma cópia
dessas listas no JavaScript divergiria do portão na primeira mudança de schema, e
a interface passaria a sugerir justamente o que o kernel recusa. Por isso ela
pergunta aqui, e aqui a resposta sai da mesma tabela que o `SchemaGate` aplica.
"""

from typing import Any

from graphow.core.types import (
    NivelAutonomiaProjeto,
    StatusQuestion,
    StatusSessao,
    StatusTask,
    TipoAresta,
    TipoNo,
)
from graphow.kernel.schema_gate import SchemaGate


def montar_ontologia_publica() -> dict[str, Any]:
    """Tipos de nó, pares permitidos de cada aresta e os vocabulários de status."""
    return {
        "tipos_no": [tipo.value for tipo in TipoNo],
        "arestas": {tipo.value: _pares_permitidos(tipo) for tipo in TipoAresta},
        "status": {
            TipoNo.TASK.value: [status.value for status in StatusTask],
            TipoNo.QUESTION.value: [status.value for status in StatusQuestion],
            TipoNo.SESSAO.value: [status.value for status in StatusSessao],
        },
        "niveis_autonomia": [nivel.value for nivel in NivelAutonomiaProjeto],
    }


def _pares_permitidos(tipo: TipoAresta) -> list[list[str]]:
    """Pares origem-destino que o portão aceita para o tipo, em ordem estável."""
    pares = SchemaGate.PARES_ARESTAS_PERMITIDOS.get(tipo, frozenset())
    return sorted([origem.value, destino.value] for origem, destino in pares)
