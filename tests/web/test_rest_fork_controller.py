"""Testes unitários para o ForkWebController."""

from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.web.dto import RequisicaoCriarFork, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_fork_controller import ForkWebController


def test_criar_fork_e_diff_fluxo_nominal() -> None:
    """Valida bifurcação de ramo e cálculo de diff com nós adicionados."""
    kernel = montar_kernel_em_memoria()
    canvas_ctrl = CanvasWebController(kernel)
    fork_ctrl = ForkWebController(kernel)

    # Cria nó inicial no main
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Goal Base", id_no="g-base", ramo_id="main"))

    # Cria fork a partir do main
    rec_fork = fork_ctrl.criar_fork(RequisicaoCriarFork(novo_ramo="fork-1", ramo_origem="main"))
    assert rec_fork.sucesso is True

    # Adiciona nó no fork
    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Task Extra", id_no="t-fork", ramo_id="fork-1"))

    diff = fork_ctrl.calcular_diff_ramos("main", "fork-1")
    assert "t-fork" in diff["nos_adicionados"]
    assert "g-base" in diff["nos_comuns"]


def test_diff_ramos_identicos_edge_case() -> None:
    """Valida cálculo de diff quando ambos os ramos são idênticos."""
    kernel = montar_kernel_em_memoria()
    canvas_ctrl = CanvasWebController(kernel)
    fork_ctrl = ForkWebController(kernel)

    canvas_ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="G", id_no="g-1", ramo_id="main"))
    fork_ctrl.criar_fork(RequisicaoCriarFork(novo_ramo="fork-dup", ramo_origem="main"))

    diff = fork_ctrl.calcular_diff_ramos("main", "fork-dup")
    assert len(diff["nos_adicionados"]) == 0
    assert len(diff["nos_removidos"]) == 0
    assert len(diff["nos_comuns"]) == 1


def test_fork_com_evento_inexistente_edge_case() -> None:
    """Valida falha graciosa ao tentar fork com ID de evento inexistente."""
    kernel = montar_kernel_em_memoria()
    fork_ctrl = ForkWebController(kernel)

    rec_invalido = fork_ctrl.criar_fork(RequisicaoCriarFork(
        novo_ramo="fork-erro",
        ramo_origem="main",
        evento_id_ponto_corte="evento-fantasma",
    ))
    assert rec_invalido.sucesso is False
    assert "inexistente" in rec_invalido.mensagem


def test_fork_ramo_origem_vazio_edge_case() -> None:
    """Valida falha ao criar fork a partir de ramo sem nenhum evento."""
    kernel = montar_kernel_em_memoria()
    fork_ctrl = ForkWebController(kernel)

    recibo = fork_ctrl.criar_fork(RequisicaoCriarFork(novo_ramo="fork-vazio", ramo_origem="ramo-vazio"))
    assert recibo.sucesso is False
    assert "sem eventos" in recibo.mensagem
