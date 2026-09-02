"""Ferramentas MCP de exclusão, restritas a sessões humanas pela política de identidade."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from graphow.core.types import TipoAresta
from graphow.kernel.patch_models import ItemPatch
from graphow.mcp.construcao_operacoes import montar_operacao_remover_aresta, montar_operacao_remover_no
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)
from graphow.projection.graph_view import GrafoView


class FerramentasExclusao:
    """Remoção individual, em lote e em cascata de elementos do grafo."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de exclusão aos seus executores."""
        return {
            "excluir_em_lote": self.excluir_em_lote,
            "excluir_projeto": self.excluir_projeto,
        }

    def excluir_em_lote(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Remove atomicamente uma coleção arbitrária de nós e arestas."""
        operacoes = self._montar_operacoes_remocao(
            argumentos.get("ids_nos", []),
            argumentos.get("ids_arestas", []),
        )
        if not operacoes:
            return {"sucesso": True, "mensagem": "Nenhum elemento a excluir", "versao_log": 0}
        pedido = PedidoSubmissaoMCP(
            operacoes=operacoes,
            justificativa=str(argumentos.get("justificativa", "Exclusao em lote via MCP")),
            ramo_id=extrair_ramo(dict(argumentos)),
        )
        return self._submissor.submeter_e_relatar(pedido)

    def _montar_operacoes_remocao(
        self,
        ids_nos: Sequence[Any],
        ids_arestas: Sequence[Any],
    ) -> tuple[ItemPatch, ...]:
        """Converte as listas de identificadores em operações de remoção."""
        remocoes_de_nos = [montar_operacao_remover_no(str(id_no)) for id_no in ids_nos]
        remocoes_de_arestas = [montar_operacao_remover_aresta(str(id_aresta)) for id_aresta in ids_arestas]
        return tuple(remocoes_de_nos + remocoes_de_arestas)

    def excluir_projeto(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Remove o projeto e, opcionalmente, todos os seus descendentes."""
        id_projeto = str(argumentos["id_projeto"])
        ramo = extrair_ramo(dict(argumentos))
        view = self._contexto.kernel.obter_view(ramo)
        if not view.contem_no(id_projeto):
            return {"sucesso": False, "erro": f"Projeto '{id_projeto}' nao encontrado"}

        remover_em_cascata = bool(argumentos.get("cascata", True))
        ids = self._coletar_descendentes(id_projeto, view) if remover_em_cascata else (id_projeto,)
        pedido = PedidoSubmissaoMCP(
            operacoes=tuple(montar_operacao_remover_no(id_no) for id_no in ids),
            justificativa=f"Exclusao de projeto {id_projeto}",
            ramo_id=ramo,
            identificadores_criados={"id_projeto": id_projeto},
        )
        resposta = self._submissor.submeter_e_relatar(pedido)
        resposta["total_removidos"] = len(ids)
        return resposta

    def _coletar_descendentes(self, id_projeto: str, view: GrafoView) -> tuple[str, ...]:
        """Percorre a hierarquia de navegação recolhendo tudo que pende do projeto."""
        setores = self._destinos_por_tipo(view, TipoAresta.CONTEM, (id_projeto,))
        sessoes = self._destinos_por_tipo(view, TipoAresta.CONTEM, setores)
        trabalho = self._destinos_por_tipo(view, TipoAresta.PRODUZ, sessoes)
        encadeados = (id_projeto,) + setores + sessoes + trabalho
        return tuple(dict.fromkeys(encadeados))

    def _destinos_por_tipo(
        self,
        view: GrafoView,
        tipo_aresta: TipoAresta,
        origens: Sequence[str],
    ) -> tuple[str, ...]:
        """Coleta os destinos das arestas de um tipo que partem das origens dadas."""
        origens_procuradas = frozenset(origens)
        return tuple(
            aresta.destino_id
            for aresta in view.listar_todas_as_arestas()
            if aresta.tipo == tipo_aresta and aresta.origem_id in origens_procuradas
        )
