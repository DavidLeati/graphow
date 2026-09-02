"""Testes unitários para o SchemaGate (Portão 1)."""

from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)
from graphow.kernel.schema_gate import SchemaGate


def test_schema_gate_criacao_no_e_aresta_nominal() -> None:
    """Testa aprovação de nós e arestas válidos pela ontologia."""
    gate = SchemaGate()
    estado = GrafoEstado()
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/p1", value={"id": "p1", "tipo": TipoNo.PROJETO.value, "rotulo": "Proj"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/s1", value={"id": "s1", "tipo": TipoNo.SETOR.value, "rotulo": "Setor"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value={
                "id": "e1", "origem_id": "p1", "destino_id": "s1", "tipo": TipoAresta.CONTEM.value
            }),
        ],
    )
    res: ResultadoValidacao = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is True


def test_schema_gate_rejeita_tipo_no_invalido_edge_case() -> None:
    """Caso de borda: tipo de nó inexistente na ontologia é rejeitado."""
    gate = SchemaGate()
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/inv", value={"id": "inv", "tipo": "TipoFantasma"}),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), GrafoEstado())
    assert res.aprovado is False
    assert "Tipo de nó inválido" in str(res.mensagem_erro)


def test_schema_gate_rejeita_conexao_aresta_invalida_edge_case() -> None:
    """Caso de borda: tentativa de ligar Goal diretamente a Run com aresta 'contem' é rejeitada."""
    gate = SchemaGate()
    estado = GrafoEstado(
        nos={
            "g1": NoGrafo(id="g1", tipo=TipoNo.GOAL, rotulo="Goal"),
            "r1": NoGrafo(id="r1", tipo=TipoNo.RUN, rotulo="Run"),
        }
    )
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e_invalida", value={
                "id": "e_invalida", "origem_id": "g1", "destino_id": "r1", "tipo": TipoAresta.CONTEM.value
            }),
        ],
    )
    res = gate.validar(PropostaPatch.criar(dados), estado)
    assert res.aprovado is False
    assert "não permite conexão" in str(res.mensagem_erro)


def _validar_caminho(caminho: str) -> ResultadoValidacao:
    """Submete uma criação no caminho informado a um grafo vazio."""
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[ItemPatch(op=OperacaoPatch.ADD, path=caminho, value={"id": "", "tipo": TipoNo.SESSAO.value})],
    )
    return SchemaGate().validar(PropostaPatch.criar(dados), GrafoEstado())


def test_caminho_sem_identificador_recusa_em_vez_de_estourar_edge_case() -> None:
    """Caso de borda: '/nos/' com id vazio terminava em IndexError, não em recusa.

    Era o que acontecia quando o hook chamava `graphow harness --sessao ""`.
    Ver defeito V-02.
    """
    resultado = _validar_caminho("/nos/")

    assert not resultado.aprovado
    assert resultado.portao_falha == "SchemaGate"
    assert "nao identifica" in (resultado.mensagem_erro or "")


def test_caminho_de_aresta_sem_identificador_tambem_recusa_edge_case() -> None:
    """Caso de borda: a mesma lacuna existia do lado das arestas."""
    resultado = _validar_caminho("/arestas/")

    assert not resultado.aprovado
    assert "nao identifica" in (resultado.mensagem_erro or "")
