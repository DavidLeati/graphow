"""O git que a foto e a salvaguarda rodam no repositório do humano: sem fsmonitor, sem hooks e sem trava opcional.

A sessão que escapa do hook pode plantar programa na configuração do
humano. O `core.fsmonitor` roda no `git status` da própria foto, e o hook
`post-index-change` roda quando a salvaguarda grava a cópia do índice, os
dois fora do job da sessão. Todo git daqui leva os `-c` do git do orquestrador
(`SEM_CODIGO_PLANTADO`: `core.fsmonitor=false`, sem assinatura) e
`-c core.hooksPath=<pasta vazia nova>`, e o `-c` chega ao git que o
`status` roda dentro de cada submódulo, porque o git repassa o
`GIT_CONFIG_PARAMETERS` a ele. O ambiente sai sem as variáveis que apontariam
outro repositório, outro índice ou outra pasta de objetos; quem as quer as dá.
"""

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import tempfile

from graphow.orquestrador.git_do_goal import CHAVE_DOS_HOOKS, EXECUTAVEL_DO_GIT, SEM_CODIGO_PLANTADO, VARIAVEIS_DE_OUTRO_REPOSITORIO

SEM_TRAVA_OPCIONAL: str = "--no-optional-locks"
VARIAVEIS_DA_FOTO: frozenset[str] = VARIAVEIS_DE_OUTRO_REPOSITORIO | {"GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}


def git_da_foto(pasta: Path, argumentos: Sequence[str], *, entrada: bytes = b"", ambiente: Mapping[str, str] | None = None) -> str | None:
    """O git na pasta, sem fsmonitor nem hooks e sem trava opcional; a saída padrão, ou None quando ele falha."""
    variaveis = {nome: valor for nome, valor in os.environ.items() if nome.upper() not in VARIAVEIS_DA_FOTO}
    with tempfile.TemporaryDirectory(prefix="graphow-ganchos-") as vazia:
        comando = [EXECUTAVEL_DO_GIT, "-C", str(pasta), *SEM_CODIGO_PLANTADO, "-c", f"{CHAVE_DOS_HOOKS}={vazia}", SEM_TRAVA_OPCIONAL,
                   *argumentos]
        try:
            feito = subprocess.run(comando, input=entrada, env={**variaveis, **(ambiente or {})}, capture_output=True, check=False)
        except OSError:
            return None
    return feito.stdout.decode("utf-8", errors="replace") if feito.returncode == 0 else None


def e_ancestral_no_humano(repositorio: Path, antes: str, depois: str) -> bool:
    """`antes` está na história de `depois` (ou é ele), pelo git da foto."""
    return git_da_foto(repositorio, ("merge-base", "--is-ancestor", antes, depois)) is not None
