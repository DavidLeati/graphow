"""O vocabulário de governança do escopo governado: gestos por papel, leituras inteiras e falhas."""

import pytest

from graphow.core.composicao_governanca import compor_mais_restritiva
from graphow.core.falhas import CATEGORIA_POR_MODO, CategoriaFalhaMAST, ModoFalhaMAST
from graphow.core.governanca import (
    GESTOS_INTEIROS,
    GESTOS_POR_PAPEL,
    Gesto,
    PoliticaGovernanca,
    PresetGovernanca,
    compor_politica_do_projeto,
    compor_politica_global,
    politica_do_preset,
    politica_padrao,
    validar_configuracao_do_projeto,
    validar_configuracao_global,
    validar_personalizada,
)
from graphow.core.leituras_inteiras import LEITURAS_INTEIRAS
from graphow.core.types import PapelAutor

MAXIMA = politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA)
ARBITRAGEM = politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA)
LEITURAS_DO_ESCOPO = [Gesto.LIMIAR_DESVIO_POR_RAIZ, Gesto.LIMIAR_DESVIO_POR_GOAL, Gesto.TETO_EXPANSAO]
DOMINIOS = {
    Gesto.LIMIAR_DESVIO_POR_RAIZ: (1, 50),
    Gesto.LIMIAR_DESVIO_POR_GOAL: (1, 200),
    Gesto.TETO_EXPANSAO: (0, 500),
}


def _projeto_com(gesto: Gesto, valor: str | int) -> PoliticaGovernanca:
    """Projeto personalizado, sobre a arbitragem máxima, com um gesto só trocado."""
    declarada = {"preset": "personalizada", "personalizada": {gesto.value: valor}}
    return compor_politica_do_projeto(declarada, None, ARBITRAGEM)


def test_aprovar_plano_e_humano_na_governanca_maxima_e_arbitro_na_arbitragem_nominal() -> None:
    """O plano é aprovado pelo humano ou, na arbitragem máxima, pelo árbitro."""
    assert MAXIMA.valor(Gesto.APROVAR_PLANO) == "humano"
    assert ARBITRAGEM.valor(Gesto.APROVAR_PLANO) == "arbitro"
    assert ARBITRAGEM.permite(Gesto.APROVAR_PLANO, PapelAutor.ARBITRO)
    assert not MAXIMA.permite(Gesto.APROVAR_PLANO, PapelAutor.ARBITRO)


def test_responder_desvio_e_humano_nos_dois_presets_fixos_nominal() -> None:
    """Nem a arbitragem máxima tira do humano o gesto que mostra o placar."""
    assert MAXIMA.valor(Gesto.RESPONDER_DESVIO) == "humano"
    assert ARBITRAGEM.valor(Gesto.RESPONDER_DESVIO) == "humano"
    assert not ARBITRAGEM.permite(Gesto.RESPONDER_DESVIO, PapelAutor.ARBITRO)
    assert ARBITRAGEM.permite(Gesto.RESPONDER_DESVIO, PapelAutor.HUMANO)


def test_so_a_personalizada_entrega_o_responder_desvio_ao_arbitro_edge_case() -> None:
    """Caso de borda: a personalizada é o único caminho para o árbitro dispensar um alerta."""
    politica = compor_politica_global({"preset": "personalizada", "personalizada": {"responder_desvio": "arbitro"}})
    assert politica.permite(Gesto.RESPONDER_DESVIO, PapelAutor.ARBITRO)
    assert politica.valor(Gesto.APROVAR_PLANO) == "humano"


def test_gestos_novos_se_decidem_por_papel_e_as_leituras_nao_nominal() -> None:
    """`aprovar_plano` e `responder_desvio` são por papel; os limiares e o teto têm leitura própria."""
    assert {Gesto.APROVAR_PLANO, Gesto.RESPONDER_DESVIO} <= GESTOS_POR_PAPEL
    assert set(LEITURAS_DO_ESCOPO) <= GESTOS_INTEIROS
    assert not set(LEITURAS_DO_ESCOPO) & GESTOS_POR_PAPEL
    with pytest.raises(ValueError, match="não se decide por papel"):
        MAXIMA.permite(Gesto.TETO_EXPANSAO, PapelAutor.HUMANO)


@pytest.mark.parametrize("politica", [MAXIMA, ARBITRAGEM, politica_padrao()])
def test_leituras_do_escopo_tem_os_padroes_do_contrato_nominal(politica: PoliticaGovernanca) -> None:
    """K é 3, M é 5 e o teto nasce desligado (0), em qualquer preset fixo."""
    assert politica.limiar_desvio_por_raiz == 3
    assert politica.limiar_desvio_por_goal == 5
    assert politica.teto_expansao == 0


@pytest.mark.parametrize("gesto", LEITURAS_DO_ESCOPO)
def test_dominio_das_leituras_aceita_os_extremos_nominal(gesto: Gesto) -> None:
    """Os dois extremos do domínio são válidos."""
    minimo, maximo = DOMINIOS[gesto]
    assert (LEITURAS_INTEIRAS[gesto.value].minimo, LEITURAS_INTEIRAS[gesto.value].maximo) == (minimo, maximo)
    assert validar_personalizada({gesto.value: minimo}) == []
    assert validar_personalizada({gesto.value: maximo}) == []


@pytest.mark.parametrize("gesto", LEITURAS_DO_ESCOPO)
def test_dominio_das_leituras_recusa_o_que_esta_fora_edge_case(gesto: Gesto) -> None:
    """Caso de borda: abaixo, acima, texto, decimal e booleano voltam como problema."""
    minimo, maximo = DOMINIOS[gesto]
    for invalido in (minimo - 1, maximo + 1, str(minimo), 1.5, True, None):
        problemas = validar_personalizada({gesto.value: invalido})
        assert len(problemas) == 1, invalido
        assert f"um inteiro de {minimo} a {maximo}" in problemas[0]


def test_personalizada_global_e_do_projeto_valem_a_leitura_declarada_nominal() -> None:
    """A leitura declarada vira propriedade da política, e o resto completa com o padrão."""
    declarada = {"limiar_desvio_por_raiz": 7, "limiar_desvio_por_goal": 12, "teto_expansao": 40}
    politica = compor_politica_global({"preset": "personalizada", "personalizada": declarada})
    assert (politica.limiar_desvio_por_raiz, politica.limiar_desvio_por_goal, politica.teto_expansao) == (7, 12, 40)
    assert politica.origem(Gesto.TETO_EXPANSAO) == "global"
    assert politica.valor(Gesto.APROVAR_PLANO) == "humano"
    assert validar_configuracao_global({"preset": "personalizada", "personalizada": declarada}) == []
    assert validar_configuracao_do_projeto({"preset": "personalizada", "personalizada": declarada}) == []


def test_valor_invalido_da_leitura_e_ignorado_na_resolucao_edge_case() -> None:
    """Caso de borda: valor fora do domínio gravado por fora não vira política."""
    politica = compor_politica_global({"preset": "personalizada", "personalizada": {"teto_expansao": 9999}})
    assert politica.teto_expansao == 0


@pytest.mark.parametrize("gesto", [Gesto.LIMIAR_DESVIO_POR_RAIZ, Gesto.LIMIAR_DESVIO_POR_GOAL])
def test_nos_limiares_vale_o_menor_nominal(gesto: Gesto) -> None:
    """Projetos com K ou M diferentes: o menor vence, e o projeto que o declara é a origem."""
    composta = compor_mais_restritiva({"a": _projeto_com(gesto, 9), "b": _projeto_com(gesto, 2), "c": ARBITRAGEM})
    assert composta.valor(gesto) == 2
    assert composta.origem(gesto) == "projeto:b"


def test_no_teto_vale_o_menor_positivo_e_zero_perde_nominal() -> None:
    """O teto 0 é "desligado": perde para qualquer teto ligado, e entre os ligados vale o menor."""
    desligado = _projeto_com(Gesto.TETO_EXPANSAO, 0)
    composta = compor_mais_restritiva({"a": desligado, "b": _projeto_com(Gesto.TETO_EXPANSAO, 30), "c": _projeto_com(Gesto.TETO_EXPANSAO, 12)})
    assert composta.teto_expansao == 12
    assert composta.origem(Gesto.TETO_EXPANSAO) == "projeto:c"
    assert compor_mais_restritiva({"a": desligado, "b": _projeto_com(Gesto.TETO_EXPANSAO, 30)}).teto_expansao == 30


def test_teto_desligado_em_todos_os_projetos_continua_desligado_edge_case() -> None:
    """Caso de borda: sem nenhum teto ligado, a composta fica em 0 e não inventa um limite."""
    composta = compor_mais_restritiva({"a": MAXIMA, "b": ARBITRAGEM})
    assert composta.teto_expansao == 0


def test_composicao_do_responder_desvio_mantem_o_humano_edge_case() -> None:
    """Caso de borda: um projeto que entrega o desvio ao árbitro não o tira do projeto que o retém."""
    entregue = _projeto_com(Gesto.RESPONDER_DESVIO, "arbitro")
    assert entregue.permite(Gesto.RESPONDER_DESVIO, PapelAutor.ARBITRO)
    composta = compor_mais_restritiva({"a": entregue, "b": MAXIMA})
    assert composta.valor(Gesto.RESPONDER_DESVIO) == "humano"
    assert composta.origem(Gesto.RESPONDER_DESVIO) == "projeto:b"


def test_falhas_do_escopo_tem_nome_estavel_e_categoria_nominal() -> None:
    """As três recusas do escopo governado têm modo MAST e categoria declarados."""
    assert ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE.value == "ligacao_de_escopo_ausente"
    assert ModoFalhaMAST.PLANO_NAO_APROVADO.value == "plano_nao_aprovado"
    assert ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO.value == "orcamento_de_escopo_esgotado"
    assert CATEGORIA_POR_MODO[ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE] == CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA
    assert CATEGORIA_POR_MODO[ModoFalhaMAST.PLANO_NAO_APROVADO] == CategoriaFalhaMAST.VERIFICACAO_DE_TAREFA
    assert CATEGORIA_POR_MODO[ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO] == CategoriaFalhaMAST.DESIGN_DO_SISTEMA
