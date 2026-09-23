"""Testes da medição de escala: o fechamento no rollup precisa ter custo medido."""

from graphow.avaliacao.escala import MedidorDeEscala, medir_escala
from graphow.avaliacao.tarefas_gravadas import montar_cenario_gravado
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def test_relatorio_de_escala_mede_o_rollup_e_o_panorama_da_raiz_nominal() -> None:
    """As duas medidas que decidem se o fechamento pode viajar no rollup."""
    relatorio = medir_escala(montar_cenario_gravado())

    assert relatorio.milissegundos_do_rollup >= 0.0
    assert relatorio.tokens_do_panorama_da_raiz > 0
    texto = "\n".join(relatorio.formatar())
    assert "Rollup por commit" in texto
    assert "Panorama da raiz" in texto


def test_descida_guiada_parte_do_projeto_com_trabalho_aberto_edge_case() -> None:
    """Caso de borda: partir do primeiro Projeto media a descida num projeto vazio e inflava o fator."""
    nos = {
        "p-vazio": NoGrafo("p-vazio", TipoNo.PROJETO, "Vazio"),
        "p-ativo": NoGrafo("p-ativo", TipoNo.PROJETO, "Ativo"),
        "s": NoGrafo("s", TipoNo.SETOR, "Setor"),
        "se": NoGrafo("se", TipoNo.SESSAO, "Sessao"),
        "t": NoGrafo("t", TipoNo.TASK, "Tarefa", {"status": "pendente"}),
    }
    arestas = {
        "c1": ArestaGrafo("c1", "p-ativo", "s", TipoAresta.CONTEM),
        "c2": ArestaGrafo("c2", "s", "se", TipoAresta.CONTEM),
        "p1": ArestaGrafo("p1", "se", "t", TipoAresta.PRODUZ),
    }
    view = GrafoView(GrafoEstado(nos=nos, arestas=arestas))

    assert MedidorDeEscala(montar_cenario_gravado())._encontrar_raiz(view) == "p-ativo"
