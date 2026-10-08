"""Testes unitários da política de governança pura: presets, herança, legado e validação."""

import pytest

from graphow.core.governanca import (
    GESTOS_COM_LEITURA_PROPRIA,
    GESTOS_POR_PAPEL,
    ORIGEM_GLOBAL,
    ORIGEM_LEGADO,
    ORIGEM_PROJETO,
    PRESETS_FIXOS,
    Gesto,
    PoliticaGovernanca,
    PresetDoProjeto,
    PresetGovernanca,
    compor_politica_do_projeto,
    compor_politica_global,
    politica_padrao,
    validar_configuracao_do_projeto,
    validar_configuracao_global,
    validar_personalizada,
)
from graphow.core.types import PapelAutor

GESTOS_DE_PAPEL = sorted(GESTOS_POR_PAPEL, key=lambda gesto: gesto.value)
# O `responder_desvio` é do humano nos dois presets fixos: não acompanha a arbitragem máxima.
GESTOS_DELEGAVEIS = [gesto for gesto in GESTOS_DE_PAPEL if gesto != Gesto.RESPONDER_DESVIO]


def _global_arbitragem() -> PoliticaGovernanca:
    """Global com arbitragem máxima, para os testes de herança."""
    return compor_politica_global({"preset": "arbitragem_maxima"})


def test_sem_no_global_vale_governanca_maxima_nominal() -> None:
    """Sem propriedades do nó global, todo gesto é humano e a estrutura é estrita."""
    politica = compor_politica_global(None)
    assert politica == politica_padrao()
    assert all(politica.valor(gesto) == "humano" for gesto in GESTOS_POR_PAPEL)
    assert politica.valor(Gesto.ESTRUTURA) == "estrito"
    assert politica.max_correcoes == 2
    assert {politica.origem(gesto) for gesto in Gesto} == {"preset:governanca_maxima"}


def test_preset_governanca_maxima_fixo_nominal() -> None:
    """O preset governança máxima entrega tudo ao humano."""
    politica = compor_politica_global({"preset": "governanca_maxima"})
    assert dict(politica.valores) == dict(PRESETS_FIXOS[PresetGovernanca.GOVERNANCA_MAXIMA])
    assert not politica.estrutura_ilimitada


def test_preset_arbitragem_maxima_fixo_nominal() -> None:
    """O preset arbitragem máxima entrega todos os gestos ao árbitro e libera a estrutura."""
    politica = _global_arbitragem()
    assert all(politica.valor(gesto) == "arbitro" for gesto in GESTOS_DELEGAVEIS)
    assert politica.valor(Gesto.RESPONDER_DESVIO) == "humano"
    assert politica.estrutura_ilimitada
    assert politica.max_correcoes == 2
    assert {politica.origem(gesto) for gesto in Gesto} == {"preset:arbitragem_maxima"}


def test_personalizada_global_parcial_completa_com_governanca_maxima_nominal() -> None:
    """Os gestos que a personalizada não declara vêm da governança máxima."""
    politica = compor_politica_global(
        {"preset": "personalizada", "personalizada": {"responder_questao": "arbitro", "max_correcoes": 4}}
    )
    assert politica.valor(Gesto.RESPONDER_QUESTAO) == "arbitro"
    assert politica.origem(Gesto.RESPONDER_QUESTAO) == ORIGEM_GLOBAL
    assert politica.max_correcoes == 4
    assert politica.valor(Gesto.EXCLUIR) == "humano"
    assert politica.origem(Gesto.EXCLUIR) == "preset:governanca_maxima"


def test_personalizada_global_ignorada_com_preset_fixo_edge_case() -> None:
    """Caso de borda: a personalizada fica guardada, mas só vale quando o preset é ela."""
    personalizada = {"excluir": "arbitro", "estrutura": "ilimitado"}
    com_fixo = compor_politica_global({"preset": "governanca_maxima", "personalizada": personalizada})
    assert com_fixo == politica_padrao()
    voltou = compor_politica_global({"preset": "personalizada", "personalizada": personalizada})
    assert voltou.valor(Gesto.EXCLUIR) == "arbitro"
    assert voltou.estrutura_ilimitada


def test_preset_global_desconhecido_cai_em_governanca_maxima_edge_case() -> None:
    """Caso de borda: dado já gravado e ilegível não abre portão algum."""
    assert compor_politica_global({"preset": "tudo_liberado"}) == politica_padrao()


def test_personalizada_global_ignora_entradas_invalidas_edge_case() -> None:
    """Caso de borda: gesto desconhecido e valor fora do domínio não alteram a política."""
    politica = compor_politica_global(
        {"preset": "personalizada", "personalizada": {"inventado": "arbitro", "excluir": "qualquer", "fechar_goal": "arbitro"}}
    )
    assert politica.valor(Gesto.EXCLUIR) == "humano"
    assert politica.valor(Gesto.FECHAR_GOAL) == "arbitro"


def test_projeto_herdar_vale_a_global_nominal() -> None:
    """Projeto que herda tem os valores da global e a origem `global`."""
    for governanca in (None, {}, {"preset": "herdar"}):
        politica = compor_politica_do_projeto(governanca, "estrito", _global_arbitragem())
        assert politica.valores == _global_arbitragem().valores
        assert {politica.origem(gesto) for gesto in Gesto} == {ORIGEM_GLOBAL}


def test_projeto_preset_fixo_substitui_a_global_nominal() -> None:
    """Projeto com preset fixo ignora a global."""
    politica = compor_politica_do_projeto({"preset": "governanca_maxima"}, "estrito", _global_arbitragem())
    assert politica == politica_padrao()
    politica = compor_politica_do_projeto({"preset": "arbitragem_maxima"}, "estrito", politica_padrao())
    assert politica.valor(Gesto.CONSTRAINT) == "arbitro"
    assert politica.origem(Gesto.CONSTRAINT) == "preset:arbitragem_maxima"


def test_projeto_personalizada_parcial_sobre_a_global_nominal() -> None:
    """A personalizada do projeto sobrepõe só os gestos que declara."""
    governanca = {"preset": "personalizada", "personalizada": {"excluir": "humano", "max_correcoes": 0}}
    politica = compor_politica_do_projeto(governanca, "estrito", _global_arbitragem())
    assert politica.valor(Gesto.EXCLUIR) == "humano"
    assert politica.origem(Gesto.EXCLUIR) == ORIGEM_PROJETO
    assert politica.max_correcoes == 0
    assert politica.valor(Gesto.FECHAR_GOAL) == "arbitro"
    assert politica.origem(Gesto.FECHAR_GOAL) == ORIGEM_GLOBAL


def test_projeto_personalizada_ignorada_com_preset_fixo_edge_case() -> None:
    """Caso de borda: a personalizada guardada do projeto não vale sob preset fixo."""
    governanca = {"preset": "governanca_maxima", "personalizada": {"excluir": "arbitro"}}
    assert compor_politica_do_projeto(governanca, "estrito", _global_arbitragem()) == politica_padrao()


def test_legado_ilimitado_sem_governanca_vira_estrutura_ilimitada_nominal() -> None:
    """nivel_autonomia='ilimitado' com governança ausente ou herdar libera a estrutura."""
    for governanca in (None, {"preset": "herdar"}):
        politica = compor_politica_do_projeto(governanca, "ilimitado", politica_padrao())
        assert politica.estrutura_ilimitada
        assert politica.origem(Gesto.ESTRUTURA) == ORIGEM_LEGADO
        assert politica.valor(Gesto.EXCLUIR) == "humano"
        assert politica.origem(Gesto.EXCLUIR) == ORIGEM_GLOBAL


@pytest.mark.parametrize("governanca", [
    {"preset": "governanca_maxima"},
    {"preset": "arbitragem_maxima"},
    {"preset": "personalizada", "personalizada": {}},
])
def test_legado_nao_vale_com_preset_proprio_edge_case(governanca: dict[str, object]) -> None:
    """Caso de borda: o projeto que declara preset próprio não conserva o legado."""
    politica = compor_politica_do_projeto(governanca, "ilimitado", politica_padrao())
    assert politica.origem(Gesto.ESTRUTURA) != ORIGEM_LEGADO
    esperado_ilimitado = governanca["preset"] == "arbitragem_maxima"
    assert politica.estrutura_ilimitada is esperado_ilimitado


def test_legado_estrito_e_irrelevante_edge_case() -> None:
    """Caso de borda: nivel_autonomia estrito, ausente ou ilegível não muda nada."""
    for nivel in ("estrito", None, "", 7):
        assert compor_politica_do_projeto(None, nivel, politica_padrao()).estrutura_ilimitada is False


def test_legado_aceita_caixa_diferente_edge_case() -> None:
    """Caso de borda: o kernel lê o nível sem diferenciar caixa, e a política também."""
    assert compor_politica_do_projeto(None, "ILIMITADO", politica_padrao()).estrutura_ilimitada


def test_governanca_do_projeto_malformada_cai_em_herdar_edge_case() -> None:
    """Caso de borda: valor que não é objeto ou preset ilegível equivale a herdar."""
    for governanca in ("texto", 3, ["a"], {"preset": "fantasma"}):
        assert compor_politica_do_projeto(governanca, "estrito", _global_arbitragem()).valores == (
            _global_arbitragem().valores
        )


@pytest.mark.parametrize("gesto", GESTOS_DE_PAPEL)
def test_permite_humano_sempre_nominal(gesto: Gesto) -> None:
    """O humano pode todo gesto de papel, em qualquer preset."""
    for preset in PresetGovernanca:
        if preset in PRESETS_FIXOS:
            assert compor_politica_global({"preset": preset.value}).permite(gesto, PapelAutor.HUMANO)


@pytest.mark.parametrize("gesto", GESTOS_DELEGAVEIS)
def test_permite_arbitro_so_quando_a_politica_entrega_nominal(gesto: Gesto) -> None:
    """O árbitro pode o gesto sob arbitragem máxima e não pode sob governança máxima."""
    assert _global_arbitragem().permite(gesto, PapelAutor.ARBITRO)
    assert not politica_padrao().permite(gesto, PapelAutor.ARBITRO)


def test_permite_demais_papeis_nunca_edge_case() -> None:
    """Caso de borda: nem a arbitragem máxima dá o gesto a planejador, executor, revisor ou sistema."""
    politica = _global_arbitragem()
    for papel in (PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.SISTEMA):
        assert not any(politica.permite(gesto, papel) for gesto in GESTOS_POR_PAPEL)


@pytest.mark.parametrize("gesto", sorted(GESTOS_COM_LEITURA_PROPRIA, key=lambda gesto: gesto.value))
def test_permite_nao_se_aplica_aos_gestos_de_leitura_propria_edge_case(gesto: Gesto) -> None:
    """Caso de borda: perguntar permissão de papel por estes gestos é erro de quem chama."""
    with pytest.raises(ValueError, match="não se decide por papel"):
        politica_padrao().permite(gesto, PapelAutor.HUMANO)


def test_politica_resolvida_e_imutavel_edge_case() -> None:
    """Caso de borda: nem o preset fixo nem a política resolvida aceitam escrita."""
    politica = politica_padrao()
    with pytest.raises(TypeError):
        politica.valores[Gesto.EXCLUIR] = "arbitro"  # type: ignore[index]
    with pytest.raises(TypeError):
        PRESETS_FIXOS[PresetGovernanca.GOVERNANCA_MAXIMA][Gesto.EXCLUIR] = "arbitro"  # type: ignore[index]


def test_presets_fixos_cobrem_todos_os_gestos_nominal() -> None:
    """Cada preset fixo declara o valor de todos os gestos do catálogo."""
    for valores in PRESETS_FIXOS.values():
        assert set(valores) == set(Gesto)


def test_validar_configuracao_global_aceita_configuracoes_validas_nominal() -> None:
    """Sem problemas: vazio, só preset, personalizada parcial e completa."""
    assert validar_configuracao_global({}) == []
    assert validar_configuracao_global({"preset": "arbitragem_maxima"}) == []
    assert validar_configuracao_global({"preset": "personalizada", "personalizada": {"excluir": "arbitro"}}) == []
    completa = {gesto.value: valor for gesto, valor in PRESETS_FIXOS[PresetGovernanca.ARBITRAGEM_MAXIMA].items()}
    assert validar_configuracao_global({"preset": "personalizada", "personalizada": completa}) == []


@pytest.mark.parametrize("configuracao", [
    {"preset": "herdar"},
    {"preset": "inventado"},
    {"preset": 3},
    {"preset": ["personalizada"]},
    {"outra": "x"},
    {"personalizada": {"inventado": "humano"}},
    {"personalizada": {"excluir": "planejador"}},
    {"personalizada": {"estrutura": "humano"}},
    {"personalizada": {"excluir": "estrito"}},
    {"personalizada": {"max_correcoes": 6}},
    {"personalizada": {"max_correcoes": -1}},
    {"personalizada": {"max_correcoes": "2"}},
    {"personalizada": {"max_correcoes": True}},
    {"personalizada": ["excluir"]},
    "texto",
    None,
])
def test_validar_configuracao_global_recusa_edge_case(configuracao: object) -> None:
    """Caso de borda: preset, gesto ou valor inválido volta como problema."""
    assert validar_configuracao_global(configuracao)


def test_validar_configuracao_do_projeto_aceita_herdar_nominal() -> None:
    """O Projeto aceita `herdar`, os presets fixos e a personalizada parcial."""
    assert validar_configuracao_do_projeto({"preset": "herdar"}) == []
    assert validar_configuracao_do_projeto({"preset": "governanca_maxima"}) == []
    assert validar_configuracao_do_projeto({"preset": "personalizada", "personalizada": {"constraint": "arbitro"}}) == []


@pytest.mark.parametrize("configuracao", [
    {"preset": "fantasma"},
    {"preset": "arbitragem"},
    {"preset": "personalizada", "personalizada": {"integracao": "ninguem"}},
    {"preset": "personalizada", "personalizada": {"max_correcoes": 99}},
    {"extra": 1},
    [],
])
def test_validar_configuracao_do_projeto_recusa_edge_case(configuracao: object) -> None:
    """Caso de borda: o Projeto recusa o que o domínio não conhece."""
    assert validar_configuracao_do_projeto(configuracao)


def test_validar_personalizada_aceita_os_limites_de_max_correcoes_edge_case() -> None:
    """Caso de borda: 0 e 5 são os extremos válidos."""
    assert validar_personalizada({"max_correcoes": 0}) == []
    assert validar_personalizada({"max_correcoes": 5}) == []
    assert len(validar_personalizada({"max_correcoes": 6, "gesto_x": 1})) == 2


def test_enums_do_projeto_somam_herdar_aos_do_global_nominal() -> None:
    """PresetDoProjeto é PresetGovernanca mais `herdar`."""
    assert {preset.value for preset in PresetDoProjeto} == {preset.value for preset in PresetGovernanca} | {"herdar"}
