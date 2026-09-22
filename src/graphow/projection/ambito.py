"""O âmbito de cada nó: os projetos de trabalho ou as sessões que o hook abre.

O hook de início cria, por repositório, um Projeto com o nome da pasta e um Setor
`Memoria`, e pendura nele uma Sessao a cada sessão do agente. Esse ambiente
aparecia entre os projetos de trabalho, na árvore, na raiz do canvas e no total,
com dezenas de sessões e Runs de telemetria no meio do que o humano e o
planejador estruturaram. O log já diz o que é o quê: o ambiente do hook nasce do
papel `sistema`, que só o harness assume, e um Projeto de trabalho nasce de quem
trabalha. A separação é lida da proveniência, sem propriedade que alguém precise
lembrar de gravar, e vale para o que o grafo já tem.

Separar não esvazia o ambiente do hook. A sessão dele continua sendo onde o
agente registra a pergunta ou a nota avulsa que não deve poluir projeto nenhum.
"""

from collections.abc import Mapping
from enum import Enum

from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoNo
from graphow.projection.graph_view import GrafoView


class Ambito(str, Enum):
    """Onde um nó mora: entre os projetos de trabalho ou nas sessões do hook."""

    PROJETOS = "projetos"
    HOOK = "hook"


def ler_ambito(texto: str | None) -> Ambito | None:
    """O âmbito pedido, ou None quando o pedido não nomeia um: nesse caso nada é filtrado."""
    valores = {ambito.value: ambito for ambito in Ambito}
    return valores.get((texto or "").strip().lower())


def nasceu_do_hook(no: NoGrafo) -> bool:
    """O papel `sistema` só é assumido pelo harness: o que ele criou nasceu do hook."""
    return no.proveniencia.papel == PapelAutor.SISTEMA.value


def eh_ambiente_do_hook(no: NoGrafo) -> bool:
    """Um Projeto que o hook criou guarda as sessões de um repositório, e não é projeto de trabalho."""
    return no.tipo == TipoNo.PROJETO and nasceu_do_hook(no)


def ambientes_do_hook(view: GrafoView) -> frozenset[str]:
    """Os ids dos Projetos que o hook criou, um por repositório."""
    return frozenset(no.id for no in view.listar_nos_por_tipo(TipoNo.PROJETO) if nasceu_do_hook(no))


def ambito_do_no(id_no: str, mapa_projetos: Mapping[str, str], ambientes: frozenset[str]) -> Ambito:
    """O âmbito do Projeto que contém o nó.

    Um nó fora de qualquer Projeto fica entre os projetos, onde sempre esteve: é
    lá que a pasta "Fora da hierarquia" o mostra.
    """
    return Ambito.HOOK if mapa_projetos.get(id_no) in ambientes else Ambito.PROJETOS


def contar_por_ambito(view: GrafoView, mapa_projetos: Mapping[str, str]) -> dict[str, int]:
    """Quantos nós do grafo moram em cada âmbito, para cada raiz da árvore mostrar o seu total."""
    ambientes = ambientes_do_hook(view)
    contagem = {ambito.value: 0 for ambito in Ambito}
    for no in view.listar_todos_os_nos():
        contagem[ambito_do_no(no.id, mapa_projetos, ambientes).value] += 1
    return contagem
