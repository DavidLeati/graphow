"""Testes da marcação de decisões substituídas e da proveniência nas linhas."""

from graphow.context.secoes import (
    MARCA_DE_CONTEUDO_NAO_CONFIAVEL,
    PrioridadeRetencao,
    anotar_ordem,
    formatar_no_em_linha,
)
from graphow.context.substituicao import identificar_substituta, montar_secao_de_decisoes
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog, ProvenienciaNo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _decisao(id_no: str, autor: str = "david", papel: str = PapelAutor.HUMANO.value) -> NoGrafo:
    """Decision de teste com a proveniência informada."""
    return NoGrafo(
        id=id_no,
        tipo=TipoNo.DECISION,
        rotulo=f"Decisao {id_no}",
        proveniencia=ProvenienciaNo(autor=autor, papel=papel),
    )


def _view_com_substituicao() -> GrafoView:
    """Grafo em que `d-nova` substitui `d-antiga`."""
    nos = {"d-antiga": _decisao("d-antiga"), "d-nova": _decisao("d-nova")}
    arestas = {
        "sub-1": ArestaGrafo("sub-1", "d-nova", "d-antiga", TipoAresta.SUBSTITUI),
    }
    return GrafoView(GrafoEstado(nos=nos, arestas=arestas))


def test_identifica_a_decisao_vigente_nominal() -> None:
    """A aresta `substitui` deixa de ser só travessia e passa a apontar a vigente."""
    view = _view_com_substituicao()

    assert identificar_substituta("d-antiga", view) == "d-nova"
    assert identificar_substituta("d-nova", view) is None


def test_decisao_substituida_aparece_marcada_e_por_ultimo_nominal() -> None:
    """O executor via as duas lado a lado sem saber qual valia."""
    view = _view_com_substituicao()
    decisoes = [view.obter_no("d-antiga"), view.obter_no("d-nova")]

    secao = montar_secao_de_decisoes(decisoes, view, (3, PrioridadeRetencao.DECISOES))

    assert secao.ids_incluidos == ("d-nova", "d-antiga")
    assert "SUBSTITUIDA por d-nova" in secao.linhas[1]
    assert "SUBSTITUIDA" not in secao.linhas[0]


def test_linha_carrega_autor_e_papel_nominal() -> None:
    """Autor e papel estavam no log e em nenhuma linha da vista."""
    linha = formatar_no_em_linha(_decisao("d1", autor="agente-x", papel="executor"))

    assert "(por agente-x (executor))" in linha


def test_evidencia_de_agente_recebe_marca_de_desconfianca_nominal() -> None:
    """Conteúdo trazido por ferramenta não pode chegar com autoridade de humano."""
    evidencia = NoGrafo(
        id="ev-1",
        tipo=TipoNo.EVIDENCE,
        rotulo="Saida do benchmark",
        proveniencia=ProvenienciaNo(autor="agente-x", papel=PapelAutor.EXECUTOR.value),
    )

    assert MARCA_DE_CONTEUDO_NAO_CONFIAVEL in formatar_no_em_linha(evidencia)


def test_evidencia_escrita_pelo_humano_nao_recebe_marca_edge_case() -> None:
    """Caso de borda: o que o humano escreveu não é conteúdo externo."""
    evidencia = NoGrafo(
        id="ev-2",
        tipo=TipoNo.EVIDENCE,
        rotulo="Medicao conferida",
        proveniencia=ProvenienciaNo(autor="david", papel=PapelAutor.HUMANO.value),
    )

    assert MARCA_DE_CONTEUDO_NAO_CONFIAVEL not in formatar_no_em_linha(evidencia)


def test_no_sem_proveniencia_nao_ganha_sufixo_edge_case() -> None:
    """Caso de borda: nó construído fora do log não inventa autoria."""
    assert formatar_no_em_linha(NoGrafo("n1", TipoNo.NOTE, "Nota")) == "- [n1] Nota"


def test_linha_carrega_a_posicao_do_no_no_log_nominal() -> None:
    """O agente lia uma lista sem saber qual nó veio antes de qual."""
    no = NoGrafo("d1", TipoNo.DECISION, "Decisao", ordem=OrdemNoLog(seq_criacao=12, seq_atualizacao=12))

    assert "(log #12)" in formatar_no_em_linha(no)


def test_no_sem_sequencia_conhecida_nao_ganha_ordem_inventada_edge_case() -> None:
    """Caso de borda: sem posição no log, a linha cala — não estima uma."""
    assert anotar_ordem(NoGrafo("n1", TipoNo.NOTE, "Nota")) == ""
