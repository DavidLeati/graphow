"""Testes da configuração do ambiente: o executável com caminho e a fiação publicada em sincronia."""

import json
from pathlib import Path

from graphow.documentacao.ambiente import ConfiguracaoDoAmbiente, fixar_executavel_no_agente

RAIZ_DO_REPOSITORIO: Path = Path(__file__).resolve().parents[2]
FIACAO_PUBLICADA: Path = RAIZ_DO_REPOSITORIO / ".agents" / "hooks" / "graphow_harness_hooks.json"
EXECUTAVEL: str = "C:/venv/Scripts/graphow.exe"

AGENTE: str = (
    "---\r\n"
    "mcpServers:\r\n"
    "  - graphow-executor:\r\n"
    "      type: stdio\r\n"
    "      command: graphow\r\n"
    '      args: ["mcp", "--papel", "executor"]\r\n'
    "---\r\n"
    "O comando: graphow fica no texto.\r\n"
)


def test_subagente_chama_o_executavel_com_caminho_preservando_o_resto_nominal() -> None:
    """Só a linha `command:` muda; o fim de linha CRLF e o texto do corpo ficam como estavam."""
    fixado = fixar_executavel_no_agente(AGENTE, EXECUTAVEL)

    assert f'      command: "{EXECUTAVEL}"\r\n' in fixado
    assert fixado.replace(f'"{EXECUTAVEL}"', "graphow") == AGENTE


def test_executavel_sem_caminho_deixa_o_subagente_intacto_edge_case() -> None:
    """Caso de borda: sem caminho resolvido, a definição sai byte a byte igual à do repositório."""
    assert fixar_executavel_no_agente(AGENTE, "graphow") == AGENTE


def test_hooks_chamam_o_harness_com_argumentos_em_lista_nominal() -> None:
    """Cada evento dispara a sua fase, sem shell no meio para citar caminho com espaço."""
    hooks = ConfiguracaoDoAmbiente("C:/Program Files/graphow.exe", "david").hooks()

    assert set(hooks) == {"SessionStart", "SessionEnd", "SubagentStop"}
    inicio = hooks["SessionStart"][0]["hooks"][0]
    assert inicio["command"] == "C:/Program Files/graphow.exe"
    assert inicio["args"] == ["harness", "--fase", "inicio", "--entrada-hook"]


def test_permissoes_liberam_so_leitura_na_sessao_principal_nominal() -> None:
    """A sessão de papel humano lê sem perguntar; responder e promover seguem pedindo confirmação."""
    permissoes = ConfiguracaoDoAmbiente(EXECUTAVEL, "david").permissoes()

    assert "mcp__graphow__ler_vista" in permissoes
    assert "mcp__graphow-condutor" in permissoes
    assert not any("responder_questao" in regra or "promover" in regra for regra in permissoes)


def test_servidor_da_sessao_principal_tem_papel_humano_e_o_autor_nominal() -> None:
    """O comando impresso registra o servidor no escopo do usuário, com o executável citado."""
    comando = ConfiguracaoDoAmbiente(EXECUTAVEL, "david").comando_do_servidor_da_sessao()

    assert comando.startswith("claude mcp add --scope user graphow -- ")
    assert f'"{EXECUTAVEL}" mcp --papel humano --autor david' in comando


def test_fiacao_publicada_e_a_que_o_setup_gera_nominal() -> None:
    """O arquivo de hooks do repositório não pode divergir do que o setup grava no settings.json."""
    publicada = json.loads(FIACAO_PUBLICADA.read_text(encoding="utf-8"))

    assert publicada["hooks"] == ConfiguracaoDoAmbiente("graphow", "qualquer").hooks()
