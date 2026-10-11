"""O repositório de uma execução, recriado da semente com o mesmo hash do laboratório.

A semente é a árvore do commit "Estado inicial" de cada projeto. Recriar o
commit com o mesmo autor, a mesma data e a mesma mensagem dá o mesmo hash, e é
isso que se confere: a execução começa do estado exato em que as do laboratório
começaram, e qualquer diferença (um arquivo a mais, uma conversão de fim de
linha, um hook que mexeu na mensagem) recusa antes de gastar uma sessão.

O git roda com `core.autocrlf=false` só no commit da semente, para guardar os
bytes como estão; a configuração do repositório fica a da máquina, a mesma em
que o agente trabalhou no laboratório. As variáveis `GIT_DIR` e afins saem do
ambiente: rodando de dentro de um hook do git, elas apontariam para outro
repositório.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from graphow.bancada.projetos import ErroDaBancada, ProjetoDaBancada

EXECUTAVEL_DO_GIT: str = "git"
VARIAVEIS_DE_OUTRO_REPOSITORIO: frozenset[str] = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"})
CONFIGURACAO_DO_COMMIT_DA_SEMENTE: tuple[str, ...] = ("-c", "core.autocrlf=false", "-c", "commit.gpgsign=false")


@dataclass(frozen=True)
class GitDaBancada:
    """Roda o git num repositório da bancada, com ambiente próprio, e devolve a saída."""

    repositorio: Path
    ambiente: Mapping[str, str] | None = None

    def rodar(self, *argumentos: str) -> str:
        """A saída padrão; `ErroDaBancada` com a saída de erro quando o git falha."""
        comando = [EXECUTAVEL_DO_GIT, "-C", str(self.repositorio), *argumentos]
        try:
            resultado = subprocess.run(
                comando, capture_output=True, text=True, encoding="utf-8", check=False, env=self._ambiente()
            )
        except OSError as erro:
            raise ErroDaBancada("git indisponivel", {"erro": str(erro)}) from erro
        if resultado.returncode != 0:
            raise ErroDaBancada("git recusou o comando", {"comando": " ".join(argumentos), "erro": resultado.stderr.strip()})
        return resultado.stdout

    def _ambiente(self) -> dict[str, str]:
        """O ambiente dado, ou o do processo, sem as variáveis que apontam para outro repositório."""
        base = os.environ if self.ambiente is None else self.ambiente
        return {nome: valor for nome, valor in base.items() if nome.upper() not in VARIAVEIS_DE_OUTRO_REPOSITORIO}


def criar_repositorio(projeto: ProjetoDaBancada, destino: Path) -> str:
    """Copia a semente para o destino, faz o commit inicial e devolve o hash dele, conferido."""
    if destino.exists():
        raise ErroDaBancada("destino do repositorio ja existe", {"destino": str(destino)})
    shutil.copytree(projeto.pasta_da_semente, destino)
    semente = projeto.semente
    git = GitDaBancada(destino, _ambiente_do_commit(projeto))
    git.rodar("init", "-q", "-b", semente.ramo)
    git.rodar(*CONFIGURACAO_DO_COMMIT_DA_SEMENTE, "add", "-A")
    git.rodar(*CONFIGURACAO_DO_COMMIT_DA_SEMENTE, "commit", "-q", "-m", semente.mensagem)
    _conferir(git, projeto)
    return semente.commit


def _ambiente_do_commit(projeto: ProjetoDaBancada) -> dict[str, str]:
    """O ambiente do processo com autor, committer e data da semente."""
    semente = projeto.semente
    identidade = {
        "GIT_AUTHOR_NAME": semente.nome_do_autor,
        "GIT_AUTHOR_EMAIL": semente.email_do_autor,
        "GIT_AUTHOR_DATE": semente.data,
        "GIT_COMMITTER_NAME": semente.nome_do_autor,
        "GIT_COMMITTER_EMAIL": semente.email_do_autor,
        "GIT_COMMITTER_DATE": semente.data,
    }
    return {**os.environ, **identidade}


def _conferir(git: GitDaBancada, projeto: ProjetoDaBancada) -> None:
    """A árvore e o commit recriados são os do laboratório; a recusa diz qual divergiu."""
    arvore = git.rodar("rev-parse", "HEAD^{tree}").strip()
    commit = git.rodar("rev-parse", "HEAD").strip()
    esperado = projeto.semente
    if (arvore, commit) != (esperado.arvore, esperado.commit):
        raise ErroDaBancada(
            "a semente recriada nao reproduz o commit do laboratorio",
            {"projeto": projeto.nome, "arvore": arvore, "commit": commit, "commit_esperado": esperado.commit},
        )
