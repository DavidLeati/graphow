"""Propriedades que a orquestração grava na Task, no Goal e na Evidence de revisão.

Não são termos da ontologia: o SchemaGate não valida propriedades e a assinatura
da ontologia não as cobre. São a convenção que o orquestrador escreve por
`criar_tarefa`, que a fila de trabalho devolve e que a medição lê, declarada num
lugar só para as três pontas não divergirem.
"""

from collections.abc import Mapping
from typing import Any

# Na Task: o modelo que deve executá-la e por quê, os arquivos que ela toca
# (é o que decide o paralelismo) e, na tarefa de correção, a Evidence de
# revisão que a motivou. O critério de aceite é o `criterio_pronto` de sempre.
CAMPO_MODELO: str = "modelo"
CAMPO_MOTIVO_DO_MODELO: str = "motivo_modelo"
CAMPO_ARQUIVOS_ALVO: str = "arquivos_alvo"
CAMPO_CORRIGE: str = "corrige"
CAMPO_CRITERIO_PRONTO: str = "criterio_pronto"

# No Goal: o rótulo da configuração de modelos com que ele foi orquestrado,
# para a medição comparar o mesmo conjunto de tarefas sob arranjos diferentes.
CAMPO_CONFIGURACAO: str = "configuracao"

# Na Evidence do revisor: o que ele concluiu contra os critérios da tarefa.
CAMPO_VEREDITO: str = "veredito"
VEREDITO_APROVADO: str = "aprovado"
VEREDITO_REJEITADO: str = "rejeitado"


def ler_textos(valor: object) -> tuple[str, ...]:
    """Lista de textos não vazios, sem repetição e na ordem dada; um texto solto vira lista de um."""
    brutos = [valor] if isinstance(valor, str) else valor if isinstance(valor, (list, tuple)) else []
    return tuple(dict.fromkeys(str(item).strip() for item in brutos if str(item).strip()))


def ler_texto(propriedades: Mapping[str, Any], chave: str) -> str:
    """O valor textual da propriedade, sem espaços nas pontas; vazio quando ausente."""
    return str(propriedades.get(chave, "") or "").strip()
