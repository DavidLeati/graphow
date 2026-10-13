"""Apoio dos testes do orquestrador: um repositório git de brinquedo numa pasta temporária."""

from pathlib import Path
import subprocess

IDENTIDADE: tuple[str, ...] = ("-c", "user.name=Teste", "-c", "user.email=teste@exemplo.invalid")


def git(pasta: Path, *argumentos: str) -> str:
    """Roda o git na pasta e devolve a saída; falha o teste se o git falhar."""
    feito = subprocess.run(
        ["git", "-C", str(pasta), *argumentos], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert feito.returncode == 0, feito.stderr
    return feito.stdout


def git_bytes(pasta: Path, *argumentos: str) -> bytes:
    """Roda o git na pasta e devolve a saída em bytes, sem decodificar; falha o teste se o git falhar."""
    feito = subprocess.run(["git", "-C", str(pasta), *argumentos], capture_output=True, check=False)
    assert feito.returncode == 0, feito.stderr
    return feito.stdout


def criar_repositorio(pasta: Path, arquivos: dict[str, str] | None = None) -> Path:
    """Um repositório na branch main com um commit inicial e identidade local."""
    pasta.mkdir(parents=True)
    git(pasta, "init", "-q", "-b", "main")
    git(pasta, "config", "user.name", "Teste")
    git(pasta, "config", "user.email", "teste@exemplo.invalid")
    git(pasta, "config", "core.autocrlf", "false")
    for nome, conteudo in (arquivos or {"README.md": "# brinquedo\n"}).items():
        (pasta / nome).parent.mkdir(parents=True, exist_ok=True)
        (pasta / nome).write_text(conteudo, encoding="utf-8", newline="\n")
    git(pasta, "add", "-A")
    git(pasta, "commit", "-q", "-m", "Estado inicial")
    return pasta
