"""Resolve a política de governança efetiva lendo o estado do grafo.

A composição em si é pura e mora em `core/governanca.py`; aqui só se acha o nó
global e o Projeto do alvo. A política vive no grafo para o replay ser
determinístico: o veredito do kernel depende só do log.

Nenhum portão consulta isto ainda: ligar a política ao RoleGate é do passo seguinte.
"""

from graphow.core.governanca import (
    ID_GOVERNANCA_GLOBAL,
    PROPRIEDADE_GOVERNANCA_DO_PROJETO,
    PROPRIEDADE_NIVEL_AUTONOMIA,
    PoliticaGovernanca,
    compor_politica_do_projeto,
    compor_politica_global,
)
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoNo
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral


def resolver_politica_global(estado: GrafoEstado) -> PoliticaGovernanca:
    """Política global: a do nó `governanca-global`, ou governança máxima se ele não existe."""
    no = estado.nos.get(ID_GOVERNANCA_GLOBAL)
    if no is None or no.tipo != TipoNo.GOVERNANCA:
        return compor_politica_global(None)
    return compor_politica_global(no.propriedades)


def resolver_politica_do_projeto(id_projeto: str, estado: GrafoEstado) -> PoliticaGovernanca:
    """Política efetiva do Projeto, com a herança da global e o legado `nivel_autonomia`.

    Um id que não é de um Projeto resolve para a global.
    """
    politica_global = resolver_politica_global(estado)
    projeto = estado.nos.get(id_projeto)
    if projeto is None or projeto.tipo != TipoNo.PROJETO:
        return politica_global
    return compor_politica_do_projeto(
        projeto.propriedades.get(PROPRIEDADE_GOVERNANCA_DO_PROJETO),
        projeto.propriedades.get(PROPRIEDADE_NIVEL_AUTONOMIA),
        politica_global,
    )


def resolver_politica_do_no(
    id_no: str,
    estado: GrafoEstado,
    rastreador: RastreadorProjetoAncestral,
) -> PoliticaGovernanca:
    """Política efetiva do Projeto que contém o nó; sem Projeto ancestral, a global."""
    id_projeto = rastreador.rastrear(id_no, estado)
    if id_projeto is None:
        return resolver_politica_global(estado)
    return resolver_politica_do_projeto(id_projeto, estado)
