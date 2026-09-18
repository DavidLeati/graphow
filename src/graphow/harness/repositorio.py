"""Do diretório de trabalho ao nome do projeto: o repositório é a unidade natural da memória.

O hook do ambiente roda dentro de uma pasta, e essa pasta diz em que projeto a
sessão aconteceu. Um worktree do git é a mesma base de código que o repositório
principal, então a memória de um não pode nascer separada da do outro: o `.git`
de um worktree é um arquivo que aponta para o repositório principal, e é ele
que é seguido. Sem git nenhum, a própria pasta responde.
"""

from pathlib import Path

MARCADOR_DO_GIT: str = ".git"
PREFIXO_DO_GITDIR: str = "gitdir:"
PASTA_DE_WORKTREES: str = "worktrees"
NOME_DE_PROJETO_RESERVA: str = "projeto"


def localizar_raiz_do_repositorio(caminho: Path) -> Path:
    """A raiz do repositório que contém o caminho; sem git, o próprio caminho.

    Num worktree, a raiz devolvida é a do repositório principal.
    """
    absoluto = caminho.expanduser().resolve()
    for candidato in (absoluto, *absoluto.parents):
        marcador = candidato / MARCADOR_DO_GIT
        if marcador.is_dir():
            return candidato
        if marcador.is_file():
            return _raiz_principal_do_worktree(marcador) or candidato
    return absoluto


def nome_do_projeto(caminho: Path) -> str:
    """O nome da pasta do repositório, que é o nome natural do projeto."""
    return localizar_raiz_do_repositorio(caminho).name or NOME_DE_PROJETO_RESERVA


def _raiz_principal_do_worktree(marcador: Path) -> Path | None:
    """Segue `gitdir: <principal>/.git/worktrees/<nome>` até o repositório principal."""
    gitdir = _ler_gitdir(marcador)
    if gitdir is None:
        return None
    partes = gitdir.parts
    if len(partes) < 4 or partes[-2] != PASTA_DE_WORKTREES or partes[-3] != MARCADOR_DO_GIT:
        return None
    return Path(*partes[:-3])


def _ler_gitdir(marcador: Path) -> Path | None:
    """O caminho declarado no arquivo `.git`, absoluto; None se o arquivo não o declara."""
    try:
        primeira_linha = marcador.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not primeira_linha.startswith(PREFIXO_DO_GITDIR):
        return None
    declarado = Path(primeira_linha[len(PREFIXO_DO_GITDIR) :].strip())
    if declarado.is_absolute():
        return declarado
    return (marcador.parent / declarado).resolve()
