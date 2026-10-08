"""As ferramentas `aprovar_plano` e `responder_desvio`, ponta a ponta, e a recusa do `assumir_tarefa` sem plano."""

from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from tests.kernel.cenario_escopo import lista_do_goal, montar_kernel_com_goal
from tests.mcp.cenario_governanca import servidor

MAXIMA: str = "governanca_maxima"
ARBITRAGEM: str = "arbitragem_maxima"
AGENTES: tuple[str, ...] = ("planejador", "executor", "revisor")
COM_O_ARBITRO: dict[str, str] = {"responder_desvio": "arbitro"}


def _chamar(kernel: WriteKernel, papel: str, ferramenta: str, **argumentos: Any) -> dict[str, Any]:
    """A ferramenta chamada pelo servidor MCP do papel."""
    return servidor(kernel, papel).executar_ferramenta(ferramenta, argumentos)


def test_humano_aprova_versoes_sucessivas_com_o_seq_do_log_nominal() -> None:
    """Cada chamada acrescenta uma versão, assinada pelo humano e com o `versao_log` de antes dela."""
    kernel = montar_kernel_com_goal(MAXIMA)
    antes = kernel.obter_estado().versao_log
    primeira = _chamar(kernel, "humano", "aprovar_plano", id_goal="goal", id_sessao="sess")
    assert primeira["sucesso"] is True, primeira
    assert (primeira["id_goal"], primeira["versao"], primeira["seq"]) == ("goal", 1, antes)
    assert _chamar(kernel, "humano", "aprovar_plano", id_goal="goal")["sucesso"] is True
    planos = lista_do_goal(kernel, "planos")
    assert [(p["versao"], p["papel"], p["aprovado_por"]) for p in planos] == [(1, "humano", "david"), (2, "humano", "david")]
    assert planos[0]["seq"] == antes
    assert planos[1]["seq"] > planos[0]["seq"]


@pytest.mark.parametrize(
    ("preset", "aceito"),
    [(MAXIMA, False), (ARBITRAGEM, True)],
)
def test_arbitro_aprova_so_quando_a_politica_entrega_o_gesto_nominal(preset: str, aceito: bool) -> None:
    """Governança máxima recusa o árbitro na porta da ferramenta; arbitragem máxima o aceita e grava o papel."""
    kernel = montar_kernel_com_goal(preset)
    resposta = _chamar(kernel, "arbitro", "aprovar_plano", id_goal="goal")
    assert resposta["sucesso"] is aceito, resposta
    if aceito:
        assert lista_do_goal(kernel, "planos")[0]["papel"] == "arbitro"
    else:
        assert "aprovar_plano" in resposta["erro"]
        assert lista_do_goal(kernel, "planos") == []


@pytest.mark.parametrize("preset", [MAXIMA, ARBITRAGEM])
@pytest.mark.parametrize("papel", AGENTES)
@pytest.mark.parametrize(("ferramenta", "extra"), [("aprovar_plano", {}), ("responder_desvio", {"resposta": "seguir"})])
def test_planejador_executor_e_revisor_sao_recusados_edge_case(
    preset: str, papel: str, ferramenta: str, extra: dict[str, str]
) -> None:
    """Caso de borda: nenhum preset entrega as duas ferramentas a quem não é humano nem árbitro."""
    kernel = montar_kernel_com_goal(preset)
    resposta = _chamar(kernel, papel, ferramenta, id_goal="goal", **extra)
    assert resposta["sucesso"] is False
    assert ferramenta in resposta["erro"]


def test_humano_responde_ao_desvio_com_raiz_nominal() -> None:
    """A resposta leva a raiz dada, o texto, o autor e o seq do log de antes dela."""
    kernel = montar_kernel_com_goal(MAXIMA)
    antes = kernel.obter_estado().versao_log
    resposta = _chamar(kernel, "humano", "responder_desvio", id_goal="goal", resposta="conter a expansao", raiz="dec-1")
    assert resposta["sucesso"] is True, resposta
    assert lista_do_goal(kernel, "respostas_de_desvio") == [
        {"seq": antes, "respondido_por": "david", "papel": "humano", "raiz": "dec-1", "resposta": "conter a expansao"}
    ]


@pytest.mark.parametrize(
    ("preset", "personalizada", "aceito"),
    [(MAXIMA, None, False), (ARBITRAGEM, None, False), ("personalizada", COM_O_ARBITRO, True)],
)
def test_arbitro_responde_ao_desvio_so_na_personalizada_nominal(
    preset: str, personalizada: dict[str, str] | None, aceito: bool
) -> None:
    """Os dois presets fixos deixam o gesto com o humano; só a personalizada o põe com o árbitro."""
    kernel = montar_kernel_com_goal(preset, personalizada)
    resposta = _chamar(kernel, "arbitro", "responder_desvio", id_goal="goal", resposta="seguir")
    assert resposta["sucesso"] is aceito, resposta
    assert len(lista_do_goal(kernel, "respostas_de_desvio")) == int(aceito)


@pytest.mark.parametrize(
    "argumentos",
    [{"resposta": "   "}, {"resposta": "seguir", "raiz": "nao-existe"}],
)
def test_resposta_malformada_volta_com_o_motivo_do_kernel_edge_case(argumentos: dict[str, str]) -> None:
    """Caso de borda: texto vazio e raiz que não existe são recusados pelo kernel, e nada é gravado."""
    kernel = montar_kernel_com_goal(MAXIMA)
    resposta = _chamar(kernel, "humano", "responder_desvio", id_goal="goal", **argumentos)
    assert resposta["sucesso"] is False
    assert resposta["modo_de_falha"] == ModoFalhaMAST.ESTRUTURA_INCOMPLETA.value
    assert lista_do_goal(kernel, "respostas_de_desvio") == []


@pytest.mark.parametrize(("ferramenta", "extra"), [("aprovar_plano", {}), ("responder_desvio", {"resposta": "x"})])
def test_goal_inexistente_ou_que_nao_e_goal_edge_case(ferramenta: str, extra: dict[str, str]) -> None:
    """Caso de borda: o alvo precisa ser um Goal do grafo."""
    kernel = montar_kernel_com_goal(MAXIMA)
    for alvo in ("nao-existe", "t1"):
        resposta = _chamar(kernel, "humano", ferramenta, id_goal=alvo, **extra)
        assert resposta["sucesso"] is False
        assert "Goal" in resposta["erro"]


def test_assumir_tarefa_sem_plano_chega_ao_agente_sem_lock_residual_nominal() -> None:
    """A recusa do kernel volta com o motivo e o gesto que destrava, e a posse tomada é devolvida."""
    kernel = montar_kernel_com_goal(MAXIMA)
    resposta = _chamar(kernel, "executor", "assumir_tarefa", id_task="t1")
    assert resposta["sucesso"] is False
    assert resposta["modo_de_falha"] == ModoFalhaMAST.PLANO_NAO_APROVADO.value
    assert "o Goal goal não tem plano aprovado" in resposta["mensagem"]
    assert "aprovar_plano" in resposta["mensagem"]
    assert kernel.obter_dono_do_lock("t1") is None
    assert kernel.obter_estado().nos["t1"].propriedades["status"] == "pendente"


def test_assumir_tarefa_passa_depois_do_aprovar_plano_nominal() -> None:
    """Aprovado o plano, o mesmo executor assume a mesma Task."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _chamar(kernel, "executor", "assumir_tarefa", id_task="t1")["sucesso"] is False
    assert _chamar(kernel, "humano", "aprovar_plano", id_goal="goal")["sucesso"] is True
    resposta = _chamar(kernel, "executor", "assumir_tarefa", id_task="t1")
    assert resposta["sucesso"] is True, resposta
    assert kernel.obter_dono_do_lock("t1") == resposta["autor"]


def test_task_sem_goal_e_assumida_sem_plano_edge_case() -> None:
    """Caso de borda: a Task que nenhum Goal contém não depende de plano."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _chamar(kernel, "executor", "assumir_tarefa", id_task="solta")["sucesso"] is True


def test_seq_velho_por_causa_de_outro_escritor_e_refeito_edge_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda: se o log anda entre a leitura e o commit, a ferramenta relê o `versao_log` e tenta de novo."""
    kernel = montar_kernel_com_goal(MAXIMA)
    original = kernel.submeter_patch
    concorrente = {"ja": False}

    def submeter_com_corrida(proposta: Any) -> ResultadoSubmissao:
        if not concorrente["ja"]:
            concorrente["ja"] = True
            assert _chamar(kernel, "humano", "responder_desvio", id_goal="goal", resposta="outra")["sucesso"]
        return original(proposta)

    monkeypatch.setattr(kernel, "submeter_patch", submeter_com_corrida)
    resposta = _chamar(kernel, "humano", "aprovar_plano", id_goal="goal")
    assert resposta["sucesso"] is True, resposta
    assert lista_do_goal(kernel, "planos")[0]["seq"] == kernel.obter_estado().versao_log - 1
