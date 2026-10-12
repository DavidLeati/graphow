"""O limite de uso da conta e o erro passageiro da API não são falha da fatia: o laço espera, repete ou para retomável.

Na bancada, a janela de uso estourou e a fatia M2.K1.1 do agenda-salas gastou
as duas tentativas e as duas retomadas em dez segundos, e virou pendência.
"""

from datetime import datetime
import json
from pathlib import Path

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.falhas_da_api import falha_da_api
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.sessoes.leitura_stream import ler_stream
from graphow.sessoes.sessao_claude import ResultadoDeSessao

from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
# As linhas do stream da bancada (agenda-salas, M2.K1.1), sem o que não importa.
STREAM_DO_LIMITE: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "c1d4", "model": "claude-opus-5-5"}),
    json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1791812400,
                                                                "rateLimitType": "five_hour"}, "session_id": "c1d4"}),
    json.dumps({"type": "result", "subtype": "success", "is_error": True, "session_id": "c1d4", "total_cost_usd": 0,
                "num_turns": 1, "terminal_reason": "api_error", "api_error_status": 429, "api_error": "usage_limit_reached",
                "result": "You've hit your session limit · resets 10:40am (America/Sao_Paulo)"}),
]


def _resultado(linhas: list[str]) -> ResultadoDeSessao:
    """O resultado de uma invocação com o stream dado."""
    agora = datetime.now()
    return ResultadoDeSessao(comando=("claude",), arquivo_stream=Path("s.jsonl"), inicio=agora, fim=agora, codigo_saida=1,
                             tempo_esgotado=False, leitura=ler_stream(linhas))


def test_limite_de_uso_e_erro_passageiro_se_reconhecem_pelo_stream_edge_case() -> None:
    """Caso de borda (bancada C): o stream real do limite de uso e o 529 da sobrecarga se distinguem do erro do papel."""
    limite = falha_da_api(_resultado(STREAM_DO_LIMITE))
    sobrecarga = falha_da_api(_resultado([json.dumps({"type": "result", "is_error": True, "subtype": "success",
                                                      "api_error_status": 529, "api_error": "overloaded_error",
                                                      "terminal_reason": "api_error"})]))
    do_papel = falha_da_api(_resultado([json.dumps({"type": "result", "is_error": True, "subtype": "error_during_execution"})]))

    assert limite is not None and limite.limite_de_uso and "five_hour" in limite.descricao and limite.volta_em
    assert sobrecarga is not None and not sobrecarga.limite_de_uso and "529" in sobrecarga.descricao
    assert do_papel is None


def test_limite_de_uso_para_o_laco_sem_gastar_a_tentativa_e_a_retomada_fecha_nominal(tmp_path: Path) -> None:
    """Bancada C: a fatia que esbarra no limite volta a pendente sem falha; o laço para retomável e, retomado, fecha."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(0, {"limite": True})
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador(esperar=lambda segundos: None)

    parada = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.LIMITE_DE_USO, parada.mensagem
    assert "limite de uso da conta (five_hour)" in parada.mensagem and "a tentativa em curso nao conta" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and (estado.fatias[0].status, estado.fatias[0].tentativas, estado.fatias[0].falhas) == ("pendente", 0, 0)
    assert len(bancada.chamadas("executor")) == 1, "nem retomada nem nova tentativa contra o limite"
    assert orquestrador.rodar("goal-soma", AUTONOMO).fechou


def test_erro_passageiro_da_api_espera_e_repete_a_invocacao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o 529 da sobrecarga espera o recuo e repete a mesma invocação; a fatia não falha."""
    roteiro = roteiro_completo()
    roteiro["executor"].insert(0, {"sobrecarga": True})
    bancada = montar_bancada(tmp_path, roteiro)
    esperas: list[float] = []

    parada = bancada.orquestrador(esperar=esperas.append).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert esperas == [30.0]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].falhas == 0


def test_erro_passageiro_que_nao_passa_para_o_laco_retomavel_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a sobrecarga que persiste depois das três esperas para o laço, com o motivo, sem pendência."""
    roteiro = roteiro_completo()
    roteiro["executor"][0:0] = [{"sobrecarga": True} for _ in range(4)]
    bancada = montar_bancada(tmp_path, roteiro)
    esperas: list[float] = []

    parada = bancada.orquestrador(esperar=esperas.append).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.LIMITE_DE_USO and "erro da API (529 overloaded_error)" in parada.mensagem
    assert esperas == [30.0, 120.0, 300.0]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.fatias[0].status == "pendente" and not estado.bloqueadas()
