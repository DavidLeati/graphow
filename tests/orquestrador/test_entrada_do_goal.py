"""A entrada do laço recusa cedo a branch alheia e a área no checkout do humano, sem criar Goal nem abrir sessão."""

from pathlib import Path

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import Bancada, montar_bancada
from tests.orquestrador.test_retomada import roteiro_farto


def _com_branch_alheia(tmp_path: Path) -> Bancada:
    """A bancada com a branch graphow/soma já criada pelo humano, com um commit dele."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    git(bancada.repositorio, "checkout", "-q", "-b", "graphow/soma")
    (bancada.repositorio / "rascunho.txt").write_text("do humano\n", encoding="utf-8")
    git(bancada.repositorio, "add", "rascunho.txt")
    git(bancada.repositorio, "commit", "-q", "-m", "Rascunho do humano")
    git(bancada.repositorio, "checkout", "-q", "main")
    return bancada


def test_branch_que_ja_existe_com_commit_alheio_e_recusada_nominal(tmp_path: Path) -> None:
    """A branch do Goal já tem commit do humano: nada é criado, e a parada diz como seguir."""
    bancada = _com_branch_alheia(tmp_path)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo"))

    assert parada.motivo == MotivoDaParada.FALHA
    assert "graphow/soma ja existe com 1 commit(s)" in parada.mensagem and "--adotar-ramo" in parada.mensagem
    assert bancada.chamadas() == []
    assert ler_estado(bancada.kernel.obter_view(), "goal-soma") is None


def test_adotar_ramo_aceita_a_branch_alheia_edge_case(tmp_path: Path) -> None:
    """Caso de borda: com `--adotar-ramo` o humano assume o commit dele, e o Goal parte da branch e fecha."""
    bancada = _com_branch_alheia(tmp_path)

    parada = bancada.orquestrador().iniciar_da_spec(
        bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", adotar_ramo=True)
    )

    assert parada.fechou, parada.mensagem
    assert "Rascunho do humano" in git(bancada.repositorio, "log", "--format=%s", "main")


@pytest.mark.parametrize("dentro", ["", "sub/area"])
def test_area_no_checkout_do_humano_e_recusada_edge_case(tmp_path: Path, dentro: str) -> None:
    """Caso de borda: `--area` igual ao repositório, ou dentro dele, não chega ao git."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    area = bancada.repositorio / dentro if dentro else bancada.repositorio

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(area=area))

    assert parada.motivo == MotivoDaParada.FALHA
    assert "nao pode ser o checkout do humano" in parada.mensagem
    assert bancada.chamadas() == [] and git(bancada.repositorio, "worktree", "list").count("\n") == 1
