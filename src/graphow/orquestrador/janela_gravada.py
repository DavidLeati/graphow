"""A janela da foto do humano gravada em disco enquanto está aberta, para a retomada depois de uma queda.

O processo que cai no meio de uma janela (orquestrador/janela_do_humano.py)
não a confere: a sessão que plantou um programa na configuração global do git
ficava sem conferência, e a chamada seguinte rodava git no humano e no clone
(`retomar_o_rebase`, `preparar_area`) antes de qualquer foto. Por isso a
janela, ao abrir, grava aqui o que a conferência dos arquivos que mudam o git
precisa: a lista deles (`ArquivosDoGit`), o sha256 de cada um, a salvaguarda
e os não rastreados que ela guarda. Ao fechar, a gravação sai. A chamada
seguinte, antes do primeiro git, relê os arquivos contra a gravação que
sobrou, sem processo nenhum, e a apaga.
"""

import json
from pathlib import Path
from typing import Any

from graphow.orquestrador.arquivos_do_git import ArquivosDoGit
from graphow.orquestrador.foto_do_humano import NAO_RASTREADO, ArquivoListado, FotoDoHumano, soltos_da_salvaguarda
from graphow.orquestrador.salvaguarda_do_humano import Salvaguarda

# O arquivo da janela aberta, na pasta de estado do Goal (fora do clone e do repositório do humano).
JANELA_GRAVADA: str = "janela-do-humano-aberta.json"


def gravar_a_janela(antes: FotoDoHumano, caminho: Path) -> None:
    """A foto de antes, no que a conferência dos arquivos do git usa, gravada em JSON no caminho dado."""
    vigia, soltos = antes.vigia, soltos_da_salvaguarda(antes)
    dados = {"repositorio": str(antes.repositorio), "pasta_do_git": str(vigia.pasta_do_git), "comum": str(vigia.comum),
             "arquivos": [str(p) for p in vigia.arquivos], "pastas": [str(p) for p in vigia.pastas], "do_git": dict(antes.do_git),
             "salvaguarda": [antes.salvaguarda.stash, antes.salvaguarda.soltos, antes.salvaguarda.pasta],
             "soltos": {caminho: antes.conteudos[caminho] for caminho in soltos}}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def foto_gravada(caminho: Path) -> FotoDoHumano | None:
    """A foto de antes que a janela que não fechou gravou, com o bastante para conferir os arquivos do git; None sem
    gravação, ou com a que não se lê."""
    try:
        return _foto(json.loads(caminho.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _foto(dados: dict[str, Any]) -> FotoDoHumano:
    """A foto de antes a partir do JSON gravado: a lista dos arquivos do git, os sha256, a salvaguarda e os soltos."""
    repositorio = Path(dados["repositorio"])
    vigia = ArquivosDoGit(repositorio, Path(dados["pasta_do_git"]), Path(dados["comum"]), tuple(map(Path, dados["arquivos"])),
                          tuple(map(Path, dados["pastas"])))
    soltos: dict[str, str] = dados["soltos"]
    return FotoDoHumano(repositorio, "", {}, {}, {caminho: ArquivoListado(NAO_RASTREADO) for caminho in soltos}, soltos,
                        dados["do_git"], vigia, salvaguarda=Salvaguarda(*dados["salvaguarda"]))


def apagar_a_gravada(caminho: Path | None) -> None:
    """A gravação sai: a janela fechou, ou a retomada já a conferiu."""
    if caminho is not None:
        caminho.unlink(missing_ok=True)
