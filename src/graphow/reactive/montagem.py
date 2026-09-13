"""Montagem padrão do motor reativo com os comportamentos nativos do Graphow."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.builtins import (
    ReavaliacaoDecisaoSubstituidaBehavior,
    RevisorNotificadoBehavior,
)
from graphow.reactive.engine import MotorReativo
from graphow.reactive.interfaces import ComportamentoReativo


def montar_comportamentos_padrao() -> tuple[ComportamentoReativo, ...]:
    """Lista os comportamentos reativos que o produto ativa por padrão."""
    return (
        RevisorNotificadoBehavior(),
        ReavaliacaoDecisaoSubstituidaBehavior(),
    )


def montar_motor_reativo_padrao(kernel: WriteKernel) -> MotorReativo:
    """Constrói o motor reativo com os comportamentos nativos já registrados."""
    motor = MotorReativo(kernel)
    for comportamento in montar_comportamentos_padrao():
        motor.registrar_comportamento(comportamento)
    return motor
