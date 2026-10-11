"""Onde está o executável do Claude Code: `GRAPHOW_CLAUDE`, depois o PATH.

Nesta máquina o executável não está no PATH: o app desktop o guarda numa pasta
com a versão no nome, que muda a cada atualização. Os scripts do laboratório
fixavam esse caminho e quebravam na versão seguinte. O código nunca o fixa:
quem roda aponta `GRAPHOW_CLAUDE` para ele, e sem a variável vale o `claude`
do PATH. Sem nenhum dos dois, a recusa diz o que definir, em vez de um
`FileNotFoundError` no meio da execução.
"""

from collections.abc import Mapping
from pathlib import Path
import shutil

from graphow.core.exceptions import GraphowError

VARIAVEL_DO_EXECUTAVEL: str = "GRAPHOW_CLAUDE"
NOME_NO_PATH: str = "claude"


class ExecutavelAusente(GraphowError):
    """Não há executável do Claude Code para rodar a sessão."""


def descobrir_executavel(ambiente: Mapping[str, str]) -> Path:
    """O executável que `GRAPHOW_CLAUDE` indica, ou o `claude` do PATH do ambiente dado."""
    indicado = ambiente.get(VARIAVEL_DO_EXECUTAVEL, "").strip()
    if indicado:
        return _conferir_indicado(Path(indicado).expanduser())
    no_path = shutil.which(NOME_NO_PATH, path=ambiente.get("PATH"))
    if no_path is None:
        raise ExecutavelAusente(
            "executavel do Claude Code nao encontrado",
            {"dica": f"defina {VARIAVEL_DO_EXECUTAVEL} com o caminho do claude, ou ponha o claude no PATH"},
        )
    return Path(no_path)


def _conferir_indicado(caminho: Path) -> Path:
    """O caminho de `GRAPHOW_CLAUDE` tem de ser um arquivo: pasta ou caminho errado recusa já."""
    if not caminho.is_file():
        raise ExecutavelAusente(
            f"{VARIAVEL_DO_EXECUTAVEL} nao aponta para um arquivo",
            {VARIAVEL_DO_EXECUTAVEL: str(caminho)},
        )
    return caminho
