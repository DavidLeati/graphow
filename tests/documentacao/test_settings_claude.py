"""Testes da mescla no settings.json: troca o hook do harness, preserva o resto e não duplica."""

import json
from pathlib import Path

import pytest

from graphow.documentacao.ambiente import ConfiguracaoDoAmbiente
from graphow.documentacao.settings_claude import MescladorDeSettings, SettingsInvalido, e_hook_do_harness

CONFIGURACAO: ConfiguracaoDoAmbiente = ConfiguracaoDoAmbiente("C:/venv/Scripts/graphow.exe", "david")

HOOK_DE_OUTRA_FERRAMENTA: dict[str, object] = {"type": "command", "command": "notificar --fim"}
HOOK_ANTIGO_DO_HARNESS: dict[str, object] = {"type": "command", "command": "graphow harness --fase fim --entrada-hook"}


def _ler(caminho: Path) -> dict[str, object]:
    """O settings gravado, como objeto."""
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_settings_inexistente_nasce_com_hooks_e_permissoes_nominal(tmp_path: Path) -> None:
    """Sem arquivo anterior, a mescla o cria e não deixa cópia."""
    caminho = tmp_path / "settings.json"

    resultado = MescladorDeSettings(caminho, CONFIGURACAO).mesclar()

    assert resultado.copia is None
    assert _ler(caminho) == CONFIGURACAO.bloco_do_settings()


def test_mescla_troca_o_harness_antigo_e_preserva_o_resto_nominal(tmp_path: Path) -> None:
    """O hook colado na forma antiga sai, o de outra ferramenta e as chaves alheias ficam, e há cópia."""
    caminho = tmp_path / "settings.json"
    anterior = {
        "model": "opus",
        "permissions": {"allow": ["Bash(ls *)", "mcp__graphow-condutor"]},
        "hooks": {"SessionEnd": [{"hooks": [HOOK_DE_OUTRA_FERRAMENTA]}, {"hooks": [HOOK_ANTIGO_DO_HARNESS]}]},
    }
    caminho.write_text(json.dumps(anterior), encoding="utf-8")

    resultado = MescladorDeSettings(caminho, CONFIGURACAO).mesclar()

    gravado = _ler(caminho)
    assert gravado["model"] == "opus"
    assert gravado["hooks"]["SessionEnd"] == [{"hooks": [HOOK_DE_OUTRA_FERRAMENTA]}, *CONFIGURACAO.hooks()["SessionEnd"]]
    assert gravado["permissions"]["allow"][0] == "Bash(ls *)"
    assert "mcp__graphow-condutor" not in gravado["permissions"]["allow"]
    assert resultado.permissoes_removidas == ("mcp__graphow-condutor",)
    assert resultado.copia is not None and json.loads(resultado.copia.read_text(encoding="utf-8")) == anterior


def test_mescla_tira_o_hook_subagentstop_do_harness_e_deixa_o_alheio_nominal(tmp_path: Path) -> None:
    """O SubagentStop que media os subagentes do condutor sai; o hook de outra ferramenta no evento fica."""
    caminho = tmp_path / "settings.json"
    subagente = {"type": "command", "command": "graphow", "args": ["harness", "--fase", "subagente", "--entrada-hook"]}
    so_do_harness = {"hooks": {"SubagentStop": [{"hooks": [subagente]}]}}
    caminho.write_text(json.dumps(so_do_harness), encoding="utf-8")
    MescladorDeSettings(caminho, CONFIGURACAO).mesclar()
    assert "SubagentStop" not in _ler(caminho)["hooks"]

    com_alheio = {"hooks": {"SubagentStop": [{"hooks": [HOOK_DE_OUTRA_FERRAMENTA]}, {"hooks": [subagente]}]}}
    caminho.write_text(json.dumps(com_alheio), encoding="utf-8")
    MescladorDeSettings(caminho, CONFIGURACAO).mesclar()
    assert _ler(caminho)["hooks"]["SubagentStop"] == [{"hooks": [HOOK_DE_OUTRA_FERRAMENTA]}]


def test_mesclar_de_novo_nao_duplica_nada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: rodar o setup depois de cada atualização deixa o arquivo igual."""
    caminho = tmp_path / "settings.json"
    MescladorDeSettings(caminho, CONFIGURACAO).mesclar()
    primeira = caminho.read_text(encoding="utf-8")

    resultado = MescladorDeSettings(caminho, CONFIGURACAO).mesclar()

    assert caminho.read_text(encoding="utf-8") == primeira
    assert resultado.permissoes_acrescentadas == ()


def test_settings_que_nao_e_json_e_recusado_sem_sobrescrever_edge_case(tmp_path: Path) -> None:
    """Caso de borda: um settings quebrado fica como está, e a recusa diz a linha."""
    caminho = tmp_path / "settings.json"
    caminho.write_text("{ quebrado", encoding="utf-8")

    with pytest.raises(SettingsInvalido) as erro:
        MescladorDeSettings(caminho, CONFIGURACAO).mesclar()

    assert "linha 1" in erro.value.mensagem
    assert caminho.read_text(encoding="utf-8") == "{ quebrado"


def test_reconhece_o_hook_do_harness_nas_duas_formas_nominal() -> None:
    """Comando inteiro numa string ou executável com args: os dois são o harness."""
    assert e_hook_do_harness(HOOK_ANTIGO_DO_HARNESS)
    assert e_hook_do_harness(CONFIGURACAO.hook("inicio"))
    assert not e_hook_do_harness(HOOK_DE_OUTRA_FERRAMENTA)
    assert not e_hook_do_harness({"command": "graphow web"})
