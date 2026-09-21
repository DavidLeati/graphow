"""O que `criar_tarefa` grava para a orquestração: modelo, arquivos-alvo, correção e decisões.

Quem orquestra decide na própria Task qual modelo a executa, e o motivo vai
junto para a escolha ficar auditável no log: um modelo sem motivo é recusado
aqui, porque o SchemaGate não valida propriedades. Os arquivos-alvo são o que
decide o paralelismo. E as decisões que valem para a tarefa viram arestas
`orienta` no mesmo lote, que é por onde o executor que nunca viu a conversa as
encontra.
"""

from collections.abc import Mapping
from typing import Any

from graphow.core.orquestracao import (
    CAMPO_ARQUIVOS_ALVO,
    CAMPO_CORRIGE,
    CAMPO_MODELO,
    CAMPO_MOTIVO_DO_MODELO,
    ler_texto,
    ler_textos,
)
from graphow.core.types import TipoAresta
from graphow.mcp.construcao_operacoes import EspecificacaoAresta

CAMPO_DECISOES: str = "decisoes"
CAMPO_TAREFA_PAI: str = "id_tarefa_pai"


def recusar_modelo_sem_motivo(argumentos: Mapping[str, Any]) -> dict[str, Any] | None:
    """A recusa quando o modelo vem sem o motivo; None quando os dois vêm juntos ou nenhum vem."""
    if not ler_texto(argumentos, CAMPO_MODELO) or ler_texto(argumentos, CAMPO_MOTIVO_DO_MODELO):
        return None
    return {
        "sucesso": False,
        "erro": "Informe 'motivo_modelo' junto de 'modelo': a escolha do modelo precisa ficar auditavel no log",
    }


def propriedades_de_orquestracao(argumentos: Mapping[str, Any]) -> dict[str, Any]:
    """As propriedades que vieram na chamada; as ausentes não entram, para a Task antiga não mudar de forma."""
    propriedades: dict[str, Any] = {}
    modelo = ler_texto(argumentos, CAMPO_MODELO).lower()
    if modelo:
        propriedades[CAMPO_MODELO] = modelo
        propriedades[CAMPO_MOTIVO_DO_MODELO] = ler_texto(argumentos, CAMPO_MOTIVO_DO_MODELO)
    arquivos = ler_textos(argumentos.get(CAMPO_ARQUIVOS_ALVO))
    if arquivos:
        propriedades[CAMPO_ARQUIVOS_ALVO] = list(arquivos)
    corrige = ler_texto(argumentos, CAMPO_CORRIGE)
    if corrige:
        propriedades[CAMPO_CORRIGE] = corrige
    return propriedades


def arestas_de_orientacao(id_task: str, argumentos: Mapping[str, Any]) -> tuple[EspecificacaoAresta, ...]:
    """Uma aresta `orienta` de cada Decision declarada para a Task nova."""
    return tuple(
        EspecificacaoAresta(
            id=f"orienta-{id_decisao}-{id_task}",
            origem_id=id_decisao,
            destino_id=id_task,
            tipo=TipoAresta.ORIENTA,
        )
        for id_decisao in ler_textos(argumentos.get(CAMPO_DECISOES))
    )


def aresta_de_espera_da_correcao(id_task: str, argumentos: Mapping[str, Any]) -> tuple[EspecificacaoAresta, ...]:
    """A tarefa corrigida passa a depender da correção.

    Rejeitada, a original segue `pronto_para_revisao`, e a fila a oferecia de
    novo, como se esperasse outra revisão. Ela só fecha depois da correção: é
    isso que o `depende_de` diz, e a fila passa a mostrá-la impedida até lá.
    """
    id_pai = ler_texto(argumentos, CAMPO_TAREFA_PAI)
    if not ler_texto(argumentos, CAMPO_CORRIGE) or not id_pai:
        return ()
    return (EspecificacaoAresta(id=f"espera-{id_pai}-{id_task}", origem_id=id_pai, destino_id=id_task, tipo=TipoAresta.DEPENDE_DE),)
