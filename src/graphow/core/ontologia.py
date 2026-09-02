"""Versão declarada do vocabulário da ontologia e a impressão digital que a checa.

Cada evento do log carregava autor, papel e origem, e nenhuma indicação de qual
vocabulário estava em vigor quando ele foi escrito. Um log de anos atrás, relido
depois que um tipo mudou de nome, projeta silenciosamente errado. A versão viaja
no evento; a assinatura existe para que ela não possa mentir. Ver achado A-17.
"""

import hashlib

from graphow.core.types import (
    NivelAutonomiaProjeto,
    OrigemEvento,
    PapelAutor,
    StatusQuestion,
    StatusTask,
    TipoAresta,
    TipoNo,
)

VERSAO_ONTOLOGIA: str = "1.0.0"

# Eventos gravados antes de a ontologia ser versionada. Marcá-los com a versão
# corrente seria afirmar o que ninguém verificou.
VERSAO_ONTOLOGIA_DESCONHECIDA: str = "0"

TAMANHO_DA_ASSINATURA: int = 12


def calcular_assinatura_da_ontologia() -> str:
    """Impressão digital do vocabulário: muda quando um termo entra, sai ou muda."""
    termos = (
        *(f"no:{tipo.value}" for tipo in TipoNo),
        *(f"aresta:{tipo.value}" for tipo in TipoAresta),
        *(f"papel:{papel.value}" for papel in PapelAutor),
        *(f"origem:{origem.value}" for origem in OrigemEvento),
        *(f"task:{status.value}" for status in StatusTask),
        *(f"question:{status.value}" for status in StatusQuestion),
        *(f"autonomia:{nivel.value}" for nivel in NivelAutonomiaProjeto),
    )
    digestao = hashlib.sha256("|".join(sorted(termos)).encode("utf-8")).hexdigest()
    return digestao[:TAMANHO_DA_ASSINATURA]


# Fixada à mão de propósito: alterar o vocabulário sem tocar aqui derruba o teste
# de qualidade, e a decisão de subir a versão volta a ser de quem mexeu.
ASSINATURA_DECLARADA: str = "df1c29b96eae"
