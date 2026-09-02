"""Testes unitários para modelos de patch e sanitização de segurança RFC 6902."""

import pytest

from graphow.core.exceptions import ErroPatchInvalido, ErroSegurancaPatch
from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    SanitizadorPatch,
)


def test_proposta_patch_criacao_nominal() -> None:
    """Testa criação nominal de PropostaPatch via DTO."""
    item = ItemPatch(op=OperacaoPatch.ADD, path="/nos/task-1", value={"id": "task-1", "tipo": "Task"})
    dados = DadosPropostaPatch(
        autor="planejador-1",
        papel=PapelAutor.PLANEJADOR,
        operacoes=[item],
        justificativa="Nova tarefa de desenvolvimento",
    )
    proposta = PropostaPatch.criar(dados)
    assert proposta.autor == "planejador-1"
    assert proposta.papel == PapelAutor.PLANEJADOR
    assert len(proposta.operacoes) == 1
    assert proposta.ramo_id == "main"


def test_sanitizador_rejeita_proto_pollution_no_path_edge_case() -> None:
    """Caso de borda: rejeição de __proto__ ou constructor no path."""
    item_invalido = ItemPatch(op=OperacaoPatch.ADD, path="/nos/__proto__/hack", value={"x": 1})
    with pytest.raises(ErroSegurancaPatch) as excinfo:
        SanitizadorPatch.sanitizar_item(item_invalido)
    assert "__proto__" in str(excinfo.value)


def test_sanitizador_rejeita_proto_pollution_recursivo_em_valor_edge_case() -> None:
    """Caso de borda: rejeição de injeção de atributo proibido dentro de objeto aninhado."""
    item_aninhado = ItemPatch(
        op=OperacaoPatch.ADD,
        path="/nos/task-1",
        value={"propriedades": {"dados": {"__class__": "Injected"}}},
    )
    with pytest.raises(ErroSegurancaPatch) as excinfo:
        SanitizadorPatch.sanitizar_item(item_aninhado)
    assert "__class__" in str(excinfo.value)


def test_sanitizador_rejeita_caminho_sem_barra_inicial_edge_case() -> None:
    """Caso de borda: caminho RFC 6902 que não começa com / é rejeitado."""
    item_sem_barra = ItemPatch(op=OperacaoPatch.ADD, path="nos/task-1", value={})
    with pytest.raises(ErroPatchInvalido):
        SanitizadorPatch.sanitizar_item(item_sem_barra)
