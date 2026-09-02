"""Mapeamento de cada nó do grafo à Sessão e ao Projeto que o contêm."""

from collections.abc import Mapping, Sequence

from graphow.core.models import ArestaGrafo
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

# A hierarquia canônica é Projeto -> Setor -> Sessao -> trabalho, mas propagar por
# profundidade fixa quebra em silêncio se ela crescer. Ver auditoria F-11.
ARESTAS_QUE_PROPAGAM_PROJETO: frozenset[TipoAresta] = frozenset(
    {TipoAresta.CONTEM, TipoAresta.PRODUZ}
)


class MapeadorEscopo:
    """Consultas puras que associam nós aos contêineres de navegação."""

    def mapear_sessoes(self, view: GrafoView) -> Mapping[str, str]:
        """Associa cada nó de trabalho à Sessão que o produziu."""
        return {
            aresta.destino_id: aresta.origem_id
            for aresta in view.listar_todas_as_arestas()
            if aresta.tipo == TipoAresta.PRODUZ
        }

    def mapear_projetos(self, view: GrafoView) -> Mapping[str, str]:
        """Propaga a filiação a projeto por toda a cadeia, até o ponto fixo."""
        mapa: dict[str, str] = {no.id: no.id for no in view.listar_nos_por_tipo(TipoNo.PROJETO)}
        arestas_propagadoras = tuple(
            aresta
            for aresta in view.listar_todas_as_arestas()
            if aresta.tipo in ARESTAS_QUE_PROPAGAM_PROJETO
        )
        while self._propagar_uma_rodada(mapa, arestas_propagadoras):
            continue
        return mapa

    def _propagar_uma_rodada(
        self,
        mapa: dict[str, str],
        arestas: Sequence[ArestaGrafo],
    ) -> bool:
        """Estende o mapa em um salto e informa se algo novo foi descoberto."""
        descobertas = {
            aresta.destino_id: mapa[aresta.origem_id]
            for aresta in arestas
            if aresta.origem_id in mapa and aresta.destino_id not in mapa
        }
        mapa.update(descobertas)
        return bool(descobertas)

    def identificar_tasks_bloqueadas(self, view: GrafoView) -> frozenset[str]:
        """Coleta as Tasks travadas por alguma Question ainda aberta."""
        questoes_abertas = self._identificar_questoes_abertas(view)
        return frozenset(
            aresta.destino_id
            for aresta in view.listar_todas_as_arestas()
            if aresta.tipo == TipoAresta.BLOQUEIA and aresta.origem_id in questoes_abertas
        )

    def _identificar_questoes_abertas(self, view: GrafoView) -> frozenset[str]:
        """Coleta os identificadores das Questions que seguem sem resposta."""
        return frozenset(
            questao.id
            for questao in view.listar_nos_por_tipo(TipoNo.QUESTION)
            if questao.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value
        )

    def coletar_descendentes_do_projeto(self, id_projeto: str, view: GrafoView) -> tuple[str, ...]:
        """Lista o projeto e tudo que pende dele, em ordem estável."""
        mapa = self.mapear_projetos(view)
        descendentes = tuple(sorted(no_id for no_id, projeto in mapa.items() if projeto == id_projeto))
        if id_projeto in descendentes:
            return descendentes
        return (id_projeto,) + descendentes
