"""Testes do escopo por Setor no canvas e da criação de contêiner já pendurado no pai."""

from graphow.core.types import TipoAresta
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.conversao_requisicoes import converter_novo_no
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController


def _montar_dois_setores() -> CanvasWebController:
    """Projeto com dois setores, cada um com uma sessão e uma tarefa."""
    ctrl = CanvasWebController(WriteKernel(InMemoryEventStore()))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))
    for sufixo in ("a", "b"):
        ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo=f"Setor {sufixo}", id_no=f"setor-{sufixo}", contido_em="proj"))
        ctrl.criar_no(
            RequisicaoNovoNo(tipo="Sessao", rotulo=f"Sessao {sufixo}", id_no=f"sess-{sufixo}", contido_em=f"setor-{sufixo}")
        )
        ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo=f"Tarefa {sufixo}", id_no=f"t-{sufixo}", sessao_id=f"sess-{sufixo}"))
    return ctrl


def test_escopo_por_setor_mostra_so_a_subarvore_do_setor_nominal() -> None:
    """Abrir um setor na tela traz o setor, as sessões dele e o trabalho delas."""
    canvas = _montar_dois_setores().obter_canvas(setor_id="setor-a")

    assert {no.id for no in canvas.nos} == {"setor-a", "sess-a", "t-a"}


def test_escopo_por_setor_nao_arrasta_o_projeto_nem_o_setor_vizinho_edge_case() -> None:
    """Caso de borda: a filiação só desce — o Projeto acima e o Setor ao lado ficam de fora."""
    ids = {no.id for no in _montar_dois_setores().obter_canvas(setor_id="setor-b").nos}

    assert "proj" not in ids
    assert "setor-a" not in ids
    assert "t-a" not in ids


def test_escopo_por_setor_mantem_as_arestas_internas_nominal() -> None:
    """As arestas de contenção e produção do setor seguem desenhadas no recorte."""
    canvas = _montar_dois_setores().obter_canvas(setor_id="setor-a")

    assert {(a.origem_id, a.destino_id, a.tipo) for a in canvas.arestas} == {
        ("setor-a", "sess-a", TipoAresta.CONTEM.value),
        ("sess-a", "t-a", TipoAresta.PRODUZ.value),
    }


def test_setor_inexistente_devolve_a_tela_vazia_edge_case() -> None:
    """Caso de borda: um setor que não existe não pode cair no grafo inteiro."""
    assert _montar_dois_setores().obter_canvas(setor_id="setor-fantasma").total_nos == 0


def test_escopo_por_sessao_mostra_a_sessao_e_o_trabalho_dela_nominal() -> None:
    """Abrir uma sessão traz ela e o que ela produziu — as sessões vizinhas ficam de fora."""
    canvas = _montar_dois_setores().obter_canvas(sessao_id="sess-a", projeto_id="proj")

    assert {no.id for no in canvas.nos} == {"sess-a", "t-a"}


def test_contido_em_cria_o_no_e_a_aresta_contem_no_mesmo_lote_nominal() -> None:
    """O Setor nasce pendurado no Projeto, sem uma segunda requisição que possa falhar."""
    ctrl = CanvasWebController(WriteKernel(InMemoryEventStore()))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))

    recibo = ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Setor", id_no="setor", contido_em="proj"))

    assert recibo.sucesso is True
    assert len(recibo.eventos_gerados) == 2
    arestas = ctrl.obter_canvas().arestas
    assert [(a.origem_id, a.destino_id, a.tipo) for a in arestas] == [("proj", "setor", TipoAresta.CONTEM.value)]


def test_par_invalido_de_contencao_recusa_o_no_junto_edge_case() -> None:
    """Caso de borda: se o portão recusa a aresta, o nó também não entra — nada de órfão."""
    ctrl = CanvasWebController(WriteKernel(InMemoryEventStore()))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))

    recibo = ctrl.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao", id_no="sess", contido_em="proj"))

    assert recibo.sucesso is False
    assert {no.id for no in ctrl.obter_canvas().nos} == {"proj"}


def test_conversao_le_o_contido_em_do_corpo_nominal() -> None:
    """O campo novo chega do JSON da interface até o DTO."""
    req = converter_novo_no({"tipo": "Setor", "rotulo": "S", "contido_em": "proj"})

    assert req.contido_em == "proj"
    assert converter_novo_no({"tipo": "Task", "rotulo": "T"}).contido_em is None
