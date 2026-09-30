"""O que cada disparo do hook acrescenta ao Run: o consumo lido da transcrição e quem executou.

No fim da sessão, a transcrição dela dá os tokens do orquestrador. No fim de um
subagente, a transcrição dele dá os tokens, o modelo que de fato respondeu e as
tarefas que ele assumiu; é por essas tarefas que a medição atribui o custo ao
trabalho. As outras fases não leem nada.

Sem consumo, o Run grava por quê (`motivo_sem_consumo`). Antes todo caso virava
o mesmo None, e o Run sem tokens não dizia se faltou o id do agente, o caminho,
o arquivo ou a leitura: cada causa pede um conserto diferente.

A cota do plano entra pelo mesmo caminho. A raiz a escreve no despacho do
condutor, e o Run dele grava a do início da rodada; ela a escreve de novo ao
parar o laço, e o Run da sessão grava a do fim. Um executor despachado pelo
condutor não recebe a linha, e o Run dele fica sem cota.
"""

from pathlib import Path
from typing import Any

from graphow.harness.entrada_hook import EntradaDeHook
from graphow.harness.servico_harness import FaseDoHarness
from graphow.harness.transcricao import (
    CAMPO_MOTIVO_SEM_CONSUMO,
    MOTIVO_TRANSCRICAO_AUSENTE,
    ConsumoDaTranscricao,
    LeituraDaTranscricao,
    ler_transcricao,
    localizar_transcricao_do_subagente,
)

TIPO_DE_AGENTE_DESCONHECIDO: str = "subagente"
MOTIVO_SEM_AGENT_ID: str = "sem_agent_id"
MOTIVO_SEM_TRANSCRIPT_PATH: str = "sem_transcript_path"
# Sufixos das chaves de cota no Run: cota_5h_inicio, cota_semanal_fim.
MOMENTO_DO_DESPACHO: str = "inicio"
MOMENTO_DA_PARADA: str = "fim"


def ler_disparo(fase: FaseDoHarness, entrada: EntradaDeHook) -> LeituraDaTranscricao:
    """No fim da sessão, a transcrição dela; no fim de um subagente, a dele; nas outras fases, nada."""
    if fase == FaseDoHarness.FIM:
        if not entrada.transcricao:
            return LeituraDaTranscricao(motivo_sem_consumo=MOTIVO_SEM_TRANSCRIPT_PATH)
        return ler_transcricao(Path(entrada.transcricao))
    if fase != FaseDoHarness.SUBAGENTE:
        return LeituraDaTranscricao()
    if not entrada.id_agente:
        return LeituraDaTranscricao(motivo_sem_consumo=MOTIVO_SEM_AGENT_ID)
    caminho = localizar_transcricao_do_subagente(entrada.caminhos_de_transcricao(), entrada.id_agente)
    if caminho is None:
        return LeituraDaTranscricao(motivo_sem_consumo=MOTIVO_TRANSCRICAO_AUSENTE)
    return ler_transcricao(caminho)


def ler_consumo_do_disparo(fase: FaseDoHarness, entrada: EntradaDeHook) -> ConsumoDaTranscricao | None:
    """Só o consumo do disparo, para quem não precisa do motivo."""
    return ler_disparo(fase, entrada).consumo


def descrever_disparo(
    fase: FaseDoHarness,
    entrada: EntradaDeHook,
    consumo: ConsumoDaTranscricao | None,
    *,
    motivo_sem_consumo: str = "",
) -> dict[str, Any]:
    """As propriedades extras do Run; sem transcrição legível, o Run fica sem tokens, não com zero, e diz por quê."""
    propriedades = {**consumo.em_propriedades(), **_cota(fase, consumo)} if consumo is not None else {}
    if consumo is None and motivo_sem_consumo:
        propriedades[CAMPO_MOTIVO_SEM_CONSUMO] = motivo_sem_consumo
    if fase != FaseDoHarness.SUBAGENTE:
        return propriedades
    tipo = entrada.tipo_agente or TIPO_DE_AGENTE_DESCONHECIDO
    return {**propriedades, "rotulo": f"Subagente {tipo}", "agente": tipo, "id_agente": entrada.id_agente}


def _cota(fase: FaseDoHarness, consumo: ConsumoDaTranscricao) -> dict[str, float]:
    """A cota que a raiz declarou: a do despacho no Run do subagente, a da parada no Run da sessão."""
    if fase == FaseDoHarness.SUBAGENTE and consumo.cota_do_despacho is not None:
        return consumo.cota_do_despacho.em_propriedades(MOMENTO_DO_DESPACHO)
    if fase == FaseDoHarness.FIM and consumo.ultima_cota_escrita is not None:
        return consumo.ultima_cota_escrita.em_propriedades(MOMENTO_DA_PARADA)
    return {}

