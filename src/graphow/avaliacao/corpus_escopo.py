"""Carrega o corpus anonimizado de escopo e o reconstrói por replay da projeção.

O corpus (tests/avaliacao/dados/corpus_escopo.jsonl.gz, gerado por
gerar_corpus_escopo.py) guarda eventos já sem texto. Aqui eles voltam a ser
`EventoLog` e passam pelo mesmo redutor que projeta o log real, de modo que a
análise de escopo lê o grafo pelos mesmos tipos de produção, sem caminho paralelo.
"""

import gzip
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphow.core.events import EventoLog, TipoEvento
from graphow.core.models import GrafoEstado
from graphow.core.ontologia import VERSAO_ONTOLOGIA_DESCONHECIDA
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.projection.reducer import GrafoReducer

CAMINHO_DO_CORPUS: Path = (
    Path(__file__).resolve().parents[3] / "tests" / "avaliacao" / "dados" / "corpus_escopo.jsonl.gz"
)


@dataclass(frozen=True)
class CorpusEscopo:
    """Eventos do corpus em ordem de `seq` e o estado final que o replay produz."""

    eventos: tuple[EventoLog, ...]
    estado: GrafoEstado

    def estado_ate(self, seq: int) -> GrafoEstado:
        """Estado do grafo logo depois do evento `seq`, para as análises temporais."""
        return GrafoReducer.reconstruir([evento for evento in self.eventos if evento.seq <= seq])


def evento_do_corpus(registro: dict[str, Any]) -> EventoLog:
    """Reconstrói o evento a partir da linha do corpus; o id do evento é derivado do `seq`."""
    versao = registro.get("versao_ontologia")
    return EventoLog(
        id=f"ev-{registro['seq']}",
        seq=int(registro["seq"]),
        timestamp_utc=str(registro["timestamp_utc"]),
        autor=str(registro["autor"]),
        papel=PapelAutor(registro["papel"]),
        origem=OrigemEvento(registro["origem"]),
        tipo_evento=TipoEvento(registro["tipo_evento"]),
        payload=dict(registro["payload"]),
        versao_ontologia=str(versao) if versao is not None else VERSAO_ONTOLOGIA_DESCONHECIDA,
    )


def ler_registros(caminho: Path) -> Iterable[dict[str, Any]]:
    """Linhas do corpus, uma por evento, na ordem gravada."""
    with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo if linha.strip()]


def carregar_corpus(caminho: Path | None = None) -> CorpusEscopo:
    """Lê o corpus e projeta o grafo pelo redutor de produção."""
    registros = ler_registros(caminho or CAMINHO_DO_CORPUS)
    eventos = tuple(sorted((evento_do_corpus(r) for r in registros), key=lambda evento: evento.seq))
    return CorpusEscopo(eventos=eventos, estado=GrafoReducer.reconstruir(eventos))
