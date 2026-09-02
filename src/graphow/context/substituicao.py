"""Marcação de proveniência e de decisões substituídas nas linhas da vista.

Depois de uma Decision nova com aresta `substitui`, o executor via as duas lado
a lado sob "Decisões Que Governam Esta Tarefa", sem qualquer sinal de qual valia.
A aresta servia só para travessia. Aqui ela passa a governar o que o
materializador manda — e cada linha ganha a assinatura de quem a escreveu.
Ver achados A-09 e A-17.
"""

from collections.abc import Sequence

from graphow.context.secoes import PrioridadeRetencao, SecaoContexto, formatar_no_em_linha
from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def identificar_substituta(id_decisao: str, view: GrafoView) -> str | None:
    """Devolve a Decision vigente que substituiu a informada, se houver alguma."""
    entradas = view.obter_arestas_entrada(id_decisao, TipoAresta.SUBSTITUI)
    candidatas = sorted(aresta.origem_id for aresta in entradas)
    for id_candidata in candidatas:
        no = view.obter_no(id_candidata)
        if no is not None and no.tipo == TipoNo.DECISION:
            return no.id
    return None


def formatar_decisao(no: NoGrafo, view: GrafoView) -> str:
    """Descreve a decisão marcando explicitamente quando ela já não vale."""
    substituta = identificar_substituta(no.id, view)
    linha = formatar_no_em_linha(no)
    if substituta is None:
        return linha
    return f"{linha} [SUBSTITUIDA por {substituta}: nao siga esta decisao]"


def montar_secao_de_decisoes(
    decisoes: Sequence[NoGrafo],
    view: GrafoView,
    ordens: tuple[int, PrioridadeRetencao],
) -> SecaoContexto:
    """Seção de decisões com as vigentes à frente e as substituídas sinalizadas."""
    ordenadas = sorted(decisoes, key=lambda no: (identificar_substituta(no.id, view) is not None, no.id))
    ordem_exibicao, prioridade = ordens
    return SecaoContexto(
        titulo="Decisoes Que Governam Esta Tarefa",
        linhas=tuple(formatar_decisao(no, view) for no in ordenadas),
        ordem_exibicao=ordem_exibicao,
        prioridade_retencao=prioridade,
        ids_incluidos=tuple(no.id for no in ordenadas),
    )
