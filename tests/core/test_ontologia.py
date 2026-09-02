"""A versão da ontologia viaja no evento e não pode mentir.

Cada evento trazia autor, papel e origem, e nada dizia qual vocabulário estava
em vigor quando ele foi escrito. A assinatura existe para que a versão declarada
não fique para trás quando alguém mexer nos tipos. Ver achado A-17.
"""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.ontologia import (
    ASSINATURA_DECLARADA,
    VERSAO_ONTOLOGIA,
    calcular_assinatura_da_ontologia,
)
from graphow.core.types import PapelAutor


def test_assinatura_declarada_bate_com_o_vocabulario_nominal() -> None:
    """Mexer nos tipos sem subir a versão derruba este teste, que é o ponto.

    Se você chegou aqui por uma falha: acrescentou, removeu ou renomeou um termo
    da ontologia. Suba `VERSAO_ONTOLOGIA` e cole a assinatura nova em
    `ASSINATURA_DECLARADA`.
    """
    assert calcular_assinatura_da_ontologia() == ASSINATURA_DECLARADA


def test_evento_nasce_com_a_versao_corrente_nominal() -> None:
    """Todo evento novo carrega a versão do vocabulário que o escreveu."""
    evento = EventoLog.criar(
        DadosCriacaoEvento(
            seq=1,
            autor="david",
            papel=PapelAutor.HUMANO,
            tipo_evento=TipoEvento.NO_CRIADO,
            payload={"id": "n1"},
        )
    )

    assert evento.versao_ontologia == VERSAO_ONTOLOGIA


def test_versao_pode_ser_declarada_no_dto_edge_case() -> None:
    """Caso de borda: reprocessar um log antigo preserva a versão de origem."""
    evento = EventoLog.criar(
        DadosCriacaoEvento(
            seq=1,
            autor="david",
            papel=PapelAutor.HUMANO,
            tipo_evento=TipoEvento.NO_CRIADO,
            versao_ontologia="0.9.0",
        )
    )

    assert evento.versao_ontologia == "0.9.0"
