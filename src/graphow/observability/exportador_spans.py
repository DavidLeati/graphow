"""Exportador de spans para arquivo NDJSON, uma linha por span.

O tracer guardava spans em memória e o processo terminava levando tudo junto —
"não exporta nada" era a leitura correta. Este destino escreve cada span assim
que ele nasce, no formato de campos do modelo OTLP, para que uma sessão real
deixe um arquivo que outra ferramenta consiga ler. Ver achado A-13.
"""

import json
from pathlib import Path
import threading

from graphow.observability.tracer import DadosSpanDTO, SpanGenAI, Tracer, criar_span, serializar_span


class TracerArquivoNDJSON(Tracer):
    """Escreve cada span como uma linha JSON no arquivo indicado."""

    def __init__(self, caminho: str | Path) -> None:
        self._caminho: Path = Path(caminho)
        self._lock: threading.RLock = threading.RLock()
        self._caminho.parent.mkdir(parents=True, exist_ok=True)

    @property
    def caminho(self) -> Path:
        """Arquivo em que os spans estão sendo acumulados."""
        return self._caminho

    def registrar_span(self, dados: DadosSpanDTO) -> SpanGenAI:
        """Materializa o span e o acrescenta ao arquivo, sem reter nada em memória."""
        span = criar_span(dados)
        linha = json.dumps(serializar_span(span), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._acrescentar(linha)
        return span

    def _acrescentar(self, linha: str) -> None:
        """Acrescenta uma linha ao arquivo, criando-o na primeira escrita."""
        with self._caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(f"{linha}\n")
