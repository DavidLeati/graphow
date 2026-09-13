"""Rastreamento de linhagem reversa de artefatos até objetivos raiz (Goals)."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

TIPOS_DE_ARESTA_ASCENDENTE_POR_SAIDA: frozenset[TipoAresta] = frozenset(
    {
        TipoAresta.DERIVA_DE,
        TipoAresta.SUBSTITUI,
        TipoAresta.JUSTIFICA,
        TipoAresta.CONTRADIZ,
        TipoAresta.DEPENDE_DE,
    }
)


@dataclass(frozen=True)
class CaminhoLinhagem:
    """Representação imutável da cadeia de proveniência de um artefato."""

    id_alvo: str
    passos: tuple[str, ...] = field(default_factory=tuple)
    nos_cadeia: tuple[NoGrafo, ...] = field(default_factory=tuple)
    goal_raiz: NoGrafo | None = None


class LineageTracer:
    """Localiza a trilha causal completa de um nó folha até o Goal raiz."""

    def rastrear_linhagem(self, id_no_alvo: str, view: GrafoView) -> CaminhoLinhagem:
        """Sobe a hierarquia de arestas partindo do nó alvo até encontrar o Goal correspondente."""
        no_inicial = view.obter_no(id_no_alvo)
        if no_inicial is None:
            return CaminhoLinhagem(id_alvo=id_no_alvo)

        nos_visitados: list[NoGrafo] = [no_inicial]
        passos_descricao: list[str] = [f"[{no_inicial.tipo.value}] {no_inicial.rotulo} ({no_inicial.id})"]
        atual = no_inicial
        goal_encontrado: NoGrafo | None = None

        visitados_ids: set[str] = {no_inicial.id}
        while atual.tipo != TipoNo.GOAL:
            proximo = self._obter_proximo_ancestral(atual.id, view, visitados_ids)
            if proximo is None:
                break
            nos_visitados.append(proximo)
            passos_descricao.append(f"[{proximo.tipo.value}] {proximo.rotulo} ({proximo.id})")
            visitados_ids.add(proximo.id)
            atual = proximo
            if atual.tipo == TipoNo.GOAL:
                goal_encontrado = atual
                break

        return CaminhoLinhagem(
            id_alvo=id_no_alvo,
            passos=tuple(passos_descricao),
            nos_cadeia=tuple(nos_visitados),
            goal_raiz=goal_encontrado,
        )

    def _obter_proximo_ancestral(
        self,
        id_no: str,
        view: GrafoView,
        visitados: set[str],
    ) -> NoGrafo | None:
        """Busca nó pai conectado por arestas causais (deriva_de, substitui, decompoe)."""
        candidatos_de_saida = (
            aresta.destino_id
            for aresta in view.obter_arestas_saida(id_no)
            if aresta.tipo in TIPOS_DE_ARESTA_ASCENDENTE_POR_SAIDA
        )
        ancestral = self._primeiro_no_inedito(candidatos_de_saida, view, visitados)
        if ancestral is not None:
            return ancestral

        candidatos_de_entrada = (
            aresta.origem_id
            for aresta in view.obter_arestas_entrada(id_no)
            if aresta.tipo == TipoAresta.DECOMPOE
        )
        return self._primeiro_no_inedito(candidatos_de_entrada, view, visitados)

    def _primeiro_no_inedito(
        self,
        ids_candidatos: Iterable[str],
        view: GrafoView,
        visitados: set[str],
    ) -> NoGrafo | None:
        """Devolve o primeiro nó existente e ainda não percorrido da sequência."""
        for id_candidato in ids_candidatos:
            if id_candidato in visitados:
                continue
            no_candidato = view.obter_no(id_candidato)
            if no_candidato is not None:
                return no_candidato
        return None
