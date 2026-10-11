"""O stream-json lido: a sessão do init, o último resultado e o que falta não vira número."""

import json
from pathlib import Path

from graphow.sessoes.leitura_stream import UsoDeTokens, ler_stream

from tests.sessoes.apoio import STREAM_DA_ENXUTA


def _resultado(sessao: str, custo: float, **campos: object) -> str:
    """Um evento `result` mínimo."""
    return json.dumps({"type": "result", "subtype": "success", "session_id": sessao, "total_cost_usd": custo, **campos})


def test_stream_gravado_da_enxuta_da_sessao_texto_custo_e_tokens_nominal() -> None:
    """O stream recortado da execução de controle do estoque, lido como a bancada o lê."""
    leitura = ler_stream(STREAM_DA_ENXUTA.read_text(encoding="utf-8").splitlines())

    assert leitura.session_id == "4cb36a24-6f3f-4ad6-8179-f4aadfd02d53"
    assert leitura.modelo == "claude-opus-5-5"
    resultado = leitura.resultado
    assert resultado is not None
    assert resultado.texto.startswith("## Relatório — chamado 142")
    assert resultado.is_error is False
    assert round(resultado.custo_usd, 2) == 5.03
    assert resultado.turnos == 88
    assert resultado.duracao_ms == 1198251
    assert resultado.tokens == UsoDeTokens(entrada=148, saida=101671, cache_leitura=5811167, cache_criacao=287154)
    assert resultado.tokens.total == 6_200_140


def test_model_usage_soma_os_modelos_nominal() -> None:
    """Sessão Opus com subagentes Sonnet: o total soma os dois."""
    uso = {
        "claude-opus": {"inputTokens": 1, "outputTokens": 2, "cacheReadInputTokens": 3, "cacheCreationInputTokens": 4},
        "claude-sonnet": {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 30, "cacheCreationInputTokens": 40},
    }

    resultado = ler_stream([_resultado("s", 1.0, modelUsage=uso)]).resultado

    assert resultado is not None
    assert resultado.tokens.total == 110
    assert set(resultado.tokens_por_modelo) == {"claude-opus", "claude-sonnet"}


def test_vale_o_ultimo_resultado_e_lixo_e_ignorado_edge_case() -> None:
    """Caso de borda: linha truncada, texto solto e JSON que não é objeto ficam de fora; o último `result` vale."""
    linhas = [
        "texto solto",
        '{"type": "result", "total_cost',
        "[1, 2]",
        _resultado("s", 1.0),
        _resultado("s", 2.5, is_error=True, num_turns=3),
    ]

    resultado = ler_stream(linhas).resultado

    assert resultado is not None
    assert resultado.custo_usd == 2.5
    assert resultado.is_error is True
    assert resultado.turnos == 3


def test_stream_sem_resultado_nao_inventa_numero_edge_case() -> None:
    """Caso de borda: o processo morreu depois do init; há sessão e não há resultado."""
    leitura = ler_stream([json.dumps({"type": "system", "subtype": "init", "session_id": "s-1", "model": "opus"})])

    assert leitura.session_id == "s-1"
    assert leitura.resultado is None


def test_campos_ausentes_ou_de_tipo_errado_contam_zero_edge_case() -> None:
    """Caso de borda: custo em texto, turnos booleanos e `modelUsage` torto não quebram a leitura."""
    resultado = ler_stream([_resultado("s", "caro", num_turns=True, modelUsage=[1], duration_ms="x")]).resultado

    assert resultado is not None
    assert (resultado.custo_usd, resultado.turnos, resultado.duracao_ms) == (0.0, 0, None)
    assert resultado.tokens.total == 0


def test_sessao_vem_do_resultado_quando_falta_o_init_edge_case() -> None:
    """Caso de borda: sem `system/init`, a sessão sai do próprio resultado."""
    assert ler_stream([_resultado("s-2", 0.1)]).session_id == "s-2"


def test_leitura_aceita_arquivo_aberto_nominal(tmp_path: Path) -> None:
    """O arquivo do stream lido linha a linha, sem carregar tudo antes."""
    caminho = tmp_path / "s.jsonl"
    caminho.write_text(_resultado("s-3", 0.2) + "\n", encoding="utf-8")

    with caminho.open(encoding="utf-8") as arquivo:
        assert ler_stream(arquivo).session_id == "s-3"
