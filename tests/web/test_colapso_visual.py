"""Testes do recorte visual do canvas: colapso, escopo ativo e caminho crítico."""

from graphow.core.types import StatusTask, TipoAresta
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.colapso_visual import OpcoesDeRecorteVisual
from graphow.web.conversao_requisicoes import converter_opcoes_de_recorte
from graphow.web.dto import RequisicaoNovaAresta, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController


def _montar_projeto_completo() -> CanvasWebController:
    """Projeto com um setor, uma sessão e duas tarefas — uma aberta, uma fechada."""
    ctrl = CanvasWebController(WriteKernel(InMemoryEventStore()))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Setor", id_no="setor"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao", id_no="sess"))
    ctrl.criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="Aberta", id_no="t-aberta", propriedades={"status": StatusTask.PENDENTE.value})
    )
    ctrl.criar_no(
        RequisicaoNovoNo(tipo="Task", rotulo="Fechada", id_no="t-fechada", propriedades={"status": StatusTask.CONCLUIDO.value})
    )
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="proj", destino_id="setor", tipo=TipoAresta.CONTEM.value))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="setor", destino_id="sess", tipo=TipoAresta.CONTEM.value))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="sess", destino_id="t-aberta", tipo=TipoAresta.PRODUZ.value))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="sess", destino_id="t-fechada", tipo=TipoAresta.PRODUZ.value))
    return ctrl


def test_sem_opcoes_o_canvas_devolve_o_grafo_inteiro() -> None:
    """O padrão não pode esconder nada: recorte é sempre um pedido explícito."""
    canvas = _montar_projeto_completo().obter_canvas()

    assert canvas.total_nos == 5
    assert canvas.recorte["total_oculto"] == 0


def test_colapso_em_setor_esconde_sessoes_e_trabalho() -> None:
    """Colapsar no servidor é o que reduz o payload; no cliente seria cosmético."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="setor"))

    assert {no.id for no in canvas.nos} == {"proj", "setor"}
    assert canvas.recorte["total_oculto"] == 3
    assert canvas.recorte["colapsado_em"] == "setor"


def test_colapso_em_sessao_mantem_a_camada_de_navegacao_inteira() -> None:
    """Um setor com muitas sessões precisa do nível abaixo para ser navegável."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="sessao"))

    assert {no.id for no in canvas.nos} == {"proj", "setor", "sess"}


def test_super_no_carrega_o_agregado_da_propria_subarvore() -> None:
    """Sem o resumo, o super-nó esconde trabalho sem dizer quanto."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="setor"))

    setor = {no.id: no for no in canvas.nos}["setor"]
    assert setor.resumo is not None
    assert setor.resumo["tarefas_totais"] == 2
    assert setor.resumo["tarefas_abertas"] == 1


def test_escopo_ativo_esconde_o_que_esta_longe_do_trabalho_aberto() -> None:
    """A tarefa concluída sai da tela por distância, não por status."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(escopo_ativo=True, raio=0))

    ids = {no.id for no in canvas.nos}
    assert "t-aberta" in ids
    assert "t-fechada" not in ids


def test_nivel_de_colapso_desconhecido_e_ignorado_em_vez_de_esconder_tudo() -> None:
    """Query malformada não pode esvaziar a tela em silêncio."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="galaxia"))

    assert canvas.total_nos == 5
    assert canvas.recorte["filtros"] == []


def test_caminho_critico_sem_dependencia_declarada_nao_esvazia_a_tela() -> None:
    """Sem aresta de dependência a vista não tem o que mostrar: melhor mostrar tudo."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(caminho_critico=True))

    assert canvas.total_nos == 5
    assert canvas.recorte["caminho_critico"]["arestas_de_dependencia"] == 0


def test_arestas_ficam_restritas_aos_nos_que_sobraram() -> None:
    """Uma aresta apontando para nó oculto viraria linha solta no canvas."""
    canvas = _montar_projeto_completo().obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="setor"))

    assert canvas.total_arestas == 1
    assert canvas.arestas[0].origem_id == "proj"


def test_conversao_da_query_le_os_tres_recortes() -> None:
    """A leitura da query é pura e testável sem subir socket algum."""
    opcoes = converter_opcoes_de_recorte(
        {"colapsar": ["sessao"], "escopo": ["ativo"], "raio": ["2"], "vista": ["caminho_critico"]}
    )

    assert opcoes.nivel_de_colapso == "sessao"
    assert opcoes.escopo_ativo is True
    assert opcoes.raio == 2
    assert opcoes.caminho_critico is True


def test_raio_nao_numerico_cai_no_padrao() -> None:
    """Um raio inválido não pode derrubar a requisição do canvas."""
    assert converter_opcoes_de_recorte({"raio": ["abc"]}).raio == 1
