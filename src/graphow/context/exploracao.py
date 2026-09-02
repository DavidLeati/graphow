"""Exploração limitada do subgrafo a partir de um nó alvo.

As políticas de contexto precisam andar no grafo. Devolver todos os nós de um
tipo faz o orçamento de tokens ser consumido por material irrelevante ao alvo,
que é o oposto de divulgação progressiva. Ver auditoria F-08.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta
from graphow.projection.graph_view import GrafoView

SALTOS_MAXIMOS_PADRAO: int = 3


class DirecaoTravessia(str, Enum):
    """Sentido em que uma aresta é percorrida durante a exploração."""

    SAIDA = "saida"
    ENTRADA = "entrada"
    AMBAS = "ambas"


@dataclass(frozen=True)
class PedidoExploracao:
    """Parâmetros imutáveis de uma travessia a partir do nó alvo."""

    id_alvo: str
    tipos_de_aresta: frozenset[TipoAresta]
    direcao: DirecaoTravessia = DirecaoTravessia.SAIDA
    saltos_maximos: int = SALTOS_MAXIMOS_PADRAO


class ExploradorSubgrafo:
    """Percorre o grafo em largura, restrito a tipos de aresta e a um raio de saltos."""

    def __init__(self, view: GrafoView) -> None:
        self._view: GrafoView = view

    def coletar_alcancaveis(self, pedido: PedidoExploracao) -> tuple[NoGrafo, ...]:
        """Consulta pura: nós alcançáveis a partir do alvo, sem incluir o próprio alvo."""
        alcancados = self._percorrer(pedido)
        return tuple(
            no
            for no in (self._view.obter_no(id_no) for id_no in alcancados)
            if no is not None and no.id != pedido.id_alvo
        )

    def _percorrer(self, pedido: PedidoExploracao) -> tuple[str, ...]:
        """Executa a busca em largura respeitando o limite de saltos."""
        visitados: set[str] = {pedido.id_alvo}
        ordem_de_descoberta: list[str] = []
        fronteira: tuple[str, ...] = (pedido.id_alvo,)
        for _ in range(pedido.saltos_maximos):
            if not fronteira:
                break
            fronteira = self._expandir_fronteira(fronteira, pedido, visitados)
            ordem_de_descoberta.extend(fronteira)
        return tuple(ordem_de_descoberta)

    def _expandir_fronteira(
        self,
        fronteira: Sequence[str],
        pedido: PedidoExploracao,
        visitados: set[str],
    ) -> tuple[str, ...]:
        """Descobre o próximo nível de vizinhos ainda não visitados."""
        descobertos: list[str] = []
        for id_no in fronteira:
            descobertos.extend(self._vizinhos_ineditos(id_no, pedido, visitados))
        return tuple(descobertos)

    def _vizinhos_ineditos(
        self,
        id_no: str,
        pedido: PedidoExploracao,
        visitados: set[str],
    ) -> tuple[str, ...]:
        """Coleta os vizinhos do nó que ainda não foram alcançados."""
        candidatos = self._vizinhos_por_direcao(id_no, pedido)
        ineditos = tuple(dict.fromkeys(candidato for candidato in candidatos if candidato not in visitados))
        visitados.update(ineditos)
        return ineditos

    def _vizinhos_por_direcao(self, id_no: str, pedido: PedidoExploracao) -> tuple[str, ...]:
        """Lista os vizinhos conforme o sentido de travessia solicitado."""
        vizinhos: list[str] = []
        if pedido.direcao in (DirecaoTravessia.SAIDA, DirecaoTravessia.AMBAS):
            vizinhos.extend(
                aresta.destino_id
                for aresta in self._view.obter_arestas_saida(id_no)
                if aresta.tipo in pedido.tipos_de_aresta
            )
        if pedido.direcao in (DirecaoTravessia.ENTRADA, DirecaoTravessia.AMBAS):
            vizinhos.extend(
                aresta.origem_id
                for aresta in self._view.obter_arestas_entrada(id_no)
                if aresta.tipo in pedido.tipos_de_aresta
            )
        return tuple(vizinhos)

    def coletar_origens_diretas(self, id_alvo: str, tipo_aresta: TipoAresta) -> tuple[NoGrafo, ...]:
        """Nós que apontam diretamente para o alvo por um tipo específico de aresta."""
        origens = (
            self._view.obter_no(aresta.origem_id)
            for aresta in self._view.obter_arestas_entrada(id_alvo, tipo_aresta)
        )
        return tuple(no for no in origens if no is not None)
