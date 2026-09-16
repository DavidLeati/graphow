"""Testes da busca textual da interface sobre o grafo inteiro do ramo."""

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.conversao_requisicoes import converter_busca
from graphow.web.dto import RequisicaoBusca, RequisicaoNovoNo
from graphow.web.rest_busca_controller import BuscaWebController, extrair_trecho
from graphow.web.rest_canvas_controller import CanvasWebController


def _montar_busca() -> BuscaWebController:
    """Grafo com projeto, setor, uma sessão, duas tarefas e uma evidência que cita a palavra no texto."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    canvas.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))
    canvas.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Setor", id_no="setor", contido_em="proj"))
    canvas.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao", id_no="sess", contido_em="setor"))
    canvas.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Ingestao Binance", id_no="t-1", sessao_id="sess"))
    canvas.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Backtest", id_no="t-2", sessao_id="sess"))
    canvas.criar_no(
        RequisicaoNovoNo(
            tipo="Evidence",
            rotulo="Metricas",
            id_no="e-1",
            sessao_id="sess",
            propriedades={"pos_x": 10, "observacao": "Dados vindos da Binance sem vazamento"},
        )
    )
    return BuscaWebController(kernel)


def test_busca_ranqueia_rotulo_antes_de_propriedade_nominal() -> None:
    """O nó que carrega o termo no nome vem antes do que só o cita no texto."""
    resposta = _montar_busca().buscar(RequisicaoBusca(termo="binance"))

    assert resposta["sucesso"] is True
    assert [linha["id"] for linha in resposta["resultados"]] == ["t-1", "e-1"]
    assert resposta["total"] == 2
    assert resposta["truncado"] is False


def test_cada_linha_diz_a_sessao_e_o_trecho_onde_casou_nominal() -> None:
    """Sem a sessão a tela não sabe que contêiner abrir para mostrar o nó."""
    linhas = {linha["id"]: linha for linha in _montar_busca().buscar(RequisicaoBusca(termo="binance"))["resultados"]}

    assert linhas["t-1"]["sessao_id"] == "sess"
    assert linhas["t-1"]["trecho"] is None
    assert linhas["e-1"]["trecho"]["chave"] == "observacao"
    assert "Binance" in linhas["e-1"]["trecho"]["texto"]


def test_limite_corta_depois_do_ranking_e_avisa_edge_case() -> None:
    """Caso de borda: o corte vem com o total, para a tela dizer que há mais."""
    resposta = _montar_busca().buscar(RequisicaoBusca(termo="binance", limite=1))

    assert [linha["id"] for linha in resposta["resultados"]] == ["t-1"]
    assert resposta["total"] == 2
    assert resposta["truncado"] is True


def test_filtro_por_tipo_restringe_os_candidatos_nominal() -> None:
    """Pedir só evidências tira a tarefa da lista, mesmo casando no nome."""
    resposta = _montar_busca().buscar(RequisicaoBusca(termo="binance", tipos=("evidence",)))

    assert [linha["id"] for linha in resposta["resultados"]] == ["e-1"]


def test_tipo_desconhecido_e_recusado_com_o_nome_edge_case() -> None:
    """Caso de borda: um tipo fora da ontologia vira mensagem, não erro de servidor."""
    resposta = _montar_busca().buscar(RequisicaoBusca(termo="x", tipos=("Galaxia",)))

    assert resposta["sucesso"] is False
    assert "Galaxia" in resposta["mensagem"]


def test_coordenada_do_canvas_nao_vira_trecho_edge_case() -> None:
    """Caso de borda: `pos_x` casa com busca por número e não diz nada a quem lê."""
    no = NoGrafo(id="n", tipo=TipoNo.NOTE, rotulo="Nota", propriedades={"pos_x": 10, "texto": "valor 10 medido"})

    trecho = extrair_trecho(no, "10")

    assert trecho is not None
    assert trecho["chave"] == "texto"


def test_trecho_longo_ganha_reticencias_nas_pontas_edge_case() -> None:
    """Caso de borda: o trecho é uma janela, e a janela mostra que o texto continua."""
    texto = "a" * 200 + " alvo " + "b" * 200
    no = NoGrafo(id="n", tipo=TipoNo.NOTE, rotulo="Nota", propriedades={"texto": texto})

    trecho = extrair_trecho(no, "alvo")

    assert trecho is not None
    assert trecho["texto"].startswith("…")
    assert trecho["texto"].endswith("…")
    assert "alvo" in trecho["texto"]


def test_conversao_da_query_le_termo_tipos_e_limite_nominal() -> None:
    """A query da busca é lida sem subir socket algum."""
    req = converter_busca({"termo": ["dados"], "tipos": ["Task,Evidence"], "limite": ["7"], "ramo": ["exp"]})

    assert req == RequisicaoBusca(termo="dados", tipos=("Task", "Evidence"), limite=7, ramo_id="exp")
    assert converter_busca({}).limite == 20
