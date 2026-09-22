"""Testes unitários para o SchemaGate (Portão 1)."""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
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


def _validar_lote(operacao: ItemPatch, estado: GrafoEstado) -> ResultadoValidacao:
    """Submete uma operação isolada ao SchemaGate sobre o estado informado."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=[operacao])
    return SchemaGate().validar(PropostaPatch.criar(dados), estado)


def _estado_com_projeto_e_setor() -> GrafoEstado:
    """Grafo com um Projeto e um Setor, pontas válidas para uma aresta 'contem'."""
    return GrafoEstado(
        nos={
            "p1": NoGrafo(id="p1", tipo=TipoNo.PROJETO, rotulo="Proj"),
            "s1": NoGrafo(id="s1", tipo=TipoNo.SETOR, rotulo="Setor"),
        }
    )


def test_no_com_id_do_valor_diferente_do_caminho_e_recusado_edge_case() -> None:
    """Caso de borda: '/nos/nota' com 'id' 'orfa' nomeava um nó e criava outro.

    Os portões conferiam 'nota', pelo caminho, e o log gravava 'orfa', pelo
    valor. A recusa diz os dois ids para o autor refazer a operação.
    """
    operacao = ItemPatch(op=OperacaoPatch.ADD, path="/nos/nota", value={"id": "orfa", "tipo": TipoNo.NOTE.value})

    resultado = _validar_lote(operacao, GrafoEstado())

    assert resultado.aprovado is False
    assert resultado.portao_falha == "SchemaGate"
    assert resultado.modo == ModoFalhaMAST.CAMINHO_INVALIDO
    assert "'nota'" in (resultado.mensagem_erro or "")
    assert "'orfa'" in (resultado.mensagem_erro or "")
    assert dict(resultado.contexto_detalhado) == {"path": "/nos/nota", "id_caminho": "nota", "id_valor": "orfa"}


def test_aresta_com_id_do_valor_diferente_do_caminho_e_recusada_edge_case() -> None:
    """Caso de borda: a mesma divergência do lado das arestas.

    A antevisão do RoleGate registrava a aresta pelo id do caminho, e o
    acumulador a gravava pelo id do valor. O par Projeto -> Setor é válido:
    só o id está errado.
    """
    operacao = ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value={
        "id": "e2", "origem_id": "p1", "destino_id": "s1", "tipo": TipoAresta.CONTEM.value
    })

    resultado = _validar_lote(operacao, _estado_com_projeto_e_setor())

    assert resultado.aprovado is False
    assert resultado.modo == ModoFalhaMAST.CAMINHO_INVALIDO
    assert "'e1'" in (resultado.mensagem_erro or "")
    assert "'e2'" in (resultado.mensagem_erro or "")


@pytest.mark.parametrize(
    ("caminho", "valor"),
    [
        ("/nos/n1", {"tipo": TipoNo.NOTE.value}),
        ("/arestas/e1", {"origem_id": "p1", "destino_id": "s1", "tipo": TipoAresta.CONTEM.value}),
    ],
)
def test_valor_sem_id_segue_recusado_por_estrutura_incompleta_edge_case(caminho: str, valor: dict[str, str]) -> None:
    """Caso de borda: sem 'id' no valor não há o que comparar com o caminho.

    A recusa continua sendo a de campo obrigatório, e não um KeyError da
    comparação de ids.
    """
    operacao = ItemPatch(op=OperacaoPatch.ADD, path=caminho, value=valor)

    resultado = _validar_lote(operacao, _estado_com_projeto_e_setor())

    assert resultado.aprovado is False
    assert resultado.modo == ModoFalhaMAST.ESTRUTURA_INCOMPLETA


def _estado_com_no_e_aresta() -> GrafoEstado:
    """Grafo com a Note 'n1' e a aresta 'e1', alvos das formas de edição e remoção."""
    return GrafoEstado(
        nos={
            "s1": NoGrafo(id="s1", tipo=TipoNo.SESSAO, rotulo="Sessao"),
            "n1": NoGrafo(id="n1", tipo=TipoNo.NOTE, rotulo="Nota"),
        },
        arestas={"e1": ArestaGrafo(id="e1", origem_id="s1", destino_id="n1", tipo=TipoAresta.PRODUZ)},
    )


@pytest.mark.parametrize(
    ("op", "caminho"),
    [
        (OperacaoPatch.ADD, "/nos/n1/rotulo"),
        (OperacaoPatch.REPLACE, "/nos/n1/rotulo"),
        (OperacaoPatch.ADD, "/nos/n1/propriedades/k"),
        (OperacaoPatch.REPLACE, "/nos/n1/propriedades/k"),
        (OperacaoPatch.REMOVE, "/nos/n1/propriedades/k"),
        (OperacaoPatch.REMOVE, "/nos/n1"),
        (OperacaoPatch.REMOVE, "/arestas/e1"),
    ],
)
def test_formas_que_o_log_grava_como_dizem_sao_aceitas_nominal(op: OperacaoPatch, caminho: str) -> None:
    """As formas canônicas de edição e remoção seguem aceitas."""
    resultado = _validar_lote(ItemPatch(op=op, path=caminho, value="novo"), _estado_com_no_e_aresta())

    assert resultado.aprovado, resultado.mensagem_erro


@pytest.mark.parametrize(
    ("op", "caminho"),
    [
        (OperacaoPatch.TEST, "/nos/n1/propriedades/status"),
        (OperacaoPatch.MOVE, "/nos/n1/propriedades/status"),
        (OperacaoPatch.COPY, "/nos/n1/propriedades/status"),
        (OperacaoPatch.REPLACE, "/nos/n1"),
        (OperacaoPatch.REMOVE, "/nos/n1/rotulo"),
        (OperacaoPatch.REPLACE, "/nos/n1/tipo"),
        (OperacaoPatch.REPLACE, "/nos/n1/propriedades"),
        (OperacaoPatch.ADD, "/nos/n1/propriedades/k/sub"),
        (OperacaoPatch.REPLACE, "/arestas/e1"),
        (OperacaoPatch.REMOVE, "/arestas/e1/tipo"),
        (OperacaoPatch.ADD, "/arestas/e1/x"),
    ],
)
def test_formas_que_o_log_nao_grava_como_dizem_sao_recusadas_edge_case(op: OperacaoPatch, caminho: str) -> None:
    """Caso de borda: cada forma aqui virava no log outra coisa, ou nada, com recibo de sucesso.

    `test`, `move` e `copy` viravam escrita; `replace` no nó inteiro, uma
    propriedade com o nome do id; `remove` do rótulo gravava "None"; `replace`
    na aresta não gerava evento; e `remove` em '/arestas/e1/tipo' apagava a
    aresta inteira. A recusa diz as formas aceitas.
    """
    resultado = _validar_lote(ItemPatch(op=op, path=caminho, value="novo"), _estado_com_no_e_aresta())

    assert resultado.aprovado is False
    assert resultado.modo == ModoFalhaMAST.CAMINHO_INVALIDO
    assert dict(resultado.contexto_detalhado) == {"path": caminho, "op": op.value}
    assert "/nos/<id>/propriedades/<chave>" in (resultado.mensagem_erro or "")


def test_aresta_criada_duas_vezes_no_lote_e_recusada_edge_case() -> None:
    """Caso de borda: a segunda criação do mesmo id de aresta trocava a primeira no acumulador."""
    primeira = ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e9", value={
        "id": "e9", "origem_id": "p1", "destino_id": "s1", "tipo": TipoAresta.CONTEM.value
    })
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=[primeira, primeira])

    resultado = SchemaGate().validar(PropostaPatch.criar(dados), _estado_com_projeto_e_setor())

    assert resultado.aprovado is False
    assert resultado.modo == ModoFalhaMAST.ELEMENTO_JA_EXISTENTE
    assert resultado.contexto_detalhado["id"] == "e9"
