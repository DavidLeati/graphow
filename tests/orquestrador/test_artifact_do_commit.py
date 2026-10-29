"""O Artifact de cada entrega do orquestrador leva os arquivos lidos do commit, e não os que alguém declarou."""

from pathlib import Path

import pytest

from graphow.core.types import TipoNo
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.livro_razao import fora_do_commit

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import SOMA_CERTA, VERIFICAR, executor_pronto, montar_bancada, roteiro_completo

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _arquivos_do_commit(repositorio: Path, commit: str) -> list[str]:
    """Os arquivos que o commit mudou, como o git os lista."""
    return [linha for linha in git(repositorio, "show", "--name-only", "--format=", commit).splitlines() if linha.strip()]


def test_artifact_da_fatia_traz_os_arquivos_do_commit_e_nao_os_declarados_nominal(tmp_path: Path) -> None:
    """O executor declara um arquivo que não escreveu e esquece um que escreveu: o Artifact segue o commit."""
    roteiro = roteiro_completo()
    entrega = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR})
    entrega["saida"]["arquivos"] = ["soma.py", "inventado.py"]
    roteiro["executor"][0] = entrega
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    artefato = bancada.kernel.obter_view().obter_no("art-task-soma-f1-t1")
    assert artefato is not None
    commit = str(artefato.obter_propriedade("commit"))
    assert sorted(artefato.obter_propriedade("arquivos")) == sorted(_arquivos_do_commit(bancada.repositorio, commit))
    assert sorted(artefato.obter_propriedade("arquivos")) == ["soma.py", "verificar.py"]
    assert "declarados e fora do commit: inventado.py" in str(artefato.obter_propriedade("observacao"))


def test_todo_artifact_do_laco_leva_commit_e_os_arquivos_dele_nominal(tmp_path: Path) -> None:
    """Plano, aceite e fatias: cada Artifact tem o hash do commit e exatamente os arquivos que o git diz."""
    bancada = montar_bancada(tmp_path, roteiro_completo())

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    artefatos = [no for no in bancada.kernel.obter_view().listar_todos_os_nos() if no.tipo == TipoNo.ARTIFACT]
    assert {no.id for no in artefatos} >= {"art-goal-soma-plano", "art-aceite-goal-soma", "art-task-soma-f1-t1"}
    for artefato in artefatos:
        commit = str(artefato.obter_propriedade("commit"))
        assert len(commit) == 40, artefato.id
        assert sorted(artefato.obter_propriedade("arquivos")) == sorted(_arquivos_do_commit(bancada.repositorio, commit)), artefato.id
    plano = bancada.kernel.obter_view().obter_no("art-goal-soma-plano")
    assert plano is not None and plano.obter_propriedade("arquivos") == ["docs/goals/soma.md"]
    assert plano.obter_propriedade("observacao") == ""


def test_fora_do_commit_compara_caminhos_como_o_git_os_escreve_edge_case() -> None:
    """Caso de borda: `./a.py` e `pasta\\b.py` declarados são os mesmos que o git lista como `a.py` e `pasta/b.py`."""
    assert fora_do_commit(["./a.py", "pasta\\b.py"], ["a.py", "pasta/b.py"]) == ""
    assert fora_do_commit(["a.py", "c.py", "c.py"], ["a.py"]) == "declarados e fora do commit: c.py"
    assert fora_do_commit([], []) == ""


def test_laco_fecha_no_repositorio_sha256_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda (C4): no repositório `--object-format=sha256` o commit tem 64 hex, e o kernel o aceita como âncora.

    Antes, o kernel recusava o Artifact do plano e o laço parava em FALHA
    depois de pagar o planejador.
    """
    monkeypatch.setenv("GIT_DEFAULT_HASH", "sha256")
    bancada = montar_bancada(tmp_path, roteiro_completo())
    assert len(git(bancada.repositorio, "rev-parse", "HEAD").strip()) == 64

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    artefatos = [no for no in bancada.kernel.obter_view().listar_todos_os_nos() if no.tipo == TipoNo.ARTIFACT]
    assert {no.id for no in artefatos} >= {"art-goal-soma-plano", "art-aceite-goal-soma", "art-task-soma-f1-t1"}
    for artefato in artefatos:
        commit = str(artefato.obter_propriedade("commit"))
        assert len(commit) == 64, artefato.id
        assert sorted(artefato.obter_propriedade("arquivos")) == sorted(_arquivos_do_commit(bancada.repositorio, commit)), artefato.id
