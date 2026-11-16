"""O motivo do erro de uma sessão diz o que ela disse no `result` (T3l).

Na fumaça da fase 3, fora do app, o Claude Code não estava logado: as duas
invocações do planejador saíram em 2 s, e a parada disse só "sem saida
estruturada: codigo de saida 1, result com is_error (success)". A causa estava
no texto do `result`, no stream.
"""

from datetime import datetime
import json
from pathlib import Path

import pytest

from graphow.sessoes.leitura_stream import ler_stream
from graphow.sessoes.sessao_claude import ResultadoDeSessao

NAO_AUTENTICOU: str = "Failed to authenticate: OAuth session expired and could not be refreshed"
# O corte do que a sessão disse, escrito aqui para o teste falhar por comportamento contra o código de antes.
LIMITE: int = 200
# O `result` do stream real da tentativa 1 da fumaça (planejador-t1, 12/11), sem o que não importa.
RESULT_SEM_AUTENTICAR: dict[str, object] = {
    "type": "result", "subtype": "success", "is_error": True, "session_id": "6c0393a0", "total_cost_usd": 0, "num_turns": 1,
    "duration_ms": 341, "stop_reason": "stop_sequence", "terminal_reason": "api_error", "api_error_status": None,
    "result": NAO_AUTENTICOU,
}


def _resultado(evento: dict[str, object] | None, *, codigo_saida: int = 1) -> ResultadoDeSessao:
    """O resultado de uma invocação cujo stream traz o `init` e, quando dado, o `result`."""
    agora = datetime.now()
    linhas = [json.dumps({"type": "system", "subtype": "init", "session_id": "6c0393a0", "model": "claude-opus-5-5"})]
    linhas += [json.dumps(evento)] if evento is not None else []
    return ResultadoDeSessao(comando=("claude",), arquivo_stream=Path("s.jsonl"), inicio=agora, fim=agora,
                             codigo_saida=codigo_saida, tempo_esgotado=False, leitura=ler_stream(linhas))


def _com_o_texto(texto: str) -> ResultadoDeSessao:
    """O `result` com erro e o texto dado."""
    return _resultado({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": texto}, codigo_saida=0)


def test_sessao_que_nao_autentica_diz_a_causa_no_motivo_nominal() -> None:
    """T3l.1: o `result` real da fumaça sem login leva ao motivo o que a sessão disse."""
    resultado = _resultado(RESULT_SEM_AUTENTICAR)

    assert resultado.motivo_do_erro == f'codigo de saida 1, result com is_error (success), a sessao disse "{NAO_AUTENTICOU}"'
    assert resultado.em_dicionario()["erro"] == resultado.motivo_do_erro


def test_motivos_sem_o_texto_do_erro_ficam_como_antes_edge_case() -> None:
    """T3l.3 (contraprova): sem `result`, com o código de saída sozinho e com o erro da API sem texto, nada muda."""
    sem_result = _resultado(None)
    so_o_codigo = _resultado({"type": "result", "subtype": "success", "is_error": False, "result": "feito"}, codigo_saida=3)
    da_api = _resultado({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 400,
                         "api_error": "invalid_request_error", "terminal_reason": "api_error"})

    assert sem_result.motivo_do_erro == "codigo de saida 1, sem evento result no stream"
    assert so_o_codigo.motivo_do_erro == "codigo de saida 3"
    assert da_api.motivo_do_erro == "codigo de saida 1, result com is_error (success): erro da API 400 invalid_request_error"


def test_erro_da_api_com_texto_leva_os_dois_edge_case() -> None:
    """Caso de borda: o `result` com status de erro da API e texto leva ao motivo o erro e o que a sessão disse."""
    resultado = _resultado({**RESULT_SEM_AUTENTICAR, "api_error_status": 401, "api_error": "authentication_error"})

    assert resultado.motivo_do_erro == ("codigo de saida 1, result com is_error (success): erro da API 401 authentication_error, "
                                        f'a sessao disse "{NAO_AUTENTICOU}"')


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("\n\n  API Error: 500 erro interno  \r\nmais detalhes\n", 'result com is_error (error_during_execution), a sessao disse "API Error: 500 erro interno"'),
        ("x" * 300, f'result com is_error (error_during_execution), a sessao disse "{"x" * LIMITE}..."'),
        ("x" * LIMITE, f'result com is_error (error_during_execution), a sessao disse "{"x" * LIMITE}"'),
        ("  \n \r\n", "result com is_error (error_during_execution)"),
        ("", "result com is_error (error_during_execution)"),
        ("API Error: \ud83d truncado", 'result com is_error (error_during_execution), a sessao disse "API Error: ? truncado"'),
        ("erro \x1b[31mvermelho\x1b[0m\tfim", 'result com is_error (error_during_execution), a sessao disse "erro ?[31mvermelho?[0m fim"'),
    ],
    ids=["so-a-primeira-linha", "cortado-em-200", "exatamente-200", "so-espacos", "vazio", "surrogate-solto", "controle-e-tab"],
)
def test_texto_do_erro_entra_cortado_e_so_com_a_primeira_linha_edge_case(texto: str, esperado: str) -> None:
    """T3l.3 e T3l.6: a primeira linha com conteúdo, sem as pontas, cortada no limite; o que não se imprime vira `?`."""
    motivo = _com_o_texto(texto).motivo_do_erro

    assert motivo == esperado
    assert motivo.encode("utf-8").decode("utf-8") == motivo
