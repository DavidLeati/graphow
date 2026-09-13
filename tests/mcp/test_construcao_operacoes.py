"""Testes unitários para os construtores de operações JSON Patch das ferramentas MCP."""

from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import OperacaoPatch
from graphow.mcp.construcao_operacoes import (
    EspecificacaoAresta,
    EspecificacaoNo,
    gerar_identificador,
    montar_operacao_criar_aresta,
    montar_operacao_criar_no,
    montar_operacao_definir_propriedade,
    montar_operacao_remover_aresta,
    montar_operacao_remover_no,
)


def test_monta_operacao_de_criacao_de_no_nominal() -> None:
    """A operação carrega caminho, tipo e propriedades declaradas."""
    especificacao = EspecificacaoNo(
        id="task-1", tipo=TipoNo.TASK, rotulo="Escrever testes", propriedades={"status": "pendente"}
    )
    operacao = montar_operacao_criar_no(especificacao)
    assert operacao.op == OperacaoPatch.ADD
    assert operacao.path == "/nos/task-1"
    assert operacao.value == {
        "id": "task-1",
        "tipo": "Task",
        "rotulo": "Escrever testes",
        "propriedades": {"status": "pendente"},
    }


def test_monta_operacao_de_criacao_de_aresta_nominal() -> None:
    """A aresta gerada preserva origem, destino e tipo ontológico."""
    especificacao = EspecificacaoAresta(
        id="prod-1", origem_id="sess-1", destino_id="task-1", tipo=TipoAresta.PRODUZ
    )
    operacao = montar_operacao_criar_aresta(especificacao)
    assert operacao.path == "/arestas/prod-1"
    assert operacao.value["tipo"] == "produz"
    assert operacao.value["origem_id"] == "sess-1"


def test_propriedades_ausentes_viram_dicionario_vazio_edge_case() -> None:
    """Caso de borda: nó sem propriedades declara um dicionário vazio, não None."""
    operacao = montar_operacao_criar_no(EspecificacaoNo(id="n1", tipo=TipoNo.NOTE, rotulo="Nota"))
    assert operacao.value["propriedades"] == {}


def test_propriedades_originais_nao_sao_compartilhadas_edge_case() -> None:
    """Caso de borda: mutar o dicionário de origem não altera a operação já montada."""
    propriedades_originais = {"status": "pendente"}
    operacao = montar_operacao_criar_no(
        EspecificacaoNo(id="n1", tipo=TipoNo.TASK, rotulo="Tarefa", propriedades=propriedades_originais)
    )
    propriedades_originais["status"] = "concluido"
    assert operacao.value["propriedades"] == {"status": "pendente"}


def test_monta_operacoes_de_remocao_e_propriedade() -> None:
    """Remoções e definição de propriedade produzem os caminhos RFC 6902 esperados."""
    assert montar_operacao_remover_no("n1").path == "/nos/n1"
    assert montar_operacao_remover_no("n1").op == OperacaoPatch.REMOVE
    assert montar_operacao_remover_aresta("e1").path == "/arestas/e1"

    propriedade = montar_operacao_definir_propriedade("n1", "status", "concluido")
    assert propriedade.path == "/nos/n1/propriedades/status"
    assert propriedade.op == OperacaoPatch.REPLACE
    assert propriedade.value == "concluido"


def test_identificadores_gerados_sao_unicos_e_prefixados_edge_case() -> None:
    """Caso de borda: dois identificadores do mesmo prefixo nunca colidem."""
    primeiro = gerar_identificador("task")
    segundo = gerar_identificador("task")
    assert primeiro.startswith("task-")
    assert segundo.startswith("task-")
    assert primeiro != segundo
