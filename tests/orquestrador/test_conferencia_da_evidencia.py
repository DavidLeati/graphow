"""A conferência da Evidence na leitura: vigente, desatualizada com os arquivos que mudaram, ou sem âncora com o motivo."""

import hashlib
from pathlib import Path

from graphow.orquestrador.conferencia_da_evidencia import DESATUALIZADA, SEM_ANCORA, VIGENTE, conferir_evidencia
from graphow.orquestrador.git_do_goal import GitDoGoal

from tests.orquestrador.apoio_git import criar_repositorio, git

ARQUIVOS: dict[str, str] = {"soma.py": "def somar(a, b):\n    return a + b\n", "README.md": "# brinquedo\n", "docs/uso.md": "uso\n"}


def _commitar(pasta: Path, arquivos: dict[str, str], mensagem: str = "muda") -> str:
    """Escreve os arquivos, commita e devolve o hash."""
    for nome, conteudo in arquivos.items():
        (pasta / nome).write_text(conteudo, encoding="utf-8", newline="\n")
    git(pasta, "add", "-A")
    git(pasta, "commit", "-q", "-m", mensagem)
    return git(pasta, "rev-parse", "HEAD").strip()


def test_evidence_antiga_sem_commit_e_sem_ancora_nominal(tmp_path: Path) -> None:
    """T3d1.2: a Evidence de antes da regra, sem commit, sai sem âncora, com o motivo; a de commit inválido também."""
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)

    antiga = conferir_evidencia({"arquivo": "soma.py", "linhas": "1-2", "trecho": "def somar"}, GitDoGoal(repositorio))
    curta = conferir_evidencia({"commit": "abc123", "arquivos": ["soma.py"]}, GitDoGoal(repositorio))

    assert antiga.estado == SEM_ANCORA and antiga.arquivos == () and "nao tem o commit" in antiga.motivo
    assert curta.estado == SEM_ANCORA and "'abc123' nao e um hash do git" in curta.motivo


def test_commit_que_sumiu_do_repositorio_e_sem_ancora_com_o_motivo_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o commit que não existe no repositório (história reescrita, outro clone) é sem âncora, com o motivo."""
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)

    sumiu = conferir_evidencia({"commit": "f" * 40, "arquivos": ["soma.py"]}, GitDoGoal(repositorio))

    assert sumiu.estado == SEM_ANCORA and f"o commit {'f' * 12} nao existe mais no repositorio" in sumiu.motivo


def test_desatualizada_lista_so_os_arquivos_dela_que_mudaram_nominal(tmp_path: Path) -> None:
    """Mudar um arquivo da Evidence a desatualiza com ele; mudar outro, não; sem lista, qualquer mudança conta."""
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)
    commit = git(repositorio, "rev-parse", "HEAD").strip()
    _commitar(repositorio, {"README.md": "# brinquedo\nUse somar.\n"})
    afirma = {"commit": commit, "arquivos": ["soma.py", "README.md"]}

    desatualizada = conferir_evidencia(afirma, GitDoGoal(repositorio))
    vigente = conferir_evidencia({"commit": commit, "arquivo": ".\\soma.py", "linhas": "1"}, GitDoGoal(repositorio))
    inteira = conferir_evidencia({"commit": commit}, GitDoGoal(repositorio))
    na_ponta_dela = conferir_evidencia(afirma, GitDoGoal(repositorio), ponta=commit)

    assert (desatualizada.estado, desatualizada.arquivos) == (DESATUALIZADA, ("README.md",))
    assert vigente.estado == VIGENTE and vigente.vigente and vigente.motivo == ""
    assert (inteira.estado, inteira.arquivos) == (DESATUALIZADA, ("README.md",))
    assert na_ponta_dela.estado == VIGENTE


def test_arquivo_renomeado_ou_apagado_desatualiza_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o arquivo da Evidence renomeado aparece pelo caminho antigo, que é o que ela cita."""
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)
    commit = git(repositorio, "rev-parse", "HEAD").strip()
    git(repositorio, "mv", "docs/uso.md", "docs/guia.md")
    git(repositorio, "commit", "-q", "-m", "renomeia")

    conferencia = conferir_evidencia({"commit": commit, "arquivos": ["docs/uso.md"]}, GitDoGoal(repositorio))

    assert (conferencia.estado, conferencia.arquivos) == (DESATUALIZADA, ("docs/uso.md",))


def test_commit_que_o_rebase_tirou_da_historia_confere_pelas_arvores_edge_case(tmp_path: Path) -> None:
    """Caso de borda: depois do rebase, o commit da Evidence saiu da história da ponta, mas a conferência compara as árvores.

    A base que andou num arquivo dela a desatualiza; noutro, não, e o motivo avisa que o commit está fora da branch.
    """
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)
    git(repositorio, "switch", "-q", "-c", "goal")
    verificado = _commitar(repositorio, {"soma.py": "def somar(a, b):\n    return b + a\n"})
    git(repositorio, "switch", "-q", "main")
    _commitar(repositorio, {"README.md": "# brinquedo da base\n"})
    git(repositorio, "switch", "-q", "goal")
    git(repositorio, "rebase", "-q", "main")

    so_soma = conferir_evidencia({"commit": verificado, "arquivos": ["soma.py"]}, GitDoGoal(repositorio))
    com_readme = conferir_evidencia({"commit": verificado, "arquivos": ["soma.py", "README.md"]}, GitDoGoal(repositorio))

    assert so_soma.estado == VIGENTE and so_soma.motivo.startswith(f"commit fora da branch: {verificado[:12]} ")
    assert (com_readme.estado, com_readme.arquivos) == (DESATUALIZADA, ("README.md",))


def test_revisao_confere_a_partir_da_arvore_revisada_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a revisão de risco guarda a árvore revisada; o commit da fatia com essa árvore não a desatualiza."""
    repositorio = criar_repositorio(tmp_path / "repo", ARQUIVOS)
    antes = git(repositorio, "rev-parse", "HEAD").strip()
    (repositorio / "soma.py").write_text("def somar(a, b):\n    return int(a) + int(b)\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "-A")
    arvore = git(repositorio, "write-tree").strip()
    git(repositorio, "commit", "-q", "-m", "fatia de risco")
    revisao = {"commit": antes, "arvore": arvore, "arquivos": ["soma.py"]}

    depois_do_commit = conferir_evidencia(revisao, GitDoGoal(repositorio))
    _commitar(repositorio, {"soma.py": "def somar(a, b):\n    return a + b\n"})
    depois_de_outra = conferir_evidencia(revisao, GitDoGoal(repositorio))
    sem_a_arvore = conferir_evidencia({**revisao, "arvore": "e" * 40}, GitDoGoal(repositorio))

    assert depois_do_commit.estado == VIGENTE
    assert (depois_de_outra.estado, depois_de_outra.arquivos) == (DESATUALIZADA, ("soma.py",))
    assert sem_a_arvore.estado == SEM_ANCORA and "a arvore revisada" in sem_a_arvore.motivo


def test_localizada_fora_do_git_confere_pelo_sha256_do_arquivo_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a ata lida fora de repositório git confere pelo conteúdo; mudou ou sumiu, desatualizada."""
    pasta = tmp_path / "atas"
    pasta.mkdir()
    (pasta / "ata.md").write_text("aprovado o teto de 5%\n", encoding="utf-8", newline="\n")
    lida = {"arquivo": "ata.md", "linhas": "1", "trecho": "aprovado o teto de 5%",
            "sha256": hashlib.sha256((pasta / "ata.md").read_bytes()).hexdigest()}

    igual = conferir_evidencia(lida, GitDoGoal(pasta))
    (pasta / "ata.md").write_text("aprovado o teto de 7%\n", encoding="utf-8", newline="\n")
    mudou = conferir_evidencia(lida, GitDoGoal(pasta))
    (pasta / "ata.md").unlink()
    sumiu = conferir_evidencia(lida, GitDoGoal(pasta))

    assert igual.estado == VIGENTE
    assert (mudou.estado, mudou.arquivos) == (DESATUALIZADA, ("ata.md",))
    assert sumiu.estado == DESATUALIZADA and "nao existe mais" in sumiu.motivo
