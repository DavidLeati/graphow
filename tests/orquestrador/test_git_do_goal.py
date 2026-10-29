"""O git do Goal: o clone numa branch própria, o commit do orquestrador levado ao humano, a trava e o fast-forward."""

import os
from pathlib import Path
import subprocess

import pytest

from graphow.orquestrador.commit_do_pedido import commitar_so
from graphow.orquestrador.git_do_goal import (
    descartar_mudancas,
    AreaDoGoal,
    FalhaDoGitDoGoal,
    GitDoGoal,
    commitar,
    descartar_mudancas,
    integrar_por_fast_forward,
    preparar_area,
    remover_area,
    restaurar_head,
    sincronizar_ramo,
)
from graphow.orquestrador.trava_do_git import instalar_trava, regras_que_negam_git

from tests.orquestrador.apoio_git import criar_repositorio, git, git_bytes


def _area(tmp_path: Path) -> tuple[Path, Path]:
    """O repositório do humano e o clone do Goal na branch graphow/teste."""
    repositorio = criar_repositorio(tmp_path / "repo")
    area = tmp_path / "areas" / "teste"
    preparar_area(_do_goal(repositorio, area))
    return repositorio, area


def _do_goal(repositorio: Path, area: Path) -> AreaDoGoal:
    """A área de teste: a branch graphow/teste, da main."""
    return AreaDoGoal(repositorio, area, "graphow/teste", "main")


def test_area_nasce_na_branch_do_goal_sem_tocar_o_checkout_do_humano_nominal(tmp_path: Path) -> None:
    """A área é um clone na branch nova, e a branch existe no humano; o repositório dele segue na main, limpo."""
    repositorio, area = _area(tmp_path)

    assert GitDoGoal(area).ramo_atual() == "graphow/teste"
    assert GitDoGoal(repositorio).ramo_atual() == "main"
    assert GitDoGoal(repositorio).mudancas() == ()
    preparar_area(_do_goal(repositorio, area))
    assert GitDoGoal(area).head() == GitDoGoal(repositorio).head()
    assert git(repositorio, "rev-parse", "graphow/teste").strip() == GitDoGoal(area).head()
    assert git(repositorio, "worktree", "list").count("\n") == 1


def test_commit_do_orquestrador_leva_tudo_o_que_mudou_nominal(tmp_path: Path) -> None:
    """O commit da fatia leva arquivo novo e alterado, e a branch avança só na área."""
    repositorio, area = _area(tmp_path)
    (area / "soma.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8")

    commit = commitar(area, "Fatia F1: soma (C1)")
    sincronizar_ramo(_do_goal(repositorio, area))

    assert GitDoGoal(area).mudancas() == ()
    assert git(repositorio, "rev-parse", "graphow/teste").strip() == commit
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
    sincronizar_ramo(_do_goal(repositorio, area))

    integrado = integrar_por_fast_forward(repositorio, "graphow/teste", "main")

    assert integrado == commit
    assert (repositorio / "soma.py").is_file()
    assert GitDoGoal(repositorio).mudancas() == ()


def test_integracao_recusa_quando_a_base_andou_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem fast-forward, nada é integrado; rebase é da fase 3."""
    repositorio, area = _area(tmp_path)
    (area / "a.py").write_text("a\n", encoding="utf-8")
    commitar(area, "Fatia F1")
    sincronizar_ramo(_do_goal(repositorio, area))
    (repositorio / "b.py").write_text("b\n", encoding="utf-8")
    commitar(repositorio, "Trabalho do humano")

    with pytest.raises(FalhaDoGitDoGoal):
        integrar_por_fast_forward(repositorio, "graphow/teste", "main")
    assert not (repositorio / "a.py").exists()


def test_branch_que_andou_no_humano_nao_e_sobrescrita_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o humano commitou na branch do Goal; o orquestrador não a força, e diz por quê."""
    repositorio, area = _area(tmp_path)
    git(repositorio, "checkout", "-q", "graphow/teste")
    (repositorio / "h.txt").write_text("h\n", encoding="utf-8")
    commitar(repositorio, "Do humano na branch do Goal")
    git(repositorio, "checkout", "-q", "main")
    (area / "a.py").write_text("a\n", encoding="utf-8")
    commitar(area, "Fatia F1")

    with pytest.raises(FalhaDoGitDoGoal, match="andou no repositorio fora do orquestrador"):
        sincronizar_ramo(_do_goal(repositorio, area))
    assert git(repositorio, "log", "-1", "--format=%s", "graphow/teste").strip() == "Do humano na branch do Goal"


def test_area_antiga_em_worktree_vira_clone_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o Goal de uma versão anterior tinha a área num worktree; ela sai e o clone parte da branch."""
    repositorio = criar_repositorio(tmp_path / "repo")
    area = tmp_path / "areas" / "teste"
    git(repositorio, "worktree", "add", "-q", "-b", "graphow/teste", str(area), "main")
    (area / "a.py").write_text("a\n", encoding="utf-8")
    commit = commitar(area, "Fatia F1 na area antiga")

    preparar_area(_do_goal(repositorio, area))

    assert (area / ".git").is_dir() and GitDoGoal(area).head() == commit
    assert git(repositorio, "worktree", "list").count("\n") == 1


def test_remover_area_apaga_o_clone_e_a_branch_fica_nominal(tmp_path: Path) -> None:
    """O clone sai inteiro, objetos somente leitura inclusive; a branch do Goal segue no repositório do humano."""
    repositorio, area = _area(tmp_path)
    (area / "a.py").write_text("a\n", encoding="utf-8")
    commit = commitar(area, "Fatia F1")
    sincronizar_ramo(_do_goal(repositorio, area))

    assert remover_area(area) is True

    assert not area.exists()
    assert git(repositorio, "rev-parse", "graphow/teste").strip() == commit


# Um CSV em ANSI (cp1252) e um texto com CRLF: o .patch lido como texto os corrompia.
CSV_EM_ANSI: bytes = "codigo;descricao\r\n1;ação de graça\r\n".encode("cp1252")
TEXTO_COM_CRLF: bytes = b"linha 1\r\nlinha 2\r\n"


def test_patch_guarda_e_devolve_o_arquivo_byte_a_byte_edge_case(tmp_path: Path) -> None:
    """Caso de borda (rodada 4, item 3): o .patch da área guarda o ANSI e o CRLF em bytes, e o `git apply --binary` os devolve iguais."""
    area = criar_repositorio(tmp_path / "area")
    (area / "dados.csv").write_bytes(CSV_EM_ANSI)
    (area / "notas.txt").write_bytes(TEXTO_COM_CRLF)
    patch = tmp_path / "patches" / "entrega.patch"

    assert descartar_mudancas(area, patch)
    assert not (area / "dados.csv").exists()
    git_bytes(area, "apply", "--binary", str(patch))

    assert "\ufffd".encode("utf-8") not in patch.read_bytes()
    assert (area / "dados.csv").read_bytes() == CSV_EM_ANSI
    assert (area / "notas.txt").read_bytes() == TEXTO_COM_CRLF


def test_commit_do_pedido_leva_so_os_caminhos_dele_e_a_sobra_fica_na_area_edge_case(tmp_path: Path) -> None:
    """T2l: o commit do pedido leva só o caminho dado (o removido com git rm inclusive); o resto fica fora de commit."""
    repositorio = criar_repositorio(tmp_path / "repo", {"docs/goal.md": "# Goal\n", "aceite/aceite_c1.py": "x = 1\n"})
    (repositorio / "docs" / "goal.md").write_text("# Goal\n\n## Retirados\n", encoding="utf-8", newline="\n")
    (repositorio / "conftest.py").write_text("def pytest_pyfunc_call(pyfuncitem):\n    return True\n", encoding="utf-8")
    git(repositorio, "add", "conftest.py")

    commitar_so(repositorio, "Registra", ("docs/goal.md",))
    assert git(repositorio, "show", "--name-only", "--format=", "HEAD").split() == ["docs/goal.md"]
    git(repositorio, "rm", "-r", "-q", "--", "aceite")
    commitar_so(repositorio, "Retira", ("aceite",))
    assert git(repositorio, "show", "--name-only", "--format=", "HEAD").split() == ["aceite/aceite_c1.py"]
    commitar_so(repositorio, "Mantem", ("aceite",), vazio_permitido=True)

    assert git(repositorio, "show", "--name-only", "--format=", "HEAD").split() == []
    assert git(repositorio, "log", "-1", "--format=%s").strip() == "Mantem"
    assert git(repositorio, "status", "--porcelain").splitlines() == ["A  conftest.py"]
