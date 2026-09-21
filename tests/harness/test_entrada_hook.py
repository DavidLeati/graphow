"""Leitura do payload que o hook entrega na entrada padrão.

O arquivo de hooks dependia de `$CLAUDE_SESSION_ID`, variável que o ambiente não
define. O id da sessão chega no JSON da entrada padrão, e é lá que ele é lido.
"""

import io

from graphow.harness.entrada_hook import (
    MODELO_DESCONHECIDO,
    EntradaDeHook,
    interpretar_entrada_de_hook,
    ler_entrada_de_hook,
    preparar_fluxos_do_hook,
)


def test_entrada_traz_sessao_modelo_e_motivo_nominal() -> None:
    """O payload completo preenche os três campos que o harness aproveita."""
    entrada = interpretar_entrada_de_hook(
        '{"session_id": "sess-abc", "model": "claude-opus-5", "source": "startup"}'
    )

    assert entrada == EntradaDeHook(id_sessao="sess-abc", modelo="claude-opus-5", motivo="startup")
    assert entrada.tem_sessao


def test_modelo_como_objeto_e_reduzido_ao_identificador_nominal() -> None:
    """Alguns payloads descrevem o modelo como objeto, não como texto."""
    entrada = interpretar_entrada_de_hook(
        '{"session_id": "s1", "model": {"id": "claude-opus-5", "display_name": "Opus"}}'
    )

    assert entrada.modelo == "claude-opus-5"


def test_motivo_de_encerramento_e_lido_de_reason_nominal() -> None:
    """No fim da sessão o payload traz `reason`: é o motivo do disparo, não um resumo."""
    entrada = interpretar_entrada_de_hook('{"session_id": "s1", "reason": "logout"}')

    assert entrada.motivo == "logout"


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


def test_diretorio_de_trabalho_do_hook_vem_de_cwd_nominal() -> None:
    """O payload diz de onde o hook rodou; é isso que nomeia o ambiente padrão da memória."""
    entrada = interpretar_entrada_de_hook('{"session_id": "s1", "cwd": " C:/repos/graphow "}')

    assert entrada.diretorio == "C:/repos/graphow"
    assert interpretar_entrada_de_hook('{"session_id": "s1"}').diretorio == ""


def test_preparo_dos_fluxos_poe_entrada_e_saida_em_utf8_nominal() -> None:
    """O Windows abre os canos do hook em cp1252; o ambiente fala UTF-8 dos dois lados."""
    entrada = io.TextIOWrapper(io.BytesIO('{"session_id": "s1", "cwd": "C:/repos/memória"}'.encode("utf-8")), encoding="cp1252")
    saida = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")

    preparar_fluxos_do_hook(entrada, saida)

    assert entrada.encoding == "utf-8"
    assert saida.encoding == "utf-8"
    assert ler_entrada_de_hook(entrada).diretorio == "C:/repos/memória"


def test_preparo_dos_fluxos_tolera_fluxo_sem_reconfiguracao_edge_case() -> None:
    """Caso de borda: um StringIO de teste não se reconfigura, e o hook segue."""
    entrada = io.StringIO('{"session_id": "s1"}')

    preparar_fluxos_do_hook(entrada, io.StringIO())

    assert ler_entrada_de_hook(entrada).id_sessao == "s1"
