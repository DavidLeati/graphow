"""A rota HTTP do placar de escopo, fora do roteador pelo mesmo motivo das de memória e propostas."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol

RAMO_PADRAO: str = "main"


class ManipuladorComEscopo(Protocol):
    """O que esta rota usa do manipulador HTTP: o servidor e a resposta JSON."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""


def tratar_get_escopo(manipulador: ManipuladorComEscopo, params: Mapping[str, list[str]]) -> None:
    """Publica o placar de escopo do Goal pedido em `goal`, no ramo de `ramo`."""
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    goal = params.get("goal", [""])[0].strip()
    resposta = manipulador.server.escopo_ctrl.ler(goal, ramo)
    manipulador._responder_json(resposta.corpo, resposta.status)
