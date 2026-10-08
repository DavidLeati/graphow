"""As rotas HTTP do escopo (o placar e os dois gestos do humano), fora do roteador pelo mesmo motivo das de memória e propostas."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol

from graphow.web.dto import RequisicaoRespostaDeDesvio

RAMO_PADRAO: str = "main"
CAMINHO_APROVAR_PLANO: str = "/api/escopo/aprovar_plano"
CAMINHO_RESPONDER_DESVIO: str = "/api/escopo/responder_desvio"


class ManipuladorComEscopo(Protocol):
    """O que esta rota usa do manipulador HTTP: o servidor e a resposta JSON."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""

    def _ler_payload_json(self) -> dict[str, Any]:
        """Lê o corpo da requisição e o desserializa em dicionário."""

    def _recusar_identidade_declarada(self, payload: Mapping[str, Any]) -> bool:
        """Recusa o corpo que tenta declarar autor ou papel; True quando recusou."""


def tratar_get_escopo(manipulador: ManipuladorComEscopo, params: Mapping[str, list[str]]) -> None:
    """Publica o placar de escopo do Goal pedido em `goal`, no ramo de `ramo`."""
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    goal = params.get("goal", [""])[0].strip()
    resposta = manipulador.server.escopo_ctrl.ler(goal, ramo)
    manipulador._responder_json(resposta.corpo, resposta.status)


def tratar_post_escopo(manipulador: ManipuladorComEscopo, caminho: str) -> bool:
    """Atende aprovar o plano e responder o desvio, sob a identidade do servidor; False se o caminho não é deles."""
    if caminho not in (CAMINHO_APROVAR_PLANO, CAMINHO_RESPONDER_DESVIO):
        return False
    payload = manipulador._ler_payload_json()
    if manipulador._recusar_identidade_declarada(payload):
        return True
    controlador = manipulador.server.escopo_ctrl
    id_goal = str(payload.get("goal") or "").strip()
    ramo = str(payload.get("ramo") or RAMO_PADRAO)
    if caminho == CAMINHO_APROVAR_PLANO:
        resposta = controlador.aprovar_plano(id_goal, ramo)
    else:
        raiz = str(payload.get("raiz") or "").strip() or None
        resposta = controlador.responder_desvio(RequisicaoRespostaDeDesvio(id_goal, str(payload.get("resposta") or ""), raiz, ramo))
    manipulador._responder_json(resposta.corpo, resposta.status)
    return True
