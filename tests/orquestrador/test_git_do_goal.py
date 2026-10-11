"""O git do Goal: área numa branch própria, commit do orquestrador, trava do agente e integração por fast-forward."""

import os
from pathlib import Path
import subprocess

import pytest

from graphow.orquestrador.git_do_goal import (
    AreaDoGoal,
    FalhaDoGitDoGoal,
    GitDoGoal,
    commitar,
    descartar_mudancas,
    instalar_trava,
    integrar_por_fast_forward,
    preparar_area,
    regras_que_negam_git,
    restaurar_head,
)

from tests.orquestrador.apoio_git import criar_repositorio, git


def _area(tmp_path: Path) -> tuple[Path, Path]:
    """O repositório do humano e a área do Goal na branch graphow/teste."""
    repositorio = criar_repositorio(tmp_path / "repo")
    area = tmp_path / "areas" / "teste"
    preparar_area(AreaDoGoal(repositorio, area, "graphow/teste", "main"))
    return repositorio, area


def test_area_nasce_na_branch_do_goal_sem_tocar_o_checkout_do_humano_nominal(tmp_path: Path) -> None:
    """A área é um worktree na branch nova; o repositório do humano segue na main, limpo."""
    repositorio, area = _area(tmp_path)

    assert GitDoGoal(area).ramo_atual() == "graphow/teste"
    assert GitDoGoal(repositorio).ramo_atual() == "main"
    assert GitDoGoal(repositorio).mudancas() == ()
    preparar_area(AreaDoGoal(repositorio, area, "graphow/teste", "main"))
    assert GitDoGoal(area).head() == GitDoGoal(repositorio).head()


def test_commit_do_orquestrador_leva_tudo_o_que_mudou_nominal(tmp_path: Path) -> None:
    """O commit da fatia leva arquivo novo e alterado, e a branch avança só na área."""
    repositorio, area = _area(tmp_path)
    (area / "soma.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8")

    commit = commitar(area, "Fatia F1: soma (C1)")

    assert GitDoGoal(area).mudancas() == ()
    assert git(area, "log", "-1", "--format=%s").strip() == "Fatia F1: soma (C1)"
    assert GitDoGoal(repositorio).ramo_atual() == "main"
    assert not (repositorio / "soma.py").exists()
    assert GitDoGoal(repositorio).e_ancestral("main", commit)


def test_trava_impede_o_agente_de_commitar_ate_com_no_verify_nominal(tmp_path: Path) -> None:
    """O ambiente da sessão do agente aborta a atualização de ref; o git do orquestrador segue livre."""
    _, area = _area(tmp_path)
    ambiente = {**os.environ, **instalar_trava(tmp_path / "trava")}
    (area / "x.txt").write_text("x\n", encoding="utf-8")
    git(area, "add", "x.txt")

    tentativa = subprocess.run(
        ["git", "-C", str(area), "commit", "--no-verify", "-q", "-m", "do agente"],
        capture_output=True, text=True, env=ambiente, check=False,
    )

    assert tentativa.returncode != 0
    assert "quem commita e o orquestrador" in tentativa.stderr
    assert git(area, "log", "-1", "--format=%s").strip() == "Estado inicial"
    commitar(area, "Fatia F1")
    assert git(area, "log", "-1", "--format=%s").strip() == "Fatia F1"


def test_regras_de_ferramenta_negam_git_de_escrita_edge_case() -> None:
    """Caso de borda: a primeira camada nomeia commit e o resto do git de escrita."""
    regras = regras_que_negam_git(("Bash",))

    assert "Bash(git commit:*)" in regras
    assert "Bash(git reset:*)" in regras
    assert not [regra for regra in regras if "status" in regra or "diff" in regra]


def test_commit_que_escapou_volta_para_a_arvore_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o agente commitou mesmo assim; o orquestrador desfaz e as mudanças ficam para ele commitar."""
    _, area = _area(tmp_path)
    esperado = GitDoGoal(area).head()
    (area / "x.txt").write_text("x\n", encoding="utf-8")
    git(area, "add", "x.txt")
    git(area, "commit", "-q", "-m", "do agente")

    desfeito = restaurar_head(area, "graphow/teste", esperado)

    assert "reset --soft" in desfeito
    assert GitDoGoal(area).head() == esperado
    assert GitDoGoal(area).mudancas() == ("A  x.txt",)
    assert restaurar_head(area, "graphow/teste", esperado) == ""


def test_descartar_guarda_o_patch_e_volta_ao_commit_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a tentativa pausada não vaza para a fatia seguinte, e o que ela fez fica num .patch."""
    _, area = _area(tmp_path)
    (area / "novo.py").write_text("print(1)\n", encoding="utf-8")
    (area / "README.md").write_text("mudou\n", encoding="utf-8")
    patch = tmp_path / "patches" / "f1.patch"

    assert descartar_mudancas(area, patch) is True

    assert GitDoGoal(area).mudancas() == ()
    assert "novo.py" in patch.read_text(encoding="utf-8")
    assert descartar_mudancas(area, tmp_path / "outro.patch") is False


def test_integracao_avanca_a_base_no_checkout_do_humano_nominal(tmp_path: Path) -> None:
    """Fast-forward da main até a branch do Goal, no checkout em que a main está."""
    repositorio, area = _area(tmp_path)
    (area / "soma.py").write_text("x = 1\n", encoding="utf-8")
    commit = commitar(area, "Fatia F1")

    integrado = integrar_por_fast_forward(repositorio, "graphow/teste", "main")

    assert integrado == commit
    assert (repositorio / "soma.py").is_file()
    assert GitDoGoal(repositorio).mudancas() == ()


def test_integracao_recusa_quando_a_base_andou_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem fast-forward, nada é integrado; rebase é da fase 3."""
    repositorio, area = _area(tmp_path)
    (area / "a.py").write_text("a\n", encoding="utf-8")
    commitar(area, "Fatia F1")
    (repositorio / "b.py").write_text("b\n", encoding="utf-8")
    commitar(repositorio, "Trabalho do humano")

    with pytest.raises(FalhaDoGitDoGoal):
        integrar_por_fast_forward(repositorio, "graphow/teste", "main")
    assert not (repositorio / "a.py").exists()
