"""O que cada disparo do hook acrescenta ao Run: o consumo lido da transcrição e quem executou.

No fim da sessão, a transcrição dela dá os tokens do orquestrador. No fim de um
subagente, a transcrição dele dá os tokens, o modelo que de fato respondeu e as
tarefas que ele assumiu; é por essas tarefas que a medição atribui o custo ao
trabalho. As outras fases não leem nada.
"""

from pathlib import Path
from typing import Any

from graphow.harness.entrada_hook import EntradaDeHook
from graphow.harness.servico_harness import FaseDoHarness
from graphow.harness.transcricao import ConsumoDaTranscricao, ler_consumo, localizar_transcricao_do_subagente

TIPO_DE_AGENTE_DESCONHECIDO: str = "subagente"


def ler_consumo_do_disparo(fase: FaseDoHarness, entrada: EntradaDeHook) -> ConsumoDaTranscricao | None:
    """No fim da sessão, a transcrição dela; no fim de um subagente, a dele; nas outras fases, nada."""
    if fase == FaseDoHarness.FIM and entrada.transcricao:
        return ler_consumo(Path(entrada.transcricao))
    if fase != FaseDoHarness.SUBAGENTE:
        return None
    caminho = localizar_transcricao_do_subagente(entrada.caminhos_de_transcricao(), entrada.id_agente)
    return ler_consumo(caminho) if caminho is not None else None


def descrever_disparo(
    fase: FaseDoHarness,
    entrada: EntradaDeHook,
    consumo: ConsumoDaTranscricao | None,
) -> dict[str, Any]:
    """As propriedades extras do Run; sem transcrição legível, o Run fica sem tokens, não com zero."""
    propriedades = consumo.em_propriedades() if consumo is not None else {}
    if fase != FaseDoHarness.SUBAGENTE:
        return propriedades
    tipo = entrada.tipo_agente or TIPO_DE_AGENTE_DESCONHECIDO
    return {**propriedades, "rotulo": f"Subagente {tipo}", "agente": tipo, "id_agente": entrada.id_agente}
