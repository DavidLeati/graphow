"""Testes da composição pura da política mais restritiva, gesto a gesto."""

import pytest

from graphow.core.composicao_governanca import compor_mais_restritiva
from graphow.core.governanca import (
    GESTOS_POR_PAPEL,
    Gesto,
    PoliticaGovernanca,
    compor_politica_do_projeto,
    compor_politica_global,
    politica_do_preset,
    PresetGovernanca,
)
from graphow.core.types import PapelAutor

# O `responder_desvio` já é do humano na arbitragem máxima, então não há o que restringir; veja test_governanca_escopo.
GESTOS_DE_PAPEL = sorted((gesto for gesto in GESTOS_POR_PAPEL if gesto != Gesto.RESPONDER_DESVIO), key=lambda gesto: gesto.value)
MAXIMA = politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA)
ARBITRAGEM = politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA)


def _com(gesto: Gesto, valor: str | int) -> PoliticaGovernanca:
    """Arbitragem máxima com um gesto só trocado: o Projeto personalizado sobre uma global de arbitragem."""
    politica_global = compor_politica_global({"preset": "arbitragem_maxima"})
    declarada = {"preset": "personalizada", "personalizada": {gesto.value: valor}}
    return compor_politica_do_projeto(declarada, None, politica_global)


@pytest.mark.parametrize("gesto", GESTOS_DE_PAPEL)
def test_humano_vence_arbitro_em_cada_gesto_por_papel_nominal(gesto: Gesto) -> None:
    """Um Projeto em arbitragem e outro com o gesto no humano: o gesto fica com o humano, em qualquer ordem."""
    restrito = _com(gesto, "humano")
    for politicas in ({"a": ARBITRAGEM, "b": restrito}, {"b": ARBITRAGEM, "a": restrito}):
        composta = compor_mais_restritiva(politicas)
        assert composta.valor(gesto) == "humano"
        assert not composta.permite(gesto, PapelAutor.ARBITRO)
        assert composta.permite(gesto, PapelAutor.HUMANO)
        assert composta.origem(gesto) == f"projeto:{'b' if politicas['b'] is restrito else 'a'}"


def test_estrito_vence_ilimitado_nominal() -> None:
    """A estrutura fica estrita se algum Projeto a tem estrita."""
    composta = compor_mais_restritiva({"a": ARBITRAGEM, "b": _com(Gesto.ESTRUTURA, "estrito")})

    assert composta.valor(Gesto.ESTRUTURA) == "estrito"
    assert not composta.estrutura_ilimitada
    assert composta.origem(Gesto.ESTRUTURA) == "projeto:b"


def test_vale_o_menor_max_correcoes_nominal() -> None:
    """O menor número de correções vence, e o Projeto que o declara é a origem."""
    composta = compor_mais_restritiva({"a": _com(Gesto.MAX_CORRECOES, 4), "b": _com(Gesto.MAX_CORRECOES, 1), "c": ARBITRAGEM})

    assert composta.max_correcoes == 1
    assert composta.origem(Gesto.MAX_CORRECOES) == "projeto:b"


def test_cada_gesto_e_composto_por_conta_propria_nominal() -> None:
    """Um Projeto restringe um gesto e o outro restringe outro: a composta junta as duas restrições."""
    composta = compor_mais_restritiva({"a": _com(Gesto.EXCLUIR, "humano"), "b": _com(Gesto.CONSTRAINT, "humano")})

    assert composta.valor(Gesto.EXCLUIR) == "humano"
    assert composta.valor(Gesto.CONSTRAINT) == "humano"
    assert composta.valor(Gesto.FECHAR_GOAL) == "arbitro"
    assert (composta.origem(Gesto.EXCLUIR), composta.origem(Gesto.CONSTRAINT)) == ("projeto:a", "projeto:b")


def test_empate_aponta_o_menor_id_e_nao_depende_da_ordem_edge_case() -> None:
    """Caso de borda: dois Projetos com o mesmo valor mais restritivo; a origem é o de menor id."""
    um = compor_mais_restritiva({"proj-z": MAXIMA, "proj-b": MAXIMA, "proj-m": ARBITRAGEM})
    outro = compor_mais_restritiva({"proj-m": ARBITRAGEM, "proj-b": MAXIMA, "proj-z": MAXIMA})

    assert um == outro
    assert {um.origem(gesto) for gesto in Gesto} == {"projeto:proj-b"}


def test_projeto_so_devolve_a_propria_politica_sem_mudar_as_origens_edge_case() -> None:
    """Caso de borda: com um Projeto só, a política e as origens são as dele."""
    politica = compor_politica_do_projeto({"preset": "personalizada", "personalizada": {"excluir": "humano"}}, None, ARBITRAGEM)

    assert compor_mais_restritiva({"proj": politica}) == politica
    assert compor_mais_restritiva({"proj": politica}).origem(Gesto.EXCLUIR) == "projeto"


def test_politicas_iguais_nao_mudam_os_valores_edge_case() -> None:
    """Caso de borda: compor duas políticas iguais mantém os valores, só a origem passa a nomear o Projeto."""
    composta = compor_mais_restritiva({"a": ARBITRAGEM, "b": ARBITRAGEM})

    assert composta.valores == ARBITRAGEM.valores
    assert composta.permite(Gesto.EXCLUIR, PapelAutor.ARBITRO)


def test_sem_nenhum_projeto_e_erro_de_quem_chama_edge_case() -> None:
    """Caso de borda: não há política a compor sem Projeto."""
    with pytest.raises(ValueError):
        compor_mais_restritiva({})
