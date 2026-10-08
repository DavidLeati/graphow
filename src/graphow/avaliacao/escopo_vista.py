"""Ferramentas de leitura do corpus de escopo: a vista indexada e o cursor que avança o estado pelo log.

A avaliação do escopo olha o grafo em dezenas de pontos do histórico. `GrafoView`
varre todas as arestas a cada consulta, o que a projeção em produção aceita e um
percurso do histórico não: o cursor aplica só os eventos novos pelo mesmo redutor
(`aplicar_eventos`) e a vista indexada responde as mesmas perguntas por dicionário.
Nenhuma regra de escopo mora aqui; os dois só tornam a leitura barata.
"""

from collections import defaultdict
from collections.abc import Iterable

from graphow.avaliacao.corpus_escopo import CorpusEscopo
from graphow.core.events import EventoLog
from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.types import TipoAresta
from graphow.projection.graph_view import GrafoView
from graphow.projection.reducer import GrafoReducer


class VistaIndexada(GrafoView):
    """`GrafoView` que acha as arestas de um nó por índice, na mesma ordem que a varredura daria."""

    def __init__(self, estado: GrafoEstado) -> None:
        super().__init__(estado)
        self._por_origem: defaultdict[str, list[ArestaGrafo]] = defaultdict(list)
        self._por_destino: defaultdict[str, list[ArestaGrafo]] = defaultdict(list)
        for aresta in estado.arestas.values():
            self._por_origem[aresta.origem_id].append(aresta)
            self._por_destino[aresta.destino_id].append(aresta)

    def obter_arestas_saida(self, origem_id: str, tipo_aresta: TipoAresta | None = None) -> list[ArestaGrafo]:
        """As arestas que partem do nó, filtradas pelo tipo quando ele vem."""
        return _filtrar(self._por_origem.get(origem_id, ()), tipo_aresta)

    def obter_arestas_entrada(self, destino_id: str, tipo_aresta: TipoAresta | None = None) -> list[ArestaGrafo]:
        """As arestas que chegam ao nó, filtradas pelo tipo quando ele vem."""
        return _filtrar(self._por_destino.get(destino_id, ()), tipo_aresta)


class CursorDoCorpus:
    """Estado do grafo em pontos crescentes do log, sem recomeçar do zero a cada pergunta."""

    def __init__(self, corpus: CorpusEscopo) -> None:
        self._eventos: tuple[EventoLog, ...] = corpus.eventos
        self._estado: GrafoEstado = GrafoEstado()
        self._aplicados: int = 0

    def estado_ate(self, seq: int) -> GrafoEstado:
        """O estado logo depois do evento `seq`; pedir um ponto anterior ao atual recomeça o cursor."""
        if self._aplicados and self._eventos[self._aplicados - 1].seq > seq:
            self._estado, self._aplicados = GrafoEstado(), 0
        novos: list[EventoLog] = []
        while self._aplicados + len(novos) < len(self._eventos):
            proximo = self._eventos[self._aplicados + len(novos)]
            if proximo.seq > seq:
                break
            novos.append(proximo)
        self._estado = GrafoReducer.aplicar_eventos(self._estado, novos)
        self._aplicados += len(novos)
        return self._estado

    def vista_ate(self, seq: int) -> GrafoView:
        """A vista indexada do estado em `seq`."""
        return VistaIndexada(self.estado_ate(seq))


def _filtrar(arestas: Iterable[ArestaGrafo], tipo: TipoAresta | None) -> list[ArestaGrafo]:
    """As arestas do índice, todas ou só as do tipo."""
    return [aresta for aresta in arestas if tipo is None or aresta.tipo == tipo]
