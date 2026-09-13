"""Testes unitários para o analisador de argumentos da linha de comando."""

import pytest

from graphow.api.cli_parser import construir_parser


def test_subcomando_web_aceita_host_e_porta_nominal() -> None:
    """O subcomando web expõe host e porta com padrões seguros."""
    parsed = construir_parser().parse_args(["web", "--port", "9000"])
    assert parsed.comando == "web"
    assert parsed.port == 9000
    assert parsed.host == "127.0.0.1"


def test_caminho_do_banco_sem_argumento_fica_indefinido_nominal() -> None:
    """Sem --db nenhum caminho e fixado, deixando a decisao para o localizador."""
    parsed = construir_parser().parse_args(["print"])
    assert getattr(parsed, "db", None) is None


def test_db_antes_do_subcomando_sobrevive_ao_subparser_edge_case() -> None:
    """Caso de borda: --db informado antes do subcomando nao pode ser descartado."""
    antes = construir_parser().parse_args(["--db", "/tmp/a.db", "print"])
    depois = construir_parser().parse_args(["print", "--db", "/tmp/b.db"])
    assert antes.db == "/tmp/a.db"
    assert depois.db == "/tmp/b.db"


def test_subcomando_mcp_exige_papel_edge_case() -> None:
    """Caso de borda: abrir o servidor MCP sem declarar o papel é recusado."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["mcp"])


def test_subcomando_mcp_recusa_papel_fora_da_ontologia_edge_case() -> None:
    """Caso de borda: papéis inexistentes são barrados já no analisador."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["mcp", "--papel", "administrador"])


def test_subcomando_mcp_aceita_papel_valido_nominal() -> None:
    """Um papel válido é aceito e o autor recebe um padrão explícito."""
    parsed = construir_parser().parse_args(["mcp", "--papel", "executor"])
    assert parsed.papel == "executor"
    assert parsed.autor == "agente-mcp"


def test_subcomando_migrar_banco_exige_origem_edge_case() -> None:
    """Caso de borda: migrar sem informar a origem é recusado."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["migrar-banco"])


def test_execucao_sem_subcomando_nao_falha_edge_case() -> None:
    """Caso de borda: nenhum subcomando resolve para comando nulo, não para erro."""
    parsed = construir_parser().parse_args([])
    assert parsed.comando is None


def test_harness_aceita_sessao_declarada_nominal() -> None:
    """Fora de um hook, a sessão é nomeada na própria linha de comando."""
    parsed = construir_parser().parse_args(["harness", "--fase", "inicio", "--sessao", "sess-1"])
    assert parsed.sessao == "sess-1"
    assert parsed.entrada_hook is False


def test_harness_aceita_a_entrada_do_hook_como_origem_nominal() -> None:
    """Dentro de um hook, a sessão vem do JSON da entrada padrão."""
    parsed = construir_parser().parse_args(["harness", "--fase", "fim", "--entrada-hook"])
    assert parsed.entrada_hook is True
    assert parsed.sessao is None


def test_harness_recusa_sessao_em_branco_edge_case() -> None:
    """Caso de borda: `--sessao ""` virava o caminho '/nos/' e estourava no kernel."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["harness", "--fase", "inicio", "--sessao", "  "])


def test_harness_exige_uma_origem_para_a_sessao_edge_case() -> None:
    """Caso de borda: sem `--sessao` nem `--entrada-hook` não há sessão alguma."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(["harness", "--fase", "inicio"])


def test_harness_recusa_duas_origens_ao_mesmo_tempo_edge_case() -> None:
    """Caso de borda: declarar as duas origens deixa a precedência ambígua."""
    with pytest.raises(SystemExit):
        construir_parser().parse_args(
            ["harness", "--fase", "inicio", "--sessao", "s1", "--entrada-hook"]
        )
