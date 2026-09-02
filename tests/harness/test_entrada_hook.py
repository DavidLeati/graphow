"""Leitura do payload que o hook entrega na entrada padrão.

O arquivo de hooks dependia de `$CLAUDE_SESSION_ID`, variável que o ambiente não
define. O id da sessão chega no JSON da entrada padrão, e é lá que ele é lido.
Ver defeito V-02.
"""

import io

from graphow.harness.entrada_hook import (
    MODELO_DESCONHECIDO,
    EntradaDeHook,
    interpretar_entrada_de_hook,
    ler_entrada_de_hook,
)


def test_entrada_traz_sessao_modelo_e_resumo_nominal() -> None:
    """O payload completo preenche os três campos que o harness aproveita."""
    entrada = interpretar_entrada_de_hook(
        '{"session_id": "sess-abc", "model": "claude-opus-5", "source": "startup"}'
    )

    assert entrada == EntradaDeHook(id_sessao="sess-abc", modelo="claude-opus-5", resumo="startup")
    assert entrada.tem_sessao


def test_modelo_como_objeto_e_reduzido_ao_identificador_nominal() -> None:
    """Alguns payloads descrevem o modelo como objeto, não como texto."""
    entrada = interpretar_entrada_de_hook(
        '{"session_id": "s1", "model": {"id": "claude-opus-5", "display_name": "Opus"}}'
    )

    assert entrada.modelo == "claude-opus-5"


def test_motivo_de_encerramento_vira_resumo_nominal() -> None:
    """No fim da sessão o payload traz `reason`, e ele descreve a fase."""
    entrada = interpretar_entrada_de_hook('{"session_id": "s1", "reason": "logout"}')

    assert entrada.resumo == "logout"


def test_entrada_vazia_nao_inventa_sessao_edge_case() -> None:
    """Caso de borda: sem entrada, o resultado é explicitamente sem sessão."""
    entrada = interpretar_entrada_de_hook("")

    assert not entrada.tem_sessao
    assert entrada.modelo == MODELO_DESCONHECIDO


def test_json_malformado_nao_derruba_o_hook_edge_case() -> None:
    """Caso de borda: um payload quebrado vira ausência de dados, não exceção."""
    assert interpretar_entrada_de_hook("{isso nao e json") == EntradaDeHook()
    assert interpretar_entrada_de_hook("[1, 2, 3]") == EntradaDeHook()


def test_sessao_apenas_com_espacos_nao_conta_como_sessao_edge_case() -> None:
    """Caso de borda: era exatamente esse valor que virava o caminho '/nos/'."""
    entrada = interpretar_entrada_de_hook('{"session_id": "   "}')

    assert not entrada.tem_sessao


def test_leitura_consome_o_fluxo_de_texto_nominal() -> None:
    """A leitura acontece sobre um fluxo injetável, não sobre sys.stdin fixo."""
    entrada = ler_entrada_de_hook(io.StringIO('{"session_id": "sess-fluxo"}'))

    assert entrada.id_sessao == "sess-fluxo"
