"""Testes unitários para a exploração limitada do subgrafo."""

from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _no(id_no: str, tipo: TipoNo = TipoNo.TASK) -> NoGrafo:
    """Cria um nó mínimo do tipo informado."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no)


def _aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Cria uma aresta tipada entre dois nós."""
    return ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo)


def _view_em_cadeia() -> GrafoView:
    """Monta goal -> t1 -> t2 -> t3 por arestas de decomposição."""
    nos = {
        "goal": _no("goal", TipoNo.GOAL),
        "t1": _no("t1"),
        "t2": _no("t2"),
        "t3": _no("t3"),
        "solto": _no("solto", TipoNo.NOTE),
    }
    arestas = {
        "d1": _aresta("d1", "goal", "t1", TipoAresta.DECOMPOE),
        "d2": _aresta("d2", "t1", "t2", TipoAresta.DECOMPOE),
        "d3": _aresta("d3", "t2", "t3", TipoAresta.DECOMPOE),
    }
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def test_percorre_saida_ate_o_limite_de_saltos_nominal() -> None:
    """A travessia alcança três níveis e ignora o que estiver além do raio."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    pedido = PedidoExploracao(
        id_alvo="goal",
        tipos_de_aresta=frozenset({TipoAresta.DECOMPOE}),
        direcao=DirecaoTravessia.SAIDA,
        saltos_maximos=3,
    )
    assert {no.id for no in explorador.coletar_alcancaveis(pedido)} == {"t1", "t2", "t3"}


def test_raio_menor_reduz_o_alcance_nominal() -> None:
    """Limitar os saltos limita o subgrafo devolvido."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    pedido = PedidoExploracao(
        id_alvo="goal",
        tipos_de_aresta=frozenset({TipoAresta.DECOMPOE}),
        saltos_maximos=1,
    )
    assert {no.id for no in explorador.coletar_alcancaveis(pedido)} == {"t1"}


def test_percorre_entrada_para_encontrar_ancestrais_nominal() -> None:
    """A travessia inversa sobe a hierarquia a partir da folha."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    pedido = PedidoExploracao(
        id_alvo="t3",
        tipos_de_aresta=frozenset({TipoAresta.DECOMPOE}),
        direcao=DirecaoTravessia.ENTRADA,
    )
    assert {no.id for no in explorador.coletar_alcancaveis(pedido)} == {"t2", "t1", "goal"}


def test_alvo_nunca_aparece_no_proprio_resultado_edge_case() -> None:
    """Caso de borda: o alvo é excluído mesmo quando um ciclo o realcança."""
    nos = {"a": _no("a"), "b": _no("b")}
    arestas = {
        "ida": _aresta("ida", "a", "b", TipoAresta.DEPENDE_DE),
        "volta": _aresta("volta", "b", "a", TipoAresta.DEPENDE_DE),
    }
    explorador = ExploradorSubgrafo(GrafoView(GrafoEstado(nos=nos, arestas=arestas)))
    pedido = PedidoExploracao(id_alvo="a", tipos_de_aresta=frozenset({TipoAresta.DEPENDE_DE}))
    assert {no.id for no in explorador.coletar_alcancaveis(pedido)} == {"b"}


def test_tipo_de_aresta_fora_do_filtro_nao_e_percorrido_edge_case() -> None:
    """Caso de borda: arestas de outro tipo não abrem caminho na travessia."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    pedido = PedidoExploracao(id_alvo="goal", tipos_de_aresta=frozenset({TipoAresta.BLOQUEIA}))
    assert explorador.coletar_alcancaveis(pedido) == ()


def test_no_isolado_nao_alcanca_ninguem_edge_case() -> None:
    """Caso de borda: um nó sem arestas devolve exploração vazia."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    pedido = PedidoExploracao(id_alvo="solto", tipos_de_aresta=frozenset({TipoAresta.DECOMPOE}))
    assert explorador.coletar_alcancaveis(pedido) == ()


def test_origens_diretas_filtram_por_tipo_de_aresta() -> None:
    """A consulta de origens diretas respeita o tipo pedido."""
    explorador = ExploradorSubgrafo(_view_em_cadeia())
    origens = explorador.coletar_origens_diretas("t1", TipoAresta.DECOMPOE)
    assert [no.id for no in origens] == ["goal"]
    assert explorador.coletar_origens_diretas("t1", TipoAresta.ESCOPA) == ()
