"""Base dos manipuladores HTTP do canvas: a guarda na entrada e o JSON de ida e volta.

A guarda roda em `parse_request`, antes de qualquer `do_<METODO>`: nenhuma
rota nova escapa dela por esquecimento. A recusa fecha a conexão, porque o
corpo de uma escrita recusada fica sem ler no socket e seria lido como a
próxima requisição.
"""

from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import json
from typing import Any

from graphow.web.guarda_http import GuardaHTTP


class ManipuladorProtegido(BaseHTTPRequestHandler):
    """Manipulador que só despacha a requisição que a guarda do servidor aprova."""

    def parse_request(self) -> bool:
        """Lê a requisição e a submete à guarda antes de despachá-la."""
        if not super().parse_request():
            return False
        guarda: GuardaHTTP = getattr(self.server, "guarda")
        recusa = guarda.avaliar(self.command, self.headers)
        if recusa is None:
            return True
        self.close_connection = True
        self._responder_json({"sucesso": False, "mensagem": recusa.mensagem}, recusa.status)
        return False

    def _ler_payload_json(self) -> dict[str, Any]:
        """Lê o corpo da requisição e desserializa em dicionário."""
        comprimento = int(self.headers.get("Content-Length", 0))
        if comprimento == 0:
            return {}
        corpo = self.rfile.read(comprimento)
        try:
            return json.loads(corpo.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia resposta JSON formatada com headers adequados."""
        corpo_bytes = json.dumps(dict(conteudo), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo_bytes)))
        self.end_headers()
        self.wfile.write(corpo_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        """Silencia logs padrões do BaseHTTPRequestHandler para não poluir terminal."""
        pass
