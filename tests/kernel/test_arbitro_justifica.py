"""O árbitro liga a Evidence que leu à Decision que a resposta dele sustenta, em qualquer política."""

import pytest

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.matriz_papeis import QUEM_JUSTIFICA, obter_donos_de_aresta
from tests.kernel.cenario_governanca import (
    PRESET_ARBITRAGEM,
    PRESET_MAXIMA,
    criar_aresta,
    criar_no,
    montar_estado,
    validar,
)

PRESETS = [PRESET_MAXIMA, PRESET_ARBITRAGEM]


def _lote_do_julgamento() -> tuple:
    """Evidence e Decision do árbitro, cada uma com `produz`, ligadas por `justifica`."""
    return (
        criar_no("ev-arb", TipoNo.EVIDENCE),
        criar_aresta("prod-ev-arb", "sess", "ev-arb", TipoAresta.PRODUZ),
        criar_no("dec-arb", TipoNo.DECISION),
        criar_aresta("prod-dec-arb", "sess", "dec-arb", TipoAresta.PRODUZ),
        criar_aresta("just-arb", "ev-arb", "dec-arb", TipoAresta.JUSTIFICA),
    )


@pytest.mark.parametrize("preset", PRESETS)
def test_arbitro_liga_a_propria_evidence_a_propria_decision_nominal(preset: dict) -> None:
    """Em governanca_maxima e em arbitragem_maxima o árbitro cria o `justifica` do que registrou."""
    estado = montar_estado(global_=preset)

    resultado = validar(PapelAutor.ARBITRO, estado, *_lote_do_julgamento(), autor="arbitro-1#aaaa")

    assert resultado.aprovado, resultado.mensagem_erro


def test_arbitro_tambem_remove_o_justifica_nominal() -> None:
    """Quem justifica também desfaz a ligação, como os outros donos da aresta."""
    donos = obter_donos_de_aresta(TipoAresta.JUSTIFICA)

    assert PapelAutor.ARBITRO in donos.adicao
    assert PapelAutor.ARBITRO in donos.remocao


def test_justifica_segue_fechada_a_quem_nao_registra_os_dois_lados_edge_case() -> None:
    """Caso de borda: abrir o `justifica` ao árbitro não o abre ao harness."""
    assert PapelAutor.SISTEMA not in QUEM_JUSTIFICA
    assert {PapelAutor.HUMANO, PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR} <= QUEM_JUSTIFICA


def test_arbitro_continua_sem_orienta_e_deriva_de_edge_case() -> None:
    """Caso de borda: só o `justifica` foi aberto; `orienta` segue do planejador e do humano."""
    estado = montar_estado(global_=PRESET_MAXIMA)

    orienta = validar(
        PapelAutor.ARBITRO, estado, criar_aresta("orienta-x", "c", "t", TipoAresta.ORIENTA), autor="arbitro-1#aaaa"
    )
    deriva = validar(
        PapelAutor.ARBITRO, estado, criar_aresta("deriva-x", "a", "t", TipoAresta.DERIVA_DE), autor="arbitro-1#aaaa"
    )

    assert not orienta.aprovado
    assert not deriva.aprovado
