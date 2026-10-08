"""A seção Governanca diz os limiares de desvio e o teto de expansão só quando fogem do padrão."""

from graphow.context.governanca_vigente import descrever_governanca, gestos_com_o_arbitro, gestos_com_o_humano
from graphow.core.governanca import Gesto, PresetGovernanca, compor_politica_global, politica_do_preset


def _personalizada(**gestos: str | int):
    """Política global personalizada com os gestos dados."""
    return compor_politica_global({"preset": "personalizada", "personalizada": gestos})


def test_arbitragem_maxima_entrega_o_plano_ao_arbitro_e_retem_o_desvio_nominal() -> None:
    """Na arbitragem máxima o árbitro aprova o plano e o humano segue respondendo o desvio."""
    politica = politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA)
    assert Gesto.APROVAR_PLANO in gestos_com_o_arbitro(politica)
    assert Gesto.RESPONDER_DESVIO in gestos_com_o_humano(politica)
    assert Gesto.RESPONDER_DESVIO not in gestos_com_o_arbitro(politica)


def test_leituras_no_padrao_nao_geram_linha_de_escopo_nominal() -> None:
    """Na arbitragem máxima, K, M e o teto estão no padrão e a seção não os repete."""
    linhas = descrever_governanca(politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA))
    assert not any(linha.startswith("- escopo:") for linha in linhas)


def test_leituras_fora_do_padrao_aparecem_numa_linha_nominal() -> None:
    """Só as leituras que diferem do padrão entram na linha `escopo`."""
    politica = _personalizada(limiar_desvio_por_raiz=6, teto_expansao=20)
    linhas = descrever_governanca(politica)
    assert "- escopo: limiar_desvio_por_raiz 6, teto_expansao 20" in linhas


def test_so_o_teto_ligado_gera_a_linha_edge_case() -> None:
    """Caso de borda: o teto 0 (desligado) é o padrão e não aparece; ligado, aparece sozinho."""
    assert "- escopo: teto_expansao 1" in descrever_governanca(_personalizada(teto_expansao=1))
    assert not any(linha.startswith("- escopo:") for linha in descrever_governanca(_personalizada(teto_expansao=0, excluir="arbitro")))
