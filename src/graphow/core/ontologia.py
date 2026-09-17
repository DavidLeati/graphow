"""Versão declarada do vocabulário da ontologia e a impressão digital que a checa.

Cada evento do log carregava autor, papel e origem, e nenhuma indicação de qual
vocabulário estava em vigor quando ele foi escrito. Um log de anos atrás, relido
depois que um tipo mudou de nome, projeta silenciosamente errado. A versão viaja
no evento; a assinatura existe para que ela não possa mentir.
"""

import hashlib

from graphow.core.types import (
    NivelAutonomiaProjeto,
    OrigemEvento,
    PapelAutor,
    StatusQuestion,
    StatusSessao,
    StatusTask,
    TipoAresta,
    TipoNo,
)

# 1.1.0: a Sessao ganha ciclo de vida declarado (`StatusSessao`), o tipo
# `Aprendizado` e a aresta `vale_para` entram como memória de longo prazo, e
# `deriva_de` passa a admitir Evidence e Artifact como origem de uma Note.
VERSAO_ONTOLOGIA: str = "1.1.0"

# As arestas pelas quais um nó contém outro. Existem três recortes divergentes
# de "hierarquia" espalhados pelo código — `politicas` usa {decompoe, produz},
# `mapeamento_escopo` usa {contem, produz}, `fila_trabalho` usa {produz,
# decompoe} — e nenhum deles é o fecho completo. Esta é a definição canônica,
# usada pelo rollup de subárvore. Migrar os três recortes é mudança de
# comportamento e pede commit próprio, com teste fixando o atual antes.
ARESTAS_DE_CONTENCAO: frozenset[TipoAresta] = frozenset(
    {TipoAresta.CONTEM, TipoAresta.PRODUZ, TipoAresta.DECOMPOE}
)

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
        *(f"sessao:{status.value}" for status in StatusSessao),
        *(f"autonomia:{nivel.value}" for nivel in NivelAutonomiaProjeto),
    )
    digestao = hashlib.sha256("|".join(sorted(termos)).encode("utf-8")).hexdigest()
    return digestao[:TAMANHO_DA_ASSINATURA]


# Fixada à mão de propósito: alterar o vocabulário sem tocar aqui derruba o teste
# de qualidade, e a decisão de subir a versão volta a ser de quem mexeu.
ASSINATURA_DECLARADA: str = "871ab7b90f7e"
