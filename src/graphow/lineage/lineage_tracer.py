"""Rastreamento de linhagem reversa de artefatos até objetivos raiz (Goals).

A subida é uma busca em largura, não um caminho guloso. O rastreador antigo
seguia o primeiro ancestral de cada nó e, num beco sem saída, devolvia None sem
voltar atrás, embora outro ramo levasse ao Goal. Ele também subia por
`depende_de`: com `tA depende_de tB`, o artefato de `tA` era atribuído ao Goal
de `tB`. Pré-requisito não é ascendência; quem diz a que Goal a tarefa pertence
é a decomposição.
"""

from collections import deque
from collections.abc import Iterator
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
    """Localiza a trilha causal mais curta de um nó folha até o Goal raiz."""

    def rastrear_linhagem(self, id_no_alvo: str, view: GrafoView) -> CaminhoLinhagem:
        """Sobe em largura a partir do alvo; sem Goal alcançável, a trilha é só o alvo."""
        no_inicial = view.obter_no(id_no_alvo)
        if no_inicial is None:
            return CaminhoLinhagem(id_alvo=id_no_alvo)
        pais: dict[str, NoGrafo | None] = {no_inicial.id: None}
        goal = self._subir_ate_um_goal(no_inicial, view, pais)
        cadeia = self._reconstruir_cadeia(goal, pais) if goal is not None else (no_inicial,)
        return CaminhoLinhagem(
            id_alvo=id_no_alvo,
            passos=tuple(f"[{no.tipo.value}] {no.rotulo} ({no.id})" for no in cadeia),
            nos_cadeia=cadeia,
            goal_raiz=goal,
        )

    def _subir_ate_um_goal(self, inicio: NoGrafo, view: GrafoView, pais: dict[str, NoGrafo | None]) -> NoGrafo | None:
        """Busca em largura; preenche `pais` (id → nó de onde se chegou) e devolve o Goal mais próximo."""
        fila: deque[NoGrafo] = deque([inicio])
        while fila:
            atual = fila.popleft()
            if atual.tipo == TipoNo.GOAL:
                return atual
            ineditos = list({no.id: no for no in self._ancestrais(atual.id, view) if no.id not in pais}.values())
            pais.update(dict.fromkeys((no.id for no in ineditos), atual))
            fila.extend(ineditos)
        return None

    def _reconstruir_cadeia(self, goal: NoGrafo, pais: dict[str, NoGrafo | None]) -> tuple[NoGrafo, ...]:
        """Refaz o caminho do Goal de volta ao alvo e o devolve na ordem alvo → Goal."""
        cadeia: list[NoGrafo] = []
        atual: NoGrafo | None = goal
        while atual is not None:
            cadeia.append(atual)
            atual = pais[atual.id]
        return tuple(reversed(cadeia))

    def _ancestrais(self, id_no: str, view: GrafoView) -> Iterator[NoGrafo]:
        """Proveniência de saída primeiro, depois quem decompõe o nó."""
        ids_de_saida = (
            aresta.destino_id
            for aresta in view.obter_arestas_saida(id_no)
            if aresta.tipo in TIPOS_DE_ARESTA_ASCENDENTE_POR_SAIDA
        )
        ids_de_entrada = (
            aresta.origem_id for aresta in view.obter_arestas_entrada(id_no) if aresta.tipo == TipoAresta.DECOMPOE
        )
        for id_ancestral in (*ids_de_saida, *ids_de_entrada):
            no = view.obter_no(id_ancestral)
            if no is not None:
                yield no
