"""O rebase da branch do Goal no clone: um commit novo por antigo, o conflito que volta tudo, a queda no meio e as refs que andam juntas."""

from pathlib import Path

import pytest

from graphow.orquestrador.git_do_goal import (
    AreaDoGoal,
    FalhaDoGitDoGoal,
    GitDoGoal,
    commitar,
    mensagem_do_orquestrador,
    preparar_area,
    sincronizar_ramo,
)
from graphow.orquestrador.rebase_no_clone import (
    ConflitoNoRebase,
    RebaseNoClone,
    mover_as_refs,
    rebasear,
    recuperar_o_clone,
    trazer_a_base,
)

from tests.orquestrador.apoio_git import criar_repositorio, git

RAMO: str = "graphow/teste"


def _goal_com_duas_fatias(tmp_path: Path) -> AreaDoGoal:
    """O clone do Goal com a fatia F1 (soma.py) e uma fatia vazia, levadas ao repositório do humano."""
    repositorio = criar_repositorio(tmp_path / "repo", {"soma.py": "def somar(a, b):\n    return 0\n"})
    area = AreaDoGoal(repositorio, tmp_path / "area", RAMO, "main")
    preparar_area(area)
    (area.pasta / "soma.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8", newline="\n")
    commitar(area.pasta, mensagem_do_orquestrador("Fatia F1: soma", "feito", id_goal="goal-teste", id_task="task-f1"))
    commitar(area.pasta, mensagem_do_orquestrador("Fatia F2: nada", "", id_goal="goal-teste", id_task="task-f2"), vazio_permitido=True)
    sincronizar_ramo(area)
    return area


def _humano_commita(area: AreaDoGoal, arquivo: str, conteudo: str) -> str:
    """O commit do humano na main dele; devolve o hash."""
    (area.repositorio / arquivo).write_text(conteudo, encoding="utf-8", newline="\n")
    git(area.repositorio, "add", "-A")
    git(area.repositorio, "commit", "-q", "-m", f"Humano muda {arquivo}")
    return git(area.repositorio, "rev-parse", "HEAD").strip()


def test_rebase_limpo_refaz_cada_commit_com_a_mensagem_e_so_as_refs_andam_depois_nominal(tmp_path: Path) -> None:
    """Cada commit (o vazio inclusive) ganha um novo com os trailers; a branch só anda em `mover_as_refs`, no clone e no humano."""
    area = _goal_com_duas_fatias(tmp_path)
    antes = GitDoGoal(area.pasta).head()
    base = _humano_commita(area, "NOTAS.txt", "nota\n")

    assert trazer_a_base(area) == base
    feito = rebasear(area.pasta, RAMO, "main")

    assert isinstance(feito, RebaseNoClone) and feito.antes == antes and feito.base_depois == base
    assert len(feito.pares) == 2 and feito.arquivos == ("NOTAS.txt",)
    assert git(area.pasta, "rev-parse", RAMO).strip() == antes, "a branch nao anda antes do registro"
    novo_da_f2 = feito.pares[-1][1]
    assert "Graphow-Task: task-f2" in git(area.pasta, "log", "-1", "--format=%B", novo_da_f2)
    mover_as_refs(area, feito.antes, feito.depois)
    assert git(area.pasta, "branch", "--show-current").strip() == RAMO
    assert git(area.pasta, "rev-parse", RAMO).strip() == git(area.repositorio, "rev-parse", RAMO).strip() == feito.depois
    mover_as_refs(area, feito.antes, feito.depois)
    assert git(area.repositorio, "rev-parse", RAMO).strip() == feito.depois, "repetir nao muda nada"


def test_rebase_com_conflito_volta_o_clone_a_branch_como_estava_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o conflito em soma.py aborta o rebase; o clone fica na branch, no commit de antes, sem rebase pela metade."""
    area = _goal_com_duas_fatias(tmp_path)
    antes = GitDoGoal(area.pasta).head()
    _humano_commita(area, "soma.py", "def somar(a, b):\n    return a - b\n")
    trazer_a_base(area)

    feito = rebasear(area.pasta, RAMO, "main")

    assert isinstance(feito, ConflitoNoRebase) and feito.arquivos == ("soma.py",) and feito.antes == antes
    assert git(area.pasta, "branch", "--show-current").strip() == RAMO and GitDoGoal(area.pasta).head() == antes
    assert git(area.pasta, "status", "--porcelain") == "" and not (area.pasta / ".git" / "rebase-merge").exists()


def test_rebase_que_o_processo_deixou_pela_metade_sai_na_chamada_seguinte_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o processo caiu no meio do rebase (HEAD destacado, conflito aberto); `recuperar_o_clone` volta à branch."""
    area = _goal_com_duas_fatias(tmp_path)
    antes = GitDoGoal(area.pasta).head()
    _humano_commita(area, "soma.py", "def somar(a, b):\n    return a - b\n")
    trazer_a_base(area)
    git(area.pasta, "checkout", "-q", "--detach")
    assert GitDoGoal(area.pasta).tentar("rebase", "-q", "main").codigo != 0

    feito = recuperar_o_clone(area.pasta, RAMO)

    assert "abortado" in feito
    assert git(area.pasta, "branch", "--show-current").strip() == RAMO and GitDoGoal(area.pasta).head() == antes
    assert recuperar_o_clone(area.pasta, RAMO) == "", "sem rebase pela metade, nada a fazer"


def test_refs_nao_andam_por_baixo_do_checkout_do_humano_edge_case(tmp_path: Path) -> None:
    """Caso de borda: com a branch do Goal aberta no checkout do humano, o rebase não a move e diz por quê."""
    area = _goal_com_duas_fatias(tmp_path)
    _humano_commita(area, "NOTAS.txt", "nota\n")
    trazer_a_base(area)
    feito = rebasear(area.pasta, RAMO, "main")
    assert isinstance(feito, RebaseNoClone)
    git(area.repositorio, "checkout", "-q", RAMO)

    with pytest.raises(FalhaDoGitDoGoal, match="aberta no checkout do humano"):
        mover_as_refs(area, feito.antes, feito.depois)
    assert git(area.repositorio, "rev-parse", RAMO).strip() == feito.antes
