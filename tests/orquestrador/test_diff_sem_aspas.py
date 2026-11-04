"""Os diffs que vão ao briefing trazem o nome com acento como ele é, sem as aspas e o octal do `core.quotepath`."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from graphow.orquestrador.configuracao_do_aceite import diff_da_configuracao
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.diff_das_correcoes import diff_das_correcoes
from graphow.orquestrador.fatia_de_conflito import _objetivo
from graphow.orquestrador.git_do_goal import GitDoGoal
from graphow.orquestrador.rebase_no_clone import ConflitoNoRebase

from tests.orquestrador.apoio_git import criar_repositorio, git

OCTAL_DO_ACENTO: str = "\\303"


@dataclass(frozen=True)
class _Configuracao:
    """Só a base, que o objetivo da fatia de conflito cita."""

    base: str


@dataclass(frozen=True)
class _Contexto:
    """O que `_objetivo` lê do contexto do Goal: o git da área e a base."""

    git: GitDoGoal
    configuracao: _Configuracao


def _mudar(area: Path, arquivo: str, conteudo: str) -> str:
    """Grava o arquivo, commita e devolve o hash de antes do commit."""
    antes = git(area, "rev-parse", "HEAD").strip()
    (area / arquivo).parent.mkdir(parents=True, exist_ok=True)
    (area / arquivo).write_text(conteudo, encoding="utf-8", newline="\n")
    git(area, "add", "-A")
    git(area, "commit", "-q", "-m", f"muda {arquivo}")
    return antes


def test_objetivo_da_fatia_de_conflito_traz_o_nome_com_acento_edge_case(tmp_path: Path) -> None:
    """Caso de borda (Q1): o diff do conflito no objetivo da fatia cita `relatório.md`, não `relat\\303\\263rio.md`."""
    area = criar_repositorio(tmp_path / "r", {"relatório.md": "a\n"})
    antes = _mudar(area, "relatório.md", "b\n")
    contexto = cast(ContextoDoGoal, _Contexto(GitDoGoal(area), _Configuracao("main")))
    conflito = ConflitoNoRebase(antes, antes, antes, ("relatório.md",))

    objetivo = _objetivo(contexto, conflito, arvore="HEAD", arquivos=["relatório.md"], suite=None)

    assert "diff --git a/relatório.md b/relatório.md" in objetivo
    assert OCTAL_DO_ACENTO not in objetivo


def test_diff_das_correcoes_e_da_configuracao_trazem_o_nome_com_acento_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o corpo do diff das correções e o diff da configuração de teste também saem sem octal."""
    area = criar_repositorio(tmp_path / "r", {"relatório.md": "a\n", "testes_ação/conftest.py": "x = 1\n"})
    antes = _mudar(area, "relatório.md", "b\n")
    _mudar(area, "testes_ação/conftest.py", "x = 2\n")

    correcoes = diff_das_correcoes(GitDoGoal(area), antes, "soma")
    configuracao = diff_da_configuracao(area, antes)

    assert "diff --git a/relatório.md b/relatório.md" in correcoes and OCTAL_DO_ACENTO not in correcoes
    assert "diff --git a/testes_ação/conftest.py" in configuracao and OCTAL_DO_ACENTO not in configuracao
