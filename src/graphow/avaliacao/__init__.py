"""Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado."""

from graphow.avaliacao.cenario_memoria import montar_cenario_com_memoria
from graphow.avaliacao.escala import MedidorDeEscala, RelatorioDeEscala, medir_escala
from graphow.avaliacao.medicao import MedicaoDaTarefa, MedidorDeTarefas
from graphow.avaliacao.relatorio import RelatorioDeAvaliacao
from graphow.avaliacao.retomada import MedicaoDeRetomada, MedidorDeRetomada
from graphow.avaliacao.tarefas_gravadas import (
    TAREFAS_GRAVADAS,
    TarefaGravada,
    montar_cenario_gravado,
)


def executar_avaliacao() -> RelatorioDeAvaliacao:
    """Monta os cenários gravados, mede os braços e consolida o relatório.

    O braço original corre sobre o cenário base, intocado. Os braços de memória
    correm sobre a extensão, montada num kernel próprio: assim o número antigo
    continua comparável com o que já foi publicado.
    """
    medicoes = MedidorDeTarefas(montar_cenario_gravado()).medir_todas()
    retomada = MedidorDeRetomada(montar_cenario_com_memoria()).medir()
    return RelatorioDeAvaliacao.a_partir_de(medicoes, retomada=retomada)


__all__ = [
    "MedicaoDaTarefa",
    "MedicaoDeRetomada",
    "MedidorDeEscala",
    "MedidorDeRetomada",
    "MedidorDeTarefas",
    "RelatorioDeEscala",
    "RelatorioDeAvaliacao",
    "TAREFAS_GRAVADAS",
    "TarefaGravada",
    "executar_avaliacao",
    "medir_escala",
    "montar_cenario_com_memoria",
    "montar_cenario_gravado",
]
