"""As rotas HTTP da memória, fora do roteador para ele continuar do tamanho de um roteador.

O manipulador HTTP despacha por caminho e delega a conversão e a resposta a
funções como estas, que recebem o próprio manipulador. É o que ele já fazia
com os métodos `_tratar_*`; aqui o mesmo contrato mora num módulo à parte
porque a memória é uma fatia coesa e o roteador está no limite de tamanho.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol

from graphow.web.conversao_requisicoes import (
    converter_promocao_de_aprendizado,
    converter_registro_de_aprendizado,
    serializar_memoria,
)

RAMO_PADRAO: str = "main"


class ManipuladorComMemoria(Protocol):
    """O que estas rotas usam do manipulador HTTP: o servidor e as duas respostas padrão."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""

    def _recusar_identidade_declarada(self, payload: Mapping[str, Any]) -> bool:
        """Recusa o corpo que tenta declarar autor ou papel; True quando recusou."""


def tratar_get_memoria(manipulador: ManipuladorComMemoria, params: Mapping[str, list[str]]) -> None:
    """Publica os aprendizados e as sessões do ramo para o painel de memória."""
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    resposta = manipulador.server.memoria_ctrl.obter_memoria(ramo)
    manipulador._responder_json(serializar_memoria(resposta), HTTPStatus.OK)


def tratar_post_aprendizado(manipulador: ManipuladorComMemoria, payload: Mapping[str, Any]) -> None:
    """Registra um aprendizado sob a identidade fixada no servidor."""
    if manipulador._recusar_identidade_declarada(payload):
        return
    recibo = manipulador.server.memoria_ctrl.registrar_aprendizado(converter_registro_de_aprendizado(payload))
    manipulador._responder_json(recibo.__dict__, HTTPStatus.CREATED if recibo.sucesso else HTTPStatus.BAD_REQUEST)


def tratar_post_promocao(manipulador: ManipuladorComMemoria, payload: Mapping[str, Any]) -> None:
    """Promove um aprendizado: o gesto humano que lhe dá alcance."""
    if manipulador._recusar_identidade_declarada(payload):
        return
    recibo = manipulador.server.memoria_ctrl.promover_aprendizado(converter_promocao_de_aprendizado(payload))
    manipulador._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)
