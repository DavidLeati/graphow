"""Testes da resolução do repositório: a pasta do `.git` nomeia o projeto, e o worktree segue o principal."""

from pathlib import Path

from graphow.harness.repositorio import (
    NOME_DE_PROJETO_RESERVA,
    localizar_raiz_do_repositorio,
    nome_do_projeto,
)


def _criar_repositorio(raiz: Path) -> Path:
    """Uma pasta com `.git` como diretório, como num clone comum."""
    (raiz / ".git").mkdir(parents=True)
    return raiz


def test_subpasta_de_um_repositorio_resolve_para_a_raiz_nominal(tmp_path: Path) -> None:
    """O hook roda em qualquer subpasta; o projeto é a raiz do repositório."""
    raiz = _criar_repositorio(tmp_path / "graphow")
    subpasta = raiz / "src" / "graphow"
    subpasta.mkdir(parents=True)

    assert localizar_raiz_do_repositorio(subpasta) == raiz
    assert nome_do_projeto(subpasta) == "graphow"


def test_worktree_resolve_para_o_repositorio_principal_nominal(tmp_path: Path) -> None:
    """O `.git` de um worktree é um arquivo com `gitdir:`, e a memória é a do repositório principal."""
    principal = _criar_repositorio(tmp_path / "graphow")
    worktree = principal / ".claude" / "worktrees" / "memoria"
    worktree.mkdir(parents=True)
    gitdir = principal / ".git" / "worktrees" / "memoria"
    (worktree / ".git").write_text(f"gitdir: {gitdir}", encoding="utf-8")

    assert localizar_raiz_do_repositorio(worktree) == principal
    assert nome_do_projeto(worktree / "src") == "graphow"


def test_gitdir_relativo_e_resolvido_a_partir_do_arquivo_nominal(tmp_path: Path) -> None:
    """Alguns ambientes gravam o `gitdir` relativo ao próprio arquivo `.git`."""
    principal = _criar_repositorio(tmp_path / "graphow")
    worktree = tmp_path / "fora" / "wt"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: ../../graphow/.git/worktrees/wt", encoding="utf-8")

    assert localizar_raiz_do_repositorio(worktree) == principal


def test_pasta_sem_git_responde_por_si_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem repositório, a própria pasta é o projeto."""
    solta = tmp_path / "anotacoes"
    solta.mkdir()

    assert localizar_raiz_do_repositorio(solta) == solta.resolve()
    assert nome_do_projeto(solta) == "anotacoes"


def test_arquivo_git_sem_gitdir_nao_derruba_a_resolucao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: um `.git` de arquivo ilegível vira a própria pasta, não uma exceção."""
    pasta = tmp_path / "estranha"
    pasta.mkdir()
    (pasta / ".git").write_text("nada a ver", encoding="utf-8")

    assert localizar_raiz_do_repositorio(pasta) == pasta.resolve()


def test_raiz_do_disco_cai_no_nome_de_reserva_edge_case() -> None:
    """Caso de borda: a raiz do sistema de arquivos não tem nome; o projeto não fica vazio."""
    raiz = Path(Path.cwd().anchor)

    assert nome_do_projeto(raiz) == (raiz.name or NOME_DE_PROJETO_RESERVA)
