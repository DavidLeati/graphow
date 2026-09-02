"""Testes unitários dos modelos imutáveis NoGrafo, ArestaGrafo e GrafoEstado."""

import pytest

from graphow.core.models import ArestaGrafo, GrafoEstado, MetadadosTemporais, NoGrafo
from graphow.core.types import TipoAresta, TipoNo


def test_criacao_no_fluxo_nominal() -> None:
    """Testa criação nominal de NoGrafo e imutabilidade."""
    meta = MetadadosTemporais.agora()
    no = NoGrafo(id="task-1", tipo=TipoNo.TASK, rotulo="Planejar", propriedades={"status": "pendente"}, metadados=meta)
    assert no.id == "task-1"
    assert no.tipo == TipoNo.TASK
    assert no.obter_propriedade("status") == "pendente"
    assert no.obter_propriedade("inexistente", "fallback") == "fallback"


def test_no_imutabilidade_com_propriedades_edge_case() -> None:
    """Caso de borda: modificação imutável com_propriedades não altera objeto original."""
    no_original = NoGrafo(id="task-1", tipo=TipoNo.TASK, rotulo="Original", propriedades={"valor": 10})
    no_modificado = no_original.com_propriedades({"valor": 20, "novo": "abc"})

    assert no_original.propriedades["valor"] == 10
    assert "novo" not in no_original.propriedades
    assert no_modificado.propriedades["valor"] == 20
    assert no_modificado.propriedades["novo"] == "abc"


def test_no_frozen_dataclass_mutacao_direta_rejeitada_edge_case() -> None:
    """Caso de borda: tentativa de atribuição direta a campo congelado lança exceção."""
    no = NoGrafo(id="task-1", tipo=TipoNo.TASK, rotulo="Original")
    with pytest.raises(Exception):
        no.id = "outro-id"  # type: ignore[misc]


def test_serializacao_grafo_determinismo_edge_case() -> None:
    """Caso de borda: serialização JSON determinística é imune a ordem de inserção."""
    no1 = NoGrafo(id="b-no", tipo=TipoNo.TASK, rotulo="B", propriedades={"z": 1, "a": 2})
    no2 = NoGrafo(id="a-no", tipo=TipoNo.TASK, rotulo="A", propriedades={"x": 3})
    aresta = ArestaGrafo(id="e1", origem_id="a-no", destino_id="b-no", tipo=TipoAresta.DEPENDE_DE)

    # Inserção na ordem 1
    grafo1 = GrafoEstado(nos={"b-no": no1, "a-no": no2}, arestas={"e1": aresta}, versao_log=1)
    # Inserção na ordem 2
    grafo2 = GrafoEstado(nos={"a-no": no2, "b-no": no1}, arestas={"e1": aresta}, versao_log=1)

    assert grafo1.serializar_para_json() == grafo2.serializar_para_json()
