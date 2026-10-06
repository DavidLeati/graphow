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
    assert gravado["permissions"]["allow"][:2] == ["Bash(ls *)", "mcp__graphow-condutor"]
    assert "mcp__graphow-condutor" not in resultado.permissoes_acrescentadas
    assert resultado.copia is not None and json.loads(resultado.copia.read_text(encoding="utf-8")) == anterior


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
