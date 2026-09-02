"""Conversão pura de payloads JSON da interface nos DTOs de requisição.

Estas funções não decidem identidade: autor e papel vêm da sessão do servidor,
nunca do corpo. Separá-las do despachante HTTP mantém o servidor com o tamanho
de um roteador e deixa a conversão testável sem subir socket algum.
"""

from collections.abc import Mapping
from typing import Any

from graphow.web.dto import (
    PosicaoNoCanvas,
    RequisicaoCriarFork,
    RequisicaoEdicaoNo,
    RequisicaoExclusaoLote,
    RequisicaoExclusaoProjeto,
    RequisicaoNovaAresta,
    RequisicaoNovoNo,
    RequisicaoSalvarLayout,
    RequisicaoSimularVista,
)

RAMO_PADRAO: str = "main"
CAMPOS_DE_POSICAO: frozenset[str] = frozenset({"id_no", "x", "y"})


def extrair_ramo(payload: Mapping[str, Any]) -> str:
    """Lê o ramo alvo do corpo, com o ramo principal como padrão."""
    return str(payload.get("ramo_id", RAMO_PADRAO))


def converter_novo_no(payload: Mapping[str, Any]) -> RequisicaoNovoNo:
    """Monta o pedido de criação de nó a partir do corpo recebido."""
    return RequisicaoNovoNo(
        tipo=str(payload.get("tipo", "Task")),
        rotulo=str(payload.get("rotulo", "Sem título")),
        id_no=payload.get("id_no"),
        sessao_id=payload.get("sessao_id"),
        propriedades=dict(payload.get("propriedades", {})),
        ramo_id=extrair_ramo(payload),
    )


def converter_nova_aresta(payload: Mapping[str, Any]) -> RequisicaoNovaAresta:
    """Monta o pedido de criação de aresta tipada."""
    return RequisicaoNovaAresta(
        origem_id=str(payload.get("origem_id", "")),
        destino_id=str(payload.get("destino_id", "")),
        tipo=str(payload.get("tipo", "decompoe")),
        id_aresta=payload.get("id_aresta"),
        ramo_id=extrair_ramo(payload),
    )


def converter_edicao_no(payload: Mapping[str, Any]) -> RequisicaoEdicaoNo:
    """Monta o pedido de edição de rótulo e propriedades de um nó."""
    return RequisicaoEdicaoNo(
        id_no=str(payload.get("id_no", "")),
        novas_propriedades=dict(payload.get("novas_propriedades", {})),
        novo_rotulo=payload.get("novo_rotulo"),
        ramo_id=extrair_ramo(payload),
    )


def converter_criar_fork(payload: Mapping[str, Any]) -> RequisicaoCriarFork:
    """Monta o pedido de bifurcação a partir de um ponto de corte."""
    return RequisicaoCriarFork(
        novo_ramo=str(payload.get("novo_ramo", "")),
        ramo_origem=str(payload.get("ramo_origem", RAMO_PADRAO)),
        evento_id_ponto_corte=payload.get("evento_id_ponto_corte"),
    )


def converter_simular_vista(payload: Mapping[str, Any]) -> RequisicaoSimularVista:
    """Monta o pedido do simulador de orçamento, onde o papel é uma pergunta."""
    return RequisicaoSimularVista(
        id_alvo=str(payload.get("id_alvo", "")),
        papel=str(payload.get("papel", "planejador")),
        orcamento_tokens=int(payload.get("orcamento_tokens", 1000)),
        ramo_id=extrair_ramo(payload),
    )


def converter_exclusao_lote(payload: Mapping[str, Any]) -> RequisicaoExclusaoLote:
    """Monta o pedido de exclusão atômica de vários elementos."""
    return RequisicaoExclusaoLote(
        ids_nos=tuple(payload.get("ids_nos", [])),
        ids_arestas=tuple(payload.get("ids_arestas", [])),
        ramo_id=extrair_ramo(payload),
    )


def converter_exclusao_projeto(payload: Mapping[str, Any]) -> RequisicaoExclusaoProjeto:
    """Monta o pedido de exclusão em cascata de um projeto."""
    return RequisicaoExclusaoProjeto(
        id_projeto=str(payload.get("id_projeto", "")),
        ramo_id=extrair_ramo(payload),
    )


def converter_salvar_layout(payload: Mapping[str, Any]) -> RequisicaoSalvarLayout:
    """Monta o pedido de persistência do arranjo visual do canvas."""
    return RequisicaoSalvarLayout(
        posicoes=converter_posicoes(payload.get("posicoes", [])),
        ramo_id=extrair_ramo(payload),
    )


def converter_posicoes(posicoes_brutas: Any) -> tuple[PosicaoNoCanvas, ...]:
    """Converte a lista recebida do canvas em coordenadas tipadas."""
    if not isinstance(posicoes_brutas, list):
        return ()
    return tuple(
        PosicaoNoCanvas(id_no=str(item["id_no"]), x=int(item["x"]), y=int(item["y"]))
        for item in posicoes_brutas
        if isinstance(item, Mapping) and CAMPOS_DE_POSICAO <= set(item)
    )
