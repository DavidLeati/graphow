"""Testes para a persistência do arranjo visual do canvas no grafo."""

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.types import PapelAutor
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.write_kernel import WriteKernel
from graphow.web.dto import PosicaoNoCanvas, RequisicaoNovoNo, RequisicaoSalvarLayout
from graphow.web.rest_canvas_controller import CanvasWebController


def _preparar_canvas() -> tuple[CanvasWebController, WriteKernel, str]:
    """Cria um controlador com um nó já posicionável no canvas."""
    kernel = montar_kernel_em_memoria()
    controlador = CanvasWebController(kernel)
    recibo = controlador.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Tarefa", id_no="task-1"))
    assert recibo.sucesso is True
    return controlador, kernel, "task-1"


def test_layout_salvo_vira_propriedade_do_no_nominal() -> None:
    """As coordenadas passam a viver no grafo, não apenas no navegador."""
    controlador, kernel, id_task = _preparar_canvas()

    recibo = controlador.salvar_layout(
        RequisicaoSalvarLayout(posicoes=(PosicaoNoCanvas(id_no=id_task, x=340, y=120),))
    )
    assert recibo.sucesso is True

    no = kernel.obter_view().obter_no(id_task)
    assert no is not None
    assert no.obter_propriedade("pos_x") == 340
    assert no.obter_propriedade("pos_y") == 120


def test_layout_persistido_sobrevive_ao_replay_nominal() -> None:
    """O arranjo é histórico como qualquer outra mutação: o replay o reproduz."""
    controlador, kernel, id_task = _preparar_canvas()
    controlador.salvar_layout(
        RequisicaoSalvarLayout(posicoes=(PosicaoNoCanvas(id_no=id_task, x=10, y=20),))
    )

    from graphow.projection.reducer import GrafoReducer

    reconstruido = GrafoReducer.reconstruir(kernel.repositorio.ler_eventos("main"))
    assert reconstruido.nos[id_task].obter_propriedade("pos_x") == 10


def test_layout_nao_polui_o_contexto_do_agente_edge_case() -> None:
    """Caso de borda: as coordenadas ficam no grafo mas fora do orçamento do agente."""
    controlador, kernel, id_task = _preparar_canvas()
    controlador.salvar_layout(
        RequisicaoSalvarLayout(posicoes=(PosicaoNoCanvas(id_no=id_task, x=999, y=888),))
    )

    vista = MaterializadorContexto().materializar(
        RequisicaoVista(id_alvo=id_task, papel=PapelAutor.EXECUTOR), kernel.obter_view()
    )
    assert "pos_x" not in vista.conteudo_formatado
    assert "999" not in vista.conteudo_formatado


def test_posicao_de_no_inexistente_e_ignorada_edge_case() -> None:
    """Caso de borda: coordenadas de nós já removidos não geram operação."""
    controlador, kernel, id_task = _preparar_canvas()
    total_antes = len(kernel.repositorio.ler_eventos("main"))

    recibo = controlador.salvar_layout(
        RequisicaoSalvarLayout(posicoes=(PosicaoNoCanvas(id_no="no-fantasma", x=1, y=2),))
    )
    assert recibo.sucesso is True
    assert len(kernel.repositorio.ler_eventos("main")) == total_antes


def test_layout_vazio_nao_gera_evento_edge_case() -> None:
    """Caso de borda: salvar um arranjo vazio não escreve no log."""
    controlador, kernel, _ = _preparar_canvas()
    total_antes = len(kernel.repositorio.ler_eventos("main"))

    recibo = controlador.salvar_layout(RequisicaoSalvarLayout(posicoes=()))
    assert recibo.sucesso is True
    assert len(kernel.repositorio.ler_eventos("main")) == total_antes


def test_reenviar_a_mesma_posicao_nao_gera_evento_edge_case() -> None:
    """Caso de borda: coordenada que não mudou não vira evento no log.

    O canvas manda o mapa inteiro a cada arrasto. Sem esta poda, mover um nó
    gravaria todos os outros, e cada gravação viraria uma notificação SSE — o
    log real chegou a 98% de escrita de posição por causa disso.
    """
    controlador, kernel, id_task = _preparar_canvas()
    posicoes = (PosicaoNoCanvas(id_no=id_task, x=340, y=120),)
    controlador.salvar_layout(RequisicaoSalvarLayout(posicoes=posicoes))
    total_apos_primeira = len(kernel.repositorio.ler_eventos("main"))

    recibo = controlador.salvar_layout(RequisicaoSalvarLayout(posicoes=posicoes))

    assert recibo.sucesso is True
    assert len(kernel.repositorio.ler_eventos("main")) == total_apos_primeira


def test_arrastar_um_no_nao_regrava_os_vizinhos_edge_case() -> None:
    """Caso de borda: só o nó que se moveu entra no log, não o mapa inteiro."""
    controlador, kernel, id_task = _preparar_canvas()
    assert controlador.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Outra", id_no="task-2")).sucesso
    inicial = (
        PosicaoNoCanvas(id_no=id_task, x=10, y=20),
        PosicaoNoCanvas(id_no="task-2", x=310, y=20),
    )
    controlador.salvar_layout(RequisicaoSalvarLayout(posicoes=inicial))
    total_antes = len(kernel.repositorio.ler_eventos("main"))

    movido = (
        PosicaoNoCanvas(id_no=id_task, x=10, y=170),
        PosicaoNoCanvas(id_no="task-2", x=310, y=20),
    )
    controlador.salvar_layout(RequisicaoSalvarLayout(posicoes=movido))

    eventos = kernel.repositorio.ler_eventos("main")[total_antes:]
    alterados = {evento.payload["id"] for evento in eventos}
    assert alterados == {id_task}
