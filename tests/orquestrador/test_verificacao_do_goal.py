"""A verificação do Goal: a prova que ela precisa trazer e a suíte que o orquestrador roda no commit verificado."""

import copy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador import modelo_do_goal as m, verificacao_do_goal
from graphow.orquestrador.comandos_do_stream import comandos_nao_rodados
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.saidas import TITULO_DA_SUITE_VERMELHA
from graphow.orquestrador.suite import ResultadoDaSuite
from graphow.sessoes.leitura_stream import LeituraDoStream
from graphow.sessoes.sessao_claude import ResultadoDeSessao

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


def _mentirosa() -> dict[str, Any]:
    """A verificação que declara `python verificar.py` sem que o stream mostre a chamada."""
    resposta = verificacao("atende")
    resposta["bash"] = ["ls"]
    return resposta


def test_comando_declarado_que_nao_rodou_volta_a_sessao_e_a_resposta_honesta_fecha_nominal(tmp_path: Path) -> None:
    """O comando declarado que o stream não mostra volta à mesma sessão; a resposta que o rodou fecha o Goal."""
    roteiro = roteiro_farto()
    roteiro["verificador"] = [_mentirosa(), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    primeira, segunda = bancada.chamadas("verificador")
    assert "--resume" in segunda["argv"] and "--resume" not in primeira["argv"]
    assert "nao aparecem nas chamadas Bash" in segunda["stdin"] and "python verificar.py" in segunda["stdin"]


def test_verificador_que_insiste_no_comando_que_nao_rodou_nao_fecha_o_goal_edge_case(tmp_path: Path) -> None:
    """Caso de borda: duas respostas com comando inventado, nenhuma verificação gravada, e a parada diz qual comando."""
    roteiro = roteiro_farto()
    roteiro["verificador"] = [_mentirosa(), _mentirosa()]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert "nao aparecem nas chamadas Bash" in parada.mensagem and "`python verificar.py`" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.verificacoes == ()


def test_comando_declarado_vale_como_parte_da_chamada_e_sem_o_prompt_edge_case(tmp_path: Path) -> None:
    """Caso de borda: `$ python -m  unittest -v` vale dentro de `cd x && python -m unittest -v 2>&1 | tail`; o inventado não."""
    stream = tmp_path / "verificador.jsonl"
    chamada = {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "cd x && python -m unittest -v 2>&1 | tail -5"}}
    leitura = {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "pytest"}}
    linhas = [{"type": "assistant", "message": {"content": [chamada, leitura]}}, {"type": "user", "message": {"content": "pytest"}}]
    stream.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8")
    agora = datetime.now()
    resultado = ResultadoDeSessao(
        comando=(), arquivo_stream=stream, inicio=agora, fim=agora, codigo_saida=0, tempo_esgotado=False, leitura=LeituraDoStream()
    )

    faltando = comandos_nao_rodados(["$ python -m  unittest -v", "pytest -q"], [resultado])

    assert faltando == ("pytest -q",)
