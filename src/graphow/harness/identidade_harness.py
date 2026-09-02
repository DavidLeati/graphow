"""Identidade sob a qual um harness registra sessões e execuções no grafo.

Adaptadores de hook submetiam patches declarando `papel=humano`. Um gancho que
roda sozinho não é o humano no loop: era a mesma auto-atribuição de papel que o
Passo 1 fechou na superfície MCP. Ver auditoria F-02.
"""

from dataclasses import dataclass

from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.types import PapelAutor

PAPEIS_VALIDOS_EM_HARNESS: frozenset[PapelAutor] = frozenset({PapelAutor.SISTEMA, PapelAutor.HUMANO})


@dataclass(frozen=True)
class IdentidadeHarness:
    """Autor e papel fixados na configuração do harness, não na chamada."""

    autor: str = "harness"
    papel: PapelAutor = PapelAutor.SISTEMA

    def __post_init__(self) -> None:
        """Recusa papéis que dariam ao harness poderes de agente ou de planejamento."""
        if self.papel in PAPEIS_VALIDOS_EM_HARNESS:
            return
        raise ErroPermissaoPapel(
            f"O papel '{self.papel.value}' nao pode ser atribuido a um harness",
            {"papeis_aceitos": ", ".join(sorted(papel.value for papel in PAPEIS_VALIDOS_EM_HARNESS))},
        )
