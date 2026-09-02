"""Construtores de operações JSON Patch reutilizados pelas ferramentas MCP."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
import uuid

from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch


@dataclass(frozen=True)
class EspecificacaoNo:
    """Descrição imutável de um nó a ser criado no grafo."""

    id: str
    tipo: TipoNo
    rotulo: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EspecificacaoAresta:
    """Descrição imutável de uma aresta tipada a ser criada no grafo."""

    id: str
    origem_id: str
    destino_id: str
    tipo: TipoAresta


def gerar_identificador(prefixo: str) -> str:
    """Gera um identificador curto e legível para um novo elemento do grafo."""
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def montar_operacao_criar_no(especificacao: EspecificacaoNo) -> ItemPatch:
    """Monta a operação RFC 6902 de criação de um nó tipado."""
    payload: dict[str, Any] = {
        "id": especificacao.id,
        "tipo": especificacao.tipo.value,
        "rotulo": especificacao.rotulo,
        "propriedades": dict(especificacao.propriedades),
    }
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{especificacao.id}", value=payload)


def montar_operacao_criar_aresta(especificacao: EspecificacaoAresta) -> ItemPatch:
    """Monta a operação RFC 6902 de criação de uma aresta tipada."""
    payload: dict[str, Any] = {
        "id": especificacao.id,
        "origem_id": especificacao.origem_id,
        "destino_id": especificacao.destino_id,
        "tipo": especificacao.tipo.value,
    }
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{especificacao.id}", value=payload)


def montar_operacao_remover_no(id_no: str) -> ItemPatch:
    """Monta a operação RFC 6902 de remoção de um nó."""
    return ItemPatch(op=OperacaoPatch.REMOVE, path=f"/nos/{id_no}")


def montar_operacao_remover_aresta(id_aresta: str) -> ItemPatch:
    """Monta a operação RFC 6902 de remoção de uma aresta."""
    return ItemPatch(op=OperacaoPatch.REMOVE, path=f"/arestas/{id_aresta}")


def montar_operacao_definir_propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """Monta a operação RFC 6902 que define uma propriedade de um nó existente."""
    return ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)
