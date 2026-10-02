"""Testes da ferramenta configurar_governanca: sempre humana, mescla a personalizada e devolve a política efetiva."""

import pytest

from graphow.core.governanca import Gesto
from graphow.core.types import TipoNo
from tests.mcp.cenario_governanca import montar_kernel, servidor

ID_GLOBAL = "governanca-global"


def _configurar(kernel, papel: str, argumentos: dict) -> dict:
    """Chama configurar_governanca sob o papel informado."""
    return servidor(kernel, papel).executar_ferramenta("configurar_governanca", argumentos)


@pytest.mark.parametrize("papel", ["planejador", "executor", "revisor", "arbitro"])
def test_configurar_governanca_e_recusada_a_todo_papel_de_agente_edge_case(papel: str) -> None:
    """Caso de borda: nenhum papel de agente, árbitro inclusive, escreve a política."""
    kernel = montar_kernel()

    no_global = _configurar(kernel, papel, {"escopo": "global", "preset": "arbitragem_maxima"})
    no_projeto = _configurar(kernel, papel, {"escopo": "proj-a", "preset": "arbitragem_maxima"})

    assert no_global["sucesso"] is False
    assert no_projeto["sucesso"] is False
    assert "exige uma sessao humana" in no_global["erro"]
    assert not kernel.obter_view().contem_no(ID_GLOBAL)
    assert kernel.obter_view().obter_no("proj-a").obter_propriedade("governanca") is None


def test_configurar_autonomia_projeto_segue_funcionando_como_legado_nominal() -> None:
    """A ferramenta antiga continua do humano, continua gravando e continua recusada ao agente."""
    kernel = montar_kernel()

    humano = servidor(kernel, "humano").executar_ferramenta(
        "configurar_autonomia_projeto", {"id_projeto": "proj-a", "nivel_autonomia": "ilimitado"}
    )
    arbitro = servidor(kernel, "arbitro").executar_ferramenta(
        "configurar_autonomia_projeto", {"id_projeto": "proj-a", "nivel_autonomia": "estrito"}
    )

    assert humano["sucesso"] is True, humano
    assert arbitro["sucesso"] is False
    assert kernel.obter_view().obter_no("proj-a").obter_propriedade("nivel_autonomia") == "ilimitado"


def test_cria_o_no_global_e_devolve_a_politica_efetiva_nominal() -> None:
    """No global o nó nasce sem hierarquia, e a resposta traz o valor e a origem de cada gesto."""
    kernel = montar_kernel()

    resposta = _configurar(kernel, "humano", {"escopo": "global", "preset": "arbitragem_maxima"})

    assert resposta["sucesso"] is True, resposta
    no = kernel.obter_view().obter_no(ID_GLOBAL)
    assert no.tipo == TipoNo.GOVERNANCA
    assert no.obter_propriedade("preset") == "arbitragem_maxima"
    assert set(resposta["politica_efetiva"]) == {gesto.value for gesto in Gesto}
    assert resposta["politica_efetiva"]["responder_questao"] == "arbitro"
    assert resposta["politica_efetiva"]["estrutura"] == "ilimitado"
    assert resposta["origens"]["excluir"] == "preset:arbitragem_maxima"


def test_segunda_configuracao_global_atualiza_o_no_existente_nominal() -> None:
    """Configurar de novo troca as propriedades do mesmo nó, sem criar outro."""
    kernel = montar_kernel()
    _configurar(kernel, "humano", {"escopo": "global", "preset": "arbitragem_maxima"})

    resposta = _configurar(kernel, "humano", {"escopo": "global", "preset": "governanca_maxima"})

    assert resposta["sucesso"] is True, resposta
    assert kernel.obter_view().obter_no(ID_GLOBAL).obter_propriedade("preset") == "governanca_maxima"
    assert len(kernel.obter_view().listar_nos_por_tipo(TipoNo.GOVERNANCA)) == 1
    assert resposta["politica_efetiva"]["responder_questao"] == "humano"


def test_trocar_de_preset_preserva_a_personalizada_nominal() -> None:
    """A personalizada é mesclada na salva e sobrevive à troca para um preset fixo e à volta."""
    kernel = montar_kernel()
    _configurar(kernel, "humano", {"escopo": "global", "preset": "personalizada", "personalizada": {"excluir": "arbitro"}})
    _configurar(kernel, "humano", {"escopo": "global", "preset": "personalizada", "personalizada": {"integracao": "arbitro"}})

    fixo = _configurar(kernel, "humano", {"escopo": "global", "preset": "governanca_maxima"})
    de_volta = _configurar(kernel, "humano", {"escopo": "global", "preset": "personalizada"})

    no = kernel.obter_view().obter_no(ID_GLOBAL)
    assert no.obter_propriedade("personalizada") == {"excluir": "arbitro", "integracao": "arbitro"}
    assert fixo["politica_efetiva"]["excluir"] == "humano"
    assert de_volta["politica_efetiva"]["excluir"] == "arbitro"
    assert de_volta["politica_efetiva"]["integracao"] == "arbitro"
    assert de_volta["politica_efetiva"]["responder_questao"] == "humano"
    assert de_volta["origens"]["excluir"] == "global"


def test_aplica_herdar_por_gesto_no_projeto_nominal() -> None:
    """No Projeto, 'herdar' apaga a sobrescrita do gesto, e o gesto volta à origem global."""
    kernel = montar_kernel()
    _configurar(kernel, "humano", {"escopo": "global", "preset": "governanca_maxima"})
    primeira = _configurar(
        kernel,
        "humano",
        {"escopo": "proj-a", "preset": "personalizada", "personalizada": {"excluir": "arbitro", "fechar_goal": "arbitro"}},
    )
    segunda = _configurar(
        kernel, "humano", {"escopo": "proj-a", "preset": "personalizada", "personalizada": {"excluir": "herdar"}}
    )

    assert primeira["origens"]["excluir"] == "projeto"
    assert primeira["politica_efetiva"]["excluir"] == "arbitro"
    assert segunda["sucesso"] is True, segunda
    assert segunda["politica_efetiva"]["excluir"] == "humano"
    assert segunda["origens"]["excluir"] == "global"
    assert segunda["politica_efetiva"]["fechar_goal"] == "arbitro"
    guardada = kernel.obter_view().obter_no("proj-a").obter_propriedade("governanca")
    assert guardada == {"preset": "personalizada", "personalizada": {"fechar_goal": "arbitro"}}


def test_projeto_trocar_para_herdar_preserva_a_personalizada_nominal() -> None:
    """O preset 'herdar' vale a global e guarda a personalizada do Projeto à parte."""
    kernel = montar_kernel()
    _configurar(kernel, "humano", {"escopo": "proj-a", "preset": "personalizada", "personalizada": {"excluir": "arbitro"}})

    resposta = _configurar(kernel, "humano", {"escopo": "proj-a", "preset": "herdar"})

    guardada = kernel.obter_view().obter_no("proj-a").obter_propriedade("governanca")
    assert guardada == {"preset": "herdar", "personalizada": {"excluir": "arbitro"}}
    assert resposta["politica_efetiva"]["excluir"] == "humano"


@pytest.mark.parametrize(
    "argumentos",
    [
        {"escopo": "global", "preset": "inexistente"},
        {"escopo": "global", "preset": "herdar"},
        {"escopo": "global", "preset": "personalizada", "personalizada": {"excluir": "herdar"}},
        {"escopo": "global", "preset": "personalizada", "personalizada": {"gesto_inventado": "humano"}},
        {"escopo": "global", "preset": "personalizada", "personalizada": {"excluir": "talvez"}},
        {"escopo": "global", "preset": "personalizada", "personalizada": {"max_correcoes": 9}},
        {"escopo": "global", "preset": "personalizada", "personalizada": "excluir=arbitro"},
        {"escopo": "proj-a", "preset": "personalizada", "personalizada": {"gesto_inventado": "herdar"}},
        {"escopo": "proj-a", "preset": "personalizada", "personalizada": {"estrutura": "arbitro"}},
        {"escopo": "proj-inexistente", "preset": "herdar"},
        {"escopo": "sess-a", "preset": "herdar"},
    ],
)
def test_recusa_configuracao_invalida_sem_gravar_edge_case(argumentos: dict) -> None:
    """Caso de borda: preset, gesto ou valor fora do domínio e escopo inexistente são recusados, sem escrita."""
    kernel = montar_kernel()
    versao_antes = kernel.obter_view().versao_log

    resposta = _configurar(kernel, "humano", argumentos)

    assert resposta["sucesso"] is False
    assert kernel.obter_view().versao_log == versao_antes
    assert not kernel.obter_view().contem_no(ID_GLOBAL)
