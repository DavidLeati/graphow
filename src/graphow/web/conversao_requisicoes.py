"""Conversão pura de payloads JSON da interface nos DTOs de requisição.

Estas funções não decidem identidade: autor e papel vêm da sessão do servidor,
nunca do corpo. Separá-las do despachante HTTP mantém o servidor com o tamanho
de um roteador e deixa a conversão testável sem subir socket algum.
"""

from collections.abc import Mapping
from typing import Any

from graphow.projection.working_set import RAIO_PADRAO
from graphow.web.colapso_visual import OpcoesDeRecorteVisual
from graphow.web.dto import (
    DadosCanvasVisual,
    PosicaoNoCanvas,
    RequisicaoBusca,
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
LIMITE_PADRAO_DA_BUSCA_WEB: int = 20


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
        contido_em=payload.get("contido_em"),
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


def converter_opcoes_de_recorte(params: Mapping[str, Any]) -> OpcoesDeRecorteVisual:
    """Lê da query os três recortes visuais do canvas.

    Valor fora do vocabulário não vira erro: ele é ignorado e a tela recebe o
    grafo completo. Uma query malformada não deve esconder nós em silêncio.
    """
    return OpcoesDeRecorteVisual(
        colapsar_em=_primeiro(params, "colapsar"),
        escopo_ativo=_primeiro(params, "escopo") == "ativo",
        raio=_inteiro_ou_padrao(_primeiro(params, "raio"), RAIO_PADRAO),
        caminho_critico=_primeiro(params, "vista") == "caminho_critico",
    )


def converter_busca(params: Mapping[str, Any]) -> RequisicaoBusca:
    """Lê da query o termo, os tipos separados por vírgula e o limite da busca."""
    return RequisicaoBusca(
        termo=_primeiro(params, "termo"),
        tipos=tuple(tipo for tipo in _primeiro(params, "tipos").split(",") if tipo.strip()),
        limite=_inteiro_ou_padrao(_primeiro(params, "limite"), LIMITE_PADRAO_DA_BUSCA_WEB),
        ramo_id=_primeiro(params, "ramo") or RAMO_PADRAO,
    )


def _primeiro(params: Mapping[str, Any], chave: str) -> str:
    """Primeiro valor textual da chave na query, ou string vazia."""
    valores = params.get(chave)
    if not valores:
        return ""
    return str(valores[0]) if isinstance(valores, (list, tuple)) else str(valores)


def _inteiro_ou_padrao(bruto: str, padrao: int) -> int:
    """Converte o texto em inteiro, caindo no padrão quando ele não é um número."""
    try:
        return int(bruto)
    except ValueError:
        return padrao


def serializar_canvas(dados: DadosCanvasVisual) -> dict[str, Any]:
    """Converte o DTO do canvas no dicionário que a interface consome."""
    return {
        "ramo_id": dados.ramo_id,
        "versao_log": dados.versao_log,
        "total_nos": dados.total_nos,
        "total_arestas": dados.total_arestas,
        "nos": [no.__dict__ for no in dados.nos],
        "arestas": [aresta.__dict__ for aresta in dados.arestas],
        "recorte": dict(dados.recorte),
    }
