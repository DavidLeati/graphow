"""Camada de consulta e visualização imutável do grafo projetado (CQRS)."""

from collections.abc import Sequence

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo


class GrafoView:
    """Consultas somente-leitura sobre o estado projetado do grafo em memória."""

    def __init__(self, estado: GrafoEstado) -> None:
        self._estado: GrafoEstado = estado

    @property
    def versao_log(self) -> int:
        """Versão atual do log refletida na projeção."""
        return self._estado.versao_log

    @property
    def total_nos(self) -> int:
        """Total de nós presentes na projeção."""
        return len(self._estado.nos)

    @property
    def total_arestas(self) -> int:
        """Total de arestas presentes na projeção."""
        return len(self._estado.arestas)

    def contem_no(self, id_no: str) -> bool:
        """Verifica se um nó está presente na projeção."""
        return self._estado.contem_no(id_no)

    def contem_aresta(self, id_aresta: str) -> bool:
        """Verifica se uma aresta está presente na projeção."""
        return self._estado.contem_aresta(id_aresta)

    def obter_no(self, id_no: str) -> NoGrafo | None:
        """Retorna o nó pelo seu ID ou None caso não exista."""
        return self._estado.nos.get(id_no)

    def obter_aresta(self, id_aresta: str) -> ArestaGrafo | None:
        """Retorna a aresta pelo ID ou None caso não exista."""
        return self._estado.arestas.get(id_aresta)

    def listar_todos_os_nos(self) -> tuple[NoGrafo, ...]:
        """Enumera todos os nós da projeção, evitando acesso ao estado interno."""
        return tuple(self._estado.nos.values())

    def listar_todas_as_arestas(self) -> tuple[ArestaGrafo, ...]:
        """Enumera todas as arestas da projeção, evitando acesso ao estado interno."""
        return tuple(self._estado.arestas.values())

    def listar_nos_por_tipo(self, tipo: TipoNo) -> list[NoGrafo]:
        """Filtra todos os nós de um determinado tipo da ontologia."""
        return [no for no in self._estado.nos.values() if no.tipo == tipo]

    def obter_arestas_saida(
        self,
        origem_id: str,
        tipo_aresta: TipoAresta | None = None,
    ) -> list[ArestaGrafo]:
        """Lista arestas partindo do nó de origem informado."""
        arestas = [a for a in self._estado.arestas.values() if a.origem_id == origem_id]
        if tipo_aresta is None:
            return arestas
        return [a for a in arestas if a.tipo == tipo_aresta]

    def obter_arestas_entrada(
        self,
        destino_id: str,
        tipo_aresta: TipoAresta | None = None,
    ) -> list[ArestaGrafo]:
        """Lista arestas incidindo no nó de destino informado."""
        arestas = [a for a in self._estado.arestas.values() if a.destino_id == destino_id]
        if tipo_aresta is None:
            return arestas
        return [a for a in arestas if a.tipo == tipo_aresta]

    def obter_vizinhos_1_salto(self, id_no: str) -> list[NoGrafo]:
        """Coleta nós vizinhos conectados diretamente em 1 salto (entrada ou saída)."""
        ids_vizinhos = self._coletar_ids_vizinhos(id_no)
        return [self._estado.nos[id_vizinho] for id_vizinho in sorted(ids_vizinhos) if id_vizinho in self._estado.nos]

    def _coletar_ids_vizinhos(self, id_no: str) -> frozenset[str]:
        """Reúne os identificadores ligados ao nó por qualquer direção de aresta."""
        saidas = {a.destino_id for a in self._estado.arestas.values() if a.origem_id == id_no}
        entradas = {a.origem_id for a in self._estado.arestas.values() if a.destino_id == id_no}
        return frozenset(saidas | entradas)

    def buscar_nos(
        self,
        termo: str,
        tipos: Sequence[TipoNo] | None = None,
    ) -> list[NoGrafo]:
        """Busca textual sobre rótulo e propriedades de nós filtrados por tipos."""
        termo_lower: str = termo.lower()
        resultado: list[NoGrafo] = []
        for no in self._estado.nos.values():
            if tipos is not None and no.tipo not in tipos:
                continue
            if self._no_corresponde_termo(no, termo_lower):
                resultado.append(no)
        return resultado

    def _no_corresponde_termo(self, no: NoGrafo, termo_lower: str) -> bool:
        """Verifica se o termo de busca está presente no nó."""
        if termo_lower in no.rotulo.lower():
            return True
        conteudo_props: str = str(no.propriedades).lower()
        return termo_lower in conteudo_props

    def obter_questoes_bloqueantes(self, id_task: str) -> list[NoGrafo]:
        """Retorna nós do tipo Question com aresta 'bloqueia' aberta para a Task."""
        arestas_bloqueio = self.obter_arestas_entrada(id_task, TipoAresta.BLOQUEIA)
        questoes: list[NoGrafo] = []
        for aresta in arestas_bloqueio:
            no_origem = self.obter_no(aresta.origem_id)
            if no_origem is None or no_origem.tipo != TipoNo.QUESTION:
                continue
            status = no_origem.obter_propriedade("status", StatusQuestion.ABERTA.value)
            if status == StatusQuestion.ABERTA.value:
                questoes.append(no_origem)
        return questoes

    def esta_bloqueada(self, id_task: str) -> bool:
        """Determina se uma Task possui alguma questão aberta bloqueante."""
        questoes_abertas = self.obter_questoes_bloqueantes(id_task)
        return len(questoes_abertas) > 0
