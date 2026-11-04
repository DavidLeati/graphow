"""As refs do repositório do humano: o fast-forward que não sobrescreve a base que andou e nenhuma ref movida por baixo de um worktree."""

from pathlib import Path

import pytest

from graphow.orquestrador import refs_do_humano
from graphow.orquestrador.git_do_goal import AreaDoGoal, FalhaDoGitDoGoal, commitar, preparar_area, sincronizar_ramo
from graphow.orquestrador.rebase_no_clone import RebaseNoClone, mover_as_refs, rebasear, trazer_a_base
from graphow.orquestrador.refs_do_humano import integrar_por_fast_forward, worktree_do_ramo

from tests.orquestrador.apoio_git import criar_repositorio, git

RAMO: str = "graphow/teste"


def _goal_com_uma_fatia(tmp_path: Path) -> AreaDoGoal:
    """O clone do Goal com a fatia F1 (a.py) levada ao repositório do humano, que fica com o HEAD destacado (a main fora do checkout)."""
    repositorio = criar_repositorio(tmp_path / "repo")
    area = AreaDoGoal(repositorio, tmp_path / "area", RAMO, "main")
    preparar_area(area)
    (area.pasta / "a.py").write_text("a = 1\n", encoding="utf-8", newline="\n")
    commitar(area.pasta, "Fatia F1")
    sincronizar_ramo(area)
    git(repositorio, "checkout", "-q", "--detach")
    return area


def _humano_commita_na_main(repositorio: Path, arquivo: str) -> str:
    """O commit do humano na main, que não está no checkout (commit-tree e update-ref); devolve o hash."""
    (repositorio / arquivo).write_text("do humano\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", arquivo)
    arvore = git(repositorio, "write-tree").strip()
    git(repositorio, "reset", "-q")
    (repositorio / arquivo).unlink()
    novo = git(repositorio, "commit-tree", arvore, "-p", "main", "-m", f"Humano muda {arquivo}").strip()
    git(repositorio, "update-ref", "refs/heads/main", novo)
    return novo


def test_fast_forward_fora_do_checkout_anda_a_base_pelo_update_ref_nominal(tmp_path: Path) -> None:
    """Com a main fora do checkout do humano, a base vai à ponta da branch do Goal."""
    area = _goal_com_uma_fatia(tmp_path)
    ponta = git(area.repositorio, "rev-parse", RAMO).strip()

    assert integrar_por_fast_forward(area.repositorio, RAMO, "main", verificado=ponta) == ponta
    assert git(area.repositorio, "rev-parse", "main").strip() == ponta


def test_branch_do_goal_que_andou_depois_da_verificacao_nao_vai_a_base_edge_case(tmp_path: Path) -> None:
    """T3g5.1: a branch do Goal tem um commit novo, que a verificação não viu; a integração recusa, e a base fica."""
    area = _goal_com_uma_fatia(tmp_path)
    verificado, base = (git(area.repositorio, "rev-parse", nome).strip() for nome in (RAMO, "main"))
    git(area.repositorio, "checkout", "-q", RAMO)
    (area.repositorio / "NAO_VERIFICADO.txt").write_text("ninguem verificou\n", encoding="utf-8", newline="\n")
    git(area.repositorio, "add", "-A")
    git(area.repositorio, "commit", "-q", "-m", "Humano na branch do Goal")
    git(area.repositorio, "checkout", "-q", "--detach")

    with pytest.raises(FalhaDoGitDoGoal, match="andou depois da verificacao"):
        integrar_por_fast_forward(area.repositorio, RAMO, "main", verificado=verificado)
    assert git(area.repositorio, "rev-parse", "main").strip() == base


def test_base_que_anda_entre_a_conferencia_e_o_fast_forward_nao_e_sobrescrita_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3g3.1: o humano commita na main depois da conferência do fast-forward; o `update-ref` com o valor antigo recusa."""
    area = _goal_com_uma_fatia(tmp_path)
    original = refs_do_humano.worktree_do_ramo
    andou: list[str] = []

    def andar_e_procurar(repositorio: Path, ramo: str) -> str:
        andou.append(_humano_commita_na_main(area.repositorio, "NOTAS.txt"))
        return original(repositorio, ramo)

    monkeypatch.setattr(refs_do_humano, "worktree_do_ramo", andar_e_procurar)

    with pytest.raises(FalhaDoGitDoGoal):
        integrar_por_fast_forward(area.repositorio, RAMO, "main", verificado=git(area.repositorio, "rev-parse", RAMO).strip())
    assert git(area.repositorio, "rev-parse", "main").strip() == andou[0], "o commit do humano fica na base"


def test_base_aberta_em_worktree_ligado_nao_anda_por_baixo_dele_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a main aberta num worktree ligado do humano; o fast-forward não a move, como o `branch -f` recusava."""
    area = _goal_com_uma_fatia(tmp_path)
    base = git(area.repositorio, "rev-parse", "main").strip()
    git(area.repositorio, "worktree", "add", "-q", str(tmp_path / "ligado"), "main")

    with pytest.raises(FalhaDoGitDoGoal, match="aberta em outro worktree"):
        integrar_por_fast_forward(area.repositorio, RAMO, "main", verificado=git(area.repositorio, "rev-parse", RAMO).strip())
    assert git(area.repositorio, "rev-parse", "main").strip() == base


def test_branch_do_goal_aberta_em_worktree_ligado_do_humano_nao_anda_no_rebase_edge_case(tmp_path: Path) -> None:
    """T3g3.2: a branch do Goal aberta num worktree ligado do humano; `mover_as_refs` não a move e diz onde ela está."""
    area = _goal_com_uma_fatia(tmp_path)
    git(area.repositorio, "checkout", "-q", "main")
    (area.repositorio / "NOTAS.txt").write_text("nota\n", encoding="utf-8", newline="\n")
    git(area.repositorio, "add", "-A")
    git(area.repositorio, "commit", "-q", "-m", "Humano")
    ligado = tmp_path / "ligado"
    git(area.repositorio, "worktree", "add", "-q", str(ligado), RAMO)
    trazer_a_base(area)
    feito = rebasear(area.pasta, RAMO, "main")
    assert isinstance(feito, RebaseNoClone)
    assert Path(worktree_do_ramo(area.repositorio, RAMO)).resolve() == ligado.resolve()

    with pytest.raises(FalhaDoGitDoGoal, match="aberta no checkout do humano") as erro:
        mover_as_refs(area, feito.antes, feito.depois)
    assert "ligado" in erro.value.formatar_para_llm()
    assert git(area.repositorio, "rev-parse", RAMO).strip() == feito.antes
    assert git(ligado, "status", "--porcelain") == ""
