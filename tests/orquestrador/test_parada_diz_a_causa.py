"""A parada do laço diz o que a sessão disse quando ela termina em erro (T3l).

Na fumaça da fase 3, o Claude Code não estava logado, e a parada disse só "O
plano nao conferiu: sem saida estruturada: codigo de saida 1, result com
is_error (success)". O motivo estava no stream do planejador.
"""

from pathlib import Path

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco

from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo

NAO_AUTENTICOU: str = "Failed to authenticate: OAuth session expired and could not be refreshed"


def test_planejador_que_termina_em_erro_para_o_goal_com_o_que_a_sessao_disse_nominal(tmp_path: Path) -> None:
    """T3l.2: as duas invocações do planejador terminam em erro com o texto da falta de login, e a parada o traz."""
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"texto": NAO_AUTENTICOU, "erro": True, "custo": 0.0} for _ in range(2)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo"))

    assert parada.motivo == MotivoDaParada.FALHA
    assert parada.mensagem.startswith("O plano nao conferiu: sem saida estruturada: ")
    assert f'a sessao disse "{NAO_AUTENTICOU}"' in parada.mensagem
    primeira, retomada = bancada.chamadas("planejador")
    assert "--resume" not in primeira["argv"] and "--resume" in retomada["argv"]
    assert bancada.chamadas("aceite") == []
