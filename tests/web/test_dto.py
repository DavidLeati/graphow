"""Testes unitários para validação de imutabilidade e integridade dos DTOs Web."""

from dataclasses import FrozenInstanceError
import pytest

from graphow.web.dto import (
    DadosArestaVisual,
    DadosCanvasVisual,
    DadosNoVisual,
    RequisicaoNovoNo,
    RespostaReciboWeb,
)


def test_dados_no_visual_fluxo_nominal() -> None:
    """Valida instanciação e leitura de atributos do DadosNoVisual."""
    dto = DadosNoVisual(
        id="task-1",
        tipo="Task",
        rotulo="Implementar UI",
        propriedades={"status": "em_andamento"},
        esta_bloqueado=False,
    )
    assert dto.id == "task-1"
    assert dto.tipo == "Task"
    assert dto.rotulo == "Implementar UI"
    assert dto.propriedades["status"] == "em_andamento"
    assert dto.esta_bloqueado is False


def test_imutabilidade_dto_edge_case_alteracao_proibida() -> None:
    """Valida que DTOs imutáveis disparam FrozenInstanceError em tentativas de mutação."""
    dto = DadosArestaVisual(id="a-1", origem_id="n-1", destino_id="n-2", tipo="decompoe")
    with pytest.raises(FrozenInstanceError):
        dto.tipo = "bloqueia"  # type: ignore[misc]


def test_valores_padrao_dto_edge_case_defaults() -> None:
    """Valida valores de fallback e coleções padrão vazias em DTOs."""
    req = RequisicaoNovoNo(tipo="Goal", rotulo="Objetivo Raiz")
    assert not hasattr(req, "autor"), "a identidade da escrita e da sessao, nao do corpo"
    assert not hasattr(req, "papel"), "a identidade da escrita e da sessao, nao do corpo"
    assert req.ramo_id == "main"
    assert req.sessao_id is None
    assert len(req.propriedades) == 0

    recibo = RespostaReciboWeb(sucesso=True, mensagem="OK")
    assert recibo.versao_log == 0
    assert len(recibo.eventos_gerados) == 0


def test_dados_canvas_visual_agregacao_completa() -> None:
    """Valida agregação de nós e arestas no DadosCanvasVisual."""
    no = DadosNoVisual(id="t-1", tipo="Task", rotulo="Tarefa 1")
    aresta = DadosArestaVisual(id="e-1", origem_id="s-1", destino_id="t-1", tipo="produz")
    canvas = DadosCanvasVisual(
        ramo_id="main",
        versao_log=10,
        total_nos=1,
        total_arestas=1,
        nos=(no,),
        arestas=(aresta,),
    )
    assert canvas.total_nos == 1
    assert canvas.nos[0].id == "t-1"
    assert canvas.arestas[0].tipo == "produz"
