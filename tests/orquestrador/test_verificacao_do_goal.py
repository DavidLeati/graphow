"""A verificação do Goal: a prova que ela precisa trazer e a suíte que o orquestrador roda no commit verificado."""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador import modelo_do_goal as m, verificacao_do_goal
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.saidas import TITULO_DA_SUITE_VERMELHA
from graphow.orquestrador.suite import ResultadoDaSuite

from tests.orquestrador.apoio_laco import montar_bancada, verificacao
from tests.orquestrador.test_retomada import roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _evidencia(bancada: Any, numero: int) -> dict[str, Any]:
    """As propriedades da Evidence da verificação de número dado."""
    no = bancada.kernel.obter_view().obter_no(f"ver-goal-soma-{numero}")
    assert no is not None
    return dict(no.propriedades)


def test_suite_vermelha_no_commit_verificado_reprova_a_verificacao_que_dizia_atende_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O verificador diz que tudo atende, a suíte do orquestrador falha: vira bloqueante, correção e nova verificação."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    original = verificacao_do_goal.rodar_suite
    chamadas: list[str] = []

    def vermelha_na_primeira(*argumentos: Any, **nomeados: Any) -> ResultadoDaSuite:
        chamadas.append("suite")
        return ResultadoDaSuite("python verificar.py", 1, "AssertionError: C1") if len(chamadas) == 1 else original(*argumentos, **nomeados)

    monkeypatch.setattr(verificacao_do_goal, "rodar_suite", vermelha_na_primeira)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    primeira, segunda = _evidencia(bancada, 1), _evidencia(bancada, 2)
    assert primeira["veredito"] == m.VEREDITO_COM_BLOQUEANTE
    assert [achado["titulo"] for achado in primeira["bloqueantes"]] == [TITULO_DA_SUITE_VERMELHA]
    assert primeira["suite_do_orquestrador"]["codigo"] == 1 and not primeira["suite_do_orquestrador"]["passou"]
    assert segunda["suite_do_orquestrador"]["passou"] and segunda["comandos"][0]["codigo"] == 0
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [fatia.codigo for fatia in estado.fatias] == ["F1", "F2", "K1.1"]


def test_verificacao_com_prova_vazia_nao_fecha_o_goal_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o verificador que responde "." duas vezes não fecha nada; o laço para com o motivo."""
    roteiro = roteiro_farto()
    vazia = verificacao("atende")
    vazia["saida"]["criterios"] = [{**parecer, "prova": "."} for parecer in vazia["saida"]["criterios"]]
    vazia["saida"]["comandos"] = []
    roteiro["verificador"] = [copy.deepcopy(vazia), copy.deepcopy(vazia)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert "A verificacao nao conferiu" in parada.mensagem and "comandos" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and not estado.fechado and estado.verificacoes == ()
