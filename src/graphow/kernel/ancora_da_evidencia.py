"""A âncora da Evidence sobre código: o commit em que o fato foi visto e os arquivos que ela afirma.

Na auditoria, 8 de 10 Evidence da api já não batiam com os arquivos 20
minutos depois, e o grafo não tinha como saber. A Evidence sobre código guarda
o `commit` em que foi verificada, para quem a lê conferir se os arquivos que
ela afirma mudaram desde ele (orquestrador/conferencia_da_evidencia.py).

A âncora é o `commit`, com 40 caracteres hexadecimais (64 no repositório
sha256). A Evidence localizada num arquivo fora de repositório git (a ata, a
planilha: decisão 1 do BRIEF) ancora no `sha256` do conteúdo dele. Os arquivos
que ela afirma são os `arquivos` que o orquestrador grava ou, na localizada, o
`arquivo` dela (`arquivos_afirmados`); sem nenhum, ela fala do commit inteiro.
"""

from collections.abc import Mapping
import re
from typing import Any

from graphow.core.orquestracao import ler_texto
from graphow.kernel.ancora_do_artifact import ANCORA_COMMIT, ANCORA_SHA256, PADRAO_DO_COMMIT, PADRAO_DO_SHA256
from graphow.kernel.localizacao import CAMPO_ARQUIVO

CAMPO_COMMIT: str = "commit"
CAMPO_SHA256: str = "sha256"
CAMPO_ARQUIVOS: str = "arquivos"


def _valido(padrao: re.Pattern[str], valor: object) -> bool:
    """O valor é texto e casa inteiro com o padrão."""
    return isinstance(valor, str) and padrao.fullmatch(valor) is not None


def ancora_da_evidencia(propriedades: Mapping[str, Any]) -> str | None:
    """`commit`, `sha256` (só com `arquivo`) ou None, quando a Evidence não tem âncora válida."""
    if _valido(PADRAO_DO_COMMIT, propriedades.get(CAMPO_COMMIT)):
        return ANCORA_COMMIT
    if _valido(PADRAO_DO_SHA256, propriedades.get(CAMPO_SHA256)) and ler_texto(propriedades, CAMPO_ARQUIVO):
        return ANCORA_SHA256
    return None


def arquivos_afirmados(propriedades: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Os `arquivos` gravados ou o `arquivo` da localizada; None quando a Evidence fala do commit inteiro."""
    lista = propriedades.get(CAMPO_ARQUIVOS)
    if isinstance(lista, list):
        return tuple(str(item) for item in lista if str(item).strip())
    arquivo = ler_texto(propriedades, CAMPO_ARQUIVO)
    return (arquivo,) if arquivo else None
