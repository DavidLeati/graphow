"""A parada do laço diz o que a sessão disse quando ela termina em erro (T3l).

Na fumaça da fase 3, o Claude Code não estava logado, e a parada disse só "O
plano nao conferiu: sem saida estruturada: codigo de saida 1, result com
is_error (success)". O motivo estava no stream do planejador.
"""

from pathlib import Path

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco

from tests.orquestrador.apoio_laco import Bancada, montar_bancada, roteiro_completo

NAO_AUTENTICOU: str = "Failed to authenticate: OAuth session expired and could not be refreshed"
# O texto de um erro 400 como o Claude Code o escreve: o corpo da resposta da API, em JSON, depois do status.
CORPO_400: str = ('API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"prompt is too long"},'
                  '"request_id":"req_011"}')
AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _planejador_que_termina_em_erro(tmp_path: Path, texto: str) -> Bancada:
    """A bancada em que as duas invocações do planejador terminam em erro com o texto dado."""
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"texto": texto, "erro": True, "custo": 0.0} for _ in range(2)]
    return montar_bancada(tmp_path, roteiro)


def test_planejador_que_termina_em_erro_para_o_goal_com_o_que_a_sessao_disse_nominal(tmp_path: Path) -> None:
    """T3l.2: as duas invocações do planejador terminam em erro com o texto da falta de login, e a parada o traz."""
    bancada = _planejador_que_termina_em_erro(tmp_path, NAO_AUTENTICOU)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert parada.mensagem.startswith("O plano nao conferiu: sem saida estruturada: ")
    assert f'a sessao disse "{NAO_AUTENTICOU}"' in parada.mensagem
    primeira, retomada = bancada.chamadas("planejador")
    assert "--resume" not in primeira["argv"] and "--resume" in retomada["argv"]
    assert bancada.chamadas("aceite") == []


def test_json_no_texto_do_erro_nao_e_lido_como_a_saida_do_papel_edge_case(tmp_path: Path) -> None:
    """T3l.5 (achado 1 da revisão): o corpo JSON de um erro 400 não vira o plano; a parada diz o que a sessão disse."""
    bancada = _planejador_que_termina_em_erro(tmp_path, CORPO_400)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert parada.mensagem.startswith("O plano nao conferiu: sem saida estruturada: ")
    assert 'a sessao disse "API Error: 400 {"type":"error"' in parada.mensagem
    assert "falta '" not in parada.mensagem and "campo nao previsto" not in parada.mensagem


def test_caractere_que_nao_se_codifica_no_texto_do_erro_nao_derruba_o_laco_edge_case(tmp_path: Path) -> None:
    """T3l.6 (achado 3 da revisão): o surrogate solto no `result` vira `?`, e o laço devolve a parada em vez de levantar."""
    bancada = _planejador_que_termina_em_erro(tmp_path, "API Error: " + chr(0xD83D) + " truncado")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA
    assert 'a sessao disse "API Error: ? truncado"' in parada.mensagem
    assert len(bancada.chamadas("planejador")) == 2
