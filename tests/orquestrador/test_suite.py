"""A suíte do plano roda no shell dos agentes, o mesmo em que o executor a rodou na sessão."""

import os
from pathlib import Path

import pytest

from graphow.orquestrador import suite
from graphow.orquestrador.briefing import briefing_do_planejador
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.suite import VARIAVEL_DO_GIT_BASH, VARIAVEL_DO_SHELL, rodar_suite, shell_dos_agentes

pytestmark = pytest.mark.skipif(shell_dos_agentes() is None, reason="a maquina nao tem bash")


def test_comando_posix_passa_na_suite_do_orquestrador_nominal(tmp_path: Path) -> None:
    """`test -f` e `&&` são do bash: no cmd do Windows este comando falharia."""
    (tmp_path / "verificar.py").write_text("print(1)\n", encoding="utf-8")

    resultado = rodar_suite(tmp_path, "test -f verificar.py && echo ok-posix", tmp_path / "descartavel.db")

    assert resultado.passou, resultado.descrever()
    assert "ok-posix" in resultado.saida
    assert resultado.shell.startswith("bash (")


def test_graphow_shell_escolhe_outro_shell_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda: o shell que não existe não abre, e o resultado diz qual era."""
    monkeypatch.setenv(VARIAVEL_DO_SHELL, str(tmp_path / "nao-existe" / "bash"))

    resultado = rodar_suite(tmp_path, "true", tmp_path / "descartavel.db")

    assert not resultado.passou
    assert "a suite nao abriu" in resultado.saida and "nao-existe" in resultado.shell


@pytest.mark.skipif(os.name != "nt", reason="o bash do WSL so existe no Windows")
def test_bash_do_wsl_nunca_e_o_shell_da_suite_edge_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda: apontar o Git Bash para o System32 não troca o shell pelo do WSL."""
    monkeypatch.delenv(VARIAVEL_DO_SHELL, raising=False)
    monkeypatch.setenv(VARIAVEL_DO_GIT_BASH, r"C:\Windows\System32\bash.exe")

    shell = suite.shell_dos_agentes()

    assert shell is not None and "system32" not in str(shell).lower()


def test_briefing_do_planejador_diz_o_shell_da_suite_nominal() -> None:
    """O planejador sabe em que shell o `comando_suite` vai rodar."""
    estado = EstadoDoGoal(id_goal="goal-soma", rotulo="soma", status="pendente", propriedades={})

    briefing = briefing_do_planejador(estado, "Quero somar.", False)

    assert "comando_suite" in briefing and "bash (" in briefing
