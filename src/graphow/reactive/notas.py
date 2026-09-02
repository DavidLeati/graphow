"""Montagem das notas reativas: sempre ligadas à sessão e ao nó que as motivou.

O motor produzia Notes com zero arestas. Elas não apareciam na vista de ninguém
— nem do revisor sobre a tarefa, nem sobre a sessão, nem sobre o artefato — e só
eram encontráveis por busca textual. Uma reação que ninguém lê não é reação.
Ver achado A-10.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
import uuid

from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.projection.graph_view import GrafoView

ARESTAS_DE_ORIGEM_DE_SESSAO: frozenset[TipoAresta] = frozenset(
    {TipoAresta.PRODUZ, TipoAresta.CONTEM}
)


@dataclass(frozen=True)
class PedidoDeNota:
    """Tudo o que uma nota reativa precisa para nascer conectada."""

    prefixo: str
    rotulo: str
    id_alvo: str
    id_sessao: str
    autor: str
    papel: PapelAutor
    propriedades: Mapping[str, Any] = field(default_factory=dict)

    @property
    def identificador(self) -> str:
        """Identificador único e legível da nota a ser criada."""
        return f"{self.prefixo}-{uuid.uuid4()}"


def localizar_sessao_de(id_no: str, view: GrafoView) -> str | None:
    """Encontra a Sessao que produziu o nó, subindo uma aresta de origem."""
    for aresta in view.obter_arestas_entrada(id_no):
        if aresta.tipo not in ARESTAS_DE_ORIGEM_DE_SESSAO:
            continue
        origem = view.obter_no(aresta.origem_id)
        if origem is not None and origem.tipo == TipoNo.SESSAO:
            return origem.id
    return None


def montar_proposta_de_nota(pedido: PedidoDeNota) -> PropostaPatch:
    """Cria a nota, o vínculo com a sessão e a aresta que aponta para o alvo."""
    id_nota = pedido.identificador
    operacoes = (
        _operacao_criar_nota(id_nota, pedido),
        _operacao_produz(id_nota, pedido.id_sessao),
        _operacao_deriva_de(id_nota, pedido.id_alvo),
    )
    dados = DadosPropostaPatch(
        autor=pedido.autor,
        papel=pedido.papel,
        operacoes=operacoes,
        justificativa=f"Reacao automatica sobre {pedido.id_alvo}",
        origem=OrigemEvento.COMPORTAMENTO,
    )
    return PropostaPatch.criar(dados)


def _operacao_criar_nota(id_nota: str, pedido: PedidoDeNota) -> ItemPatch:
    """Operação de criação do nó Note com as propriedades do pedido."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_nota}",
        value={
            "id": id_nota,
            "tipo": TipoNo.NOTE.value,
            "rotulo": pedido.rotulo,
            "propriedades": {"id_alvo": pedido.id_alvo, **dict(pedido.propriedades)},
        },
    )


def _operacao_produz(id_nota: str, id_sessao: str) -> ItemPatch:
    """Aresta que pendura a nota na sessão em que o fato aconteceu."""
    id_aresta = f"produz-{id_nota}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={
            "id": id_aresta,
            "origem_id": id_sessao,
            "destino_id": id_nota,
            "tipo": TipoAresta.PRODUZ.value,
        },
    )


def _operacao_deriva_de(id_nota: str, id_alvo: str) -> ItemPatch:
    """Aresta que faz a nota aparecer na vista de quem olha o nó alvo."""
    id_aresta = f"deriva-{id_nota}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={
            "id": id_aresta,
            "origem_id": id_nota,
            "destino_id": id_alvo,
            "tipo": TipoAresta.DERIVA_DE.value,
        },
    )
