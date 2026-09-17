"""Harness de avaliação: mede tokens por tarefa bem-sucedida sobre um corpus gravado."""

from graphow.avaliacao.cenario_entre_projetos import montar_cenario_entre_projetos
from graphow.avaliacao.cenario_memoria import montar_cenario_com_memoria
from graphow.avaliacao.entre_projetos import MedidorEntreProjetos, RelatorioEntreProjetos
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
    """Monta os cenários gravados, mede os três braços e consolida o relatório.

    O braço original corre sobre o cenário base, intocado. Os braços de memória
    correm sobre extensões montadas em kernels próprios: assim o número antigo
    continua comparável com o que já foi publicado.
    """
    medicoes = MedidorDeTarefas(montar_cenario_gravado()).medir_todas()
    retomada = MedidorDeRetomada(montar_cenario_com_memoria()).medir()
    entre_projetos = MedidorEntreProjetos(montar_cenario_entre_projetos()).medir_todas()
    return RelatorioDeAvaliacao.a_partir_de(medicoes, retomada=retomada, entre_projetos=entre_projetos)


__all__ = [
    "MedicaoDaTarefa",
    "MedicaoDeRetomada",
    "MedidorDeEscala",
    "MedidorDeRetomada",
    "MedidorDeTarefas",
    "MedidorEntreProjetos",
    "RelatorioDeEscala",
    "RelatorioDeAvaliacao",
    "RelatorioEntreProjetos",
    "TAREFAS_GRAVADAS",
    "TarefaGravada",
    "executar_avaliacao",
    "medir_escala",
    "montar_cenario_com_memoria",
    "montar_cenario_entre_projetos",
    "montar_cenario_gravado",
]
