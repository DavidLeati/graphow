"""Montagem padrão do motor reativo com os comportamentos nativos do Graphow."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.builtins import (
    ReavaliacaoDecisaoSubstituidaBehavior,
    RevisorNotificadoBehavior,
)
from graphow.reactive.condensacao import SessaoEncerradaBehavior
from graphow.reactive.consolidacao import AprendizadosAcumuladosBehavior
from graphow.reactive.engine import MotorReativo
from graphow.reactive.interfaces import ComportamentoReativo
from graphow.reactive.observador_reativo import ObservadorReativo


def montar_comportamentos_padrao() -> tuple[ComportamentoReativo, ...]:
    """Lista os comportamentos reativos que o produto ativa por padrão."""
    return (
        RevisorNotificadoBehavior(),
        ReavaliacaoDecisaoSubstituidaBehavior(),
        SessaoEncerradaBehavior(),
        AprendizadosAcumuladosBehavior(),
    )


def montar_motor_reativo_padrao(kernel: WriteKernel) -> MotorReativo:
    """Constrói o motor reativo com os comportamentos nativos já registrados."""
    motor = MotorReativo(kernel)
    for comportamento in montar_comportamentos_padrao():
        motor.registrar_comportamento(comportamento)
    return motor


def ligar_motor_reativo_padrao(kernel: WriteKernel) -> MotorReativo:
    """Monta o motor padrão e o inscreve no gancho pós-commit do kernel.

    O motor só estava ligado no processo web. O harness e o servidor MCP
    escrevem de processos próprios, e o gancho pós-commit só vê o que o próprio
    processo escreveu: uma sessão encerrada pelo hook de fim não pedia
    condensação nenhuma. Cada processo que escreve liga o seu motor.
    """
    motor = montar_motor_reativo_padrao(kernel)
    kernel.registrar_observador(ObservadorReativo(motor))
    return motor
