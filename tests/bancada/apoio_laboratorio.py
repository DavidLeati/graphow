"""O recorte dos logs do laboratório de 10/10/2026, desdobrado em disco como o laboratório o deixou.

`dados/laboratorio.json.gz` guarda, das seis execuções, só o que a medição lê:
do stream-json de cada raiz, as marcas `_lab`, o `system/init` e os eventos
`result` (sem o texto); de cada transcrição em `~/.claude/projects` (a da
sessão e as dos subagentes), a primeira e a última entrada de cada mensagem do
modelo, com o instante e o `usage`. Os logs inteiros têm 8 MB; o recorte, 47
KB, e dá os mesmos números. Os repositórios das entregas não estão nele.
"""

import gzip
import json
from pathlib import Path
from typing import Any

RECORTE: Path = Path(__file__).parent / "dados" / "laboratorio.json.gz"
PASTA_DOS_LOGS: dict[str, str] = {"graphow-0.4.4": "_runs", "enxuta": "b/_runs"}


def ler_recorte() -> dict[str, Any]:
    """O recorte por `<arquitetura>/<projeto>`: o stream (`stream`) e as transcrições (`transcricoes`)."""
    return json.loads(gzip.decompress(RECORTE.read_bytes()))


def desdobrar_recorte(destino: Path) -> tuple[Path, Path]:
    """A pasta do laboratório, com os logs em `_runs/` e `b/_runs/`, e a pasta de projetos com as transcrições."""
    laboratorio, projetos = destino / "laboratorio", destino / "projetos"
    for chave, execucao in ler_recorte().items():
        arquitetura, projeto = chave.split("/")
        log = laboratorio / PASTA_DOS_LOGS[arquitetura] / f"{projeto}.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("".join(json.dumps(evento) + "\n" for evento in execucao["stream"]), encoding="utf-8")
        for relativo, entradas in execucao["transcricoes"].items():
            caminho = projetos / chave.replace("/", "-") / relativo
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text("".join(json.dumps(entrada) + "\n" for entrada in entradas), encoding="utf-8")
    return laboratorio, projetos
