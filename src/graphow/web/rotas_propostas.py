"""As rotas HTTP da caixa de propostas fora do Goal, fora do roteador pelo mesmo motivo das da memória."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol

from graphow.web.conversao_requisicoes import converter_decisao_de_proposta, serializar_propostas

RAMO_PADRAO: str = "main"


class ManipuladorComPropostas(Protocol):
    """O que estas rotas usam do manipulador HTTP: o servidor e as duas respostas padrão."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""

    def _recusar_identidade_declarada(self, payload: Mapping[str, Any]) -> bool:
        """Recusa o corpo que tenta declarar autor ou papel; True quando recusou."""


def tratar_get_propostas(manipulador: ManipuladorComPropostas, params: Mapping[str, list[str]]) -> None:
    """Publica as propostas abertas do ramo, as de um Projeto quando `projeto` vem na query."""
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    projeto = params.get("projeto", [""])[0]
    resposta = manipulador.server.propostas_ctrl.listar(ramo, projeto or None)
    manipulador._responder_json(serializar_propostas(resposta), HTTPStatus.OK)


def tratar_post_decisao_de_proposta(manipulador: ManipuladorComPropostas, payload: Mapping[str, Any]) -> None:
    """Aceita ou descarta uma proposta sob a identidade fixada no servidor."""
    if manipulador._recusar_identidade_declarada(payload):
        return
    recibo = manipulador.server.propostas_ctrl.decidir(converter_decisao_de_proposta(payload))
    manipulador._responder_json(recibo.__dict__, HTTPStatus.OK if recibo.sucesso else HTTPStatus.BAD_REQUEST)
