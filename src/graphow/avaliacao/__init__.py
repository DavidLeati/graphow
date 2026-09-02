"""Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado."""

from graphow.avaliacao.medicao import MedicaoDaTarefa, MedidorDeTarefas
from graphow.avaliacao.relatorio import RelatorioDeAvaliacao
from graphow.avaliacao.tarefas_gravadas import (
    TAREFAS_GRAVADAS,
    TarefaGravada,
    montar_cenario_gravado,
)


def executar_avaliacao() -> RelatorioDeAvaliacao:
    """Monta o cenário gravado, mede as dez tarefas e consolida o relatório."""
    medicoes = MedidorDeTarefas(montar_cenario_gravado()).medir_todas()
    return RelatorioDeAvaliacao.a_partir_de(medicoes)


__all__ = [
    "MedicaoDaTarefa",
    "MedidorDeTarefas",
    "RelatorioDeAvaliacao",
    "TAREFAS_GRAVADAS",
    "TarefaGravada",
    "executar_avaliacao",
    "montar_cenario_gravado",
]
