"""Gera o corpus anonimizado de escopo a partir de um banco real, só em leitura.

Uso: python -m graphow.avaliacao.gerar_corpus_escopo <banco.db> <saida.jsonl.gz>

O banco nunca é aberto para escrita: a conexão é `mode=ro`. Use uma cópia do
banco, porque um banco em uso pode ter eventos ainda no `-wal`.
"""

import argparse
import gzip
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from graphow.avaliacao.anonimizacao_log import anonimizar_eventos

COLUNAS: str = (
    "id, seq, timestamp_utc, autor, papel, origem, tipo_evento, payload_json, versao_ontologia"
)


def ler_linhas(caminho_banco: Path) -> list[dict[str, Any]]:
    """Todas as linhas do ramo principal, lidas com a conexão em modo somente leitura."""
    conexao = sqlite3.connect(f"{caminho_banco.resolve().as_uri()}?mode=ro", uri=True)
    try:
        cursor = conexao.execute(f"SELECT {COLUNAS} FROM eventos WHERE ramo_id = 'main' ORDER BY seq")
        nomes = [coluna[0] for coluna in cursor.description]
        return [dict(zip(nomes, linha)) for linha in cursor.fetchall()]
    finally:
        conexao.close()


def gravar_corpus(eventos: Sequence[dict[str, Any]], destino: Path) -> int:
    """Grava um evento por linha, comprimido, de forma determinística; devolve os bytes."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas = (json.dumps(evento, sort_keys=True, separators=(",", ":")) for evento in eventos)
    with destino.open("wb") as arquivo:
        with gzip.GzipFile(fileobj=arquivo, mode="wb", mtime=0, filename="") as comprimido:
            comprimido.write(("\n".join(linhas) + "\n").encode("utf-8"))
    return destino.stat().st_size


def main(argv: Sequence[str] | None = None) -> int:
    """Lê o banco, anonimiza o recorte e grava o corpus."""
    analisador = argparse.ArgumentParser(description="Gera o corpus anonimizado do escopo governado.")
    analisador.add_argument("banco", type=Path, help="caminho do banco (de preferência uma cópia)")
    analisador.add_argument("saida", type=Path, help="caminho do corpus .jsonl.gz a gravar")
    argumentos = analisador.parse_args(argv)
    eventos = anonimizar_eventos(ler_linhas(argumentos.banco))
    tamanho = gravar_corpus(eventos, argumentos.saida)
    print(f"{len(eventos)} eventos, {tamanho} bytes em {argumentos.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
