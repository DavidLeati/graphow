"""Raiz de composição do servidor web: quem escuta os commits do kernel.

A camada reativa não pode conhecer a web; é a web que compõe as duas pontas.
"""

from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.engine import MotorReativo
from graphow.reactive.montagem import montar_motor_reativo_padrao
from graphow.reactive.observador_reativo import ObservadorReativo
from graphow.web.observador_sse import ObservadorSSE
from graphow.web.sse_controller import SSEWebController


def registrar_observadores_do_servidor(
    kernel: WriteKernel,
    controlador_sse: SSEWebController,
    motor: MotorReativo,
) -> None:
    """Liga o canal de tempo real e o motor reativo ao gancho pós-commit do kernel.

    A ordem importa: o canvas recebe primeiro o evento que originou a reação e
    depois o evento reativo derivado dela.
    """
    kernel.registrar_observador(ObservadorSSE(controlador_sse))
    kernel.registrar_observador(ObservadorReativo(motor))


def montar_tempo_real(kernel: WriteKernel, controlador_sse: SSEWebController) -> MotorReativo:
    """Monta o motor reativo padrão e o registra junto do canal SSE."""
    motor = montar_motor_reativo_padrao(kernel)
    registrar_observadores_do_servidor(kernel, controlador_sse, motor)
    return motor
