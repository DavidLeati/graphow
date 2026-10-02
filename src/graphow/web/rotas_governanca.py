"""As rotas HTTP da governança, fora do roteador para ele continuar do tamanho de um roteador.

Como as de memória, recebem o próprio manipulador. Aqui moram também as rotas
com id no caminho (`/api/projetos/<id>/governanca`, `/api/tarefas/<id>/liberar-posse`),
que o despacho por caminho exato do roteador não alcança.
"""

from collections.abc import Mapping
from http import HTTPStatus
import re
from typing import Any, Protocol
import urllib.parse

from graphow.web.conversao_requisicoes import extrair_ramo
from graphow.web.dto import RequisicaoGovernanca, RespostaHttpWeb
from graphow.web.rest_governanca_controller import LIMITE_PADRAO_DA_AUDITORIA, GovernancaWebController

RAMO_PADRAO: str = "main"
CAMINHO_GLOBAL: str = "/api/governanca"
CAMINHO_GLOBAL_ESCRITA: str = "/api/governanca/global"
CAMINHO_AUDITORIA: str = "/api/governanca/auditoria"
ROTA_DO_PROJETO: re.Pattern[str] = re.compile(r"^/api/projetos/([^/]+)/governanca$")
ROTA_LIBERAR_POSSE: re.Pattern[str] = re.compile(r"^/api/tarefas/([^/]+)/liberar-posse$")
CAMPOS_DA_ESCRITA_GLOBAL: frozenset[str] = frozenset({"preset", "personalizada", "ramo_id"})
CAMPOS_DA_ESCRITA_DO_PROJETO: frozenset[str] = CAMPOS_DA_ESCRITA_GLOBAL | {"operacao"}
CAMPOS_DA_LIBERACAO: frozenset[str] = frozenset({"ramo_id"})


class ManipuladorComGovernanca(Protocol):
    """O que estas rotas usam do manipulador HTTP: o servidor, o corpo e as respostas padrão."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""

    def _ler_payload_json(self) -> dict[str, Any]:
        """Lê o corpo da requisição e o desserializa em dicionário."""

    def _recusar_identidade_declarada(self, payload: Mapping[str, Any]) -> bool:
        """Recusa o corpo que tenta declarar autor ou papel; True quando recusou."""


def tratar_get_governanca(
    manipulador: ManipuladorComGovernanca,
    caminho: str,
    params: Mapping[str, list[str]],
) -> bool:
    """Atende as leituras de governança; False quando o caminho não é de nenhuma delas."""
    resposta = _ler_governanca(manipulador.server.governanca_ctrl, caminho, params)
    if resposta is None:
        return False
    manipulador._responder_json(resposta.corpo, resposta.status)
    return True


def _ler_governanca(
    controlador: GovernancaWebController,
    caminho: str,
    params: Mapping[str, list[str]],
) -> RespostaHttpWeb | None:
    """A leitura que o caminho pede, ou None quando ele não é de governança."""
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    if caminho == CAMINHO_GLOBAL:
        return controlador.obter_global(ramo)
    if caminho == CAMINHO_AUDITORIA:
        return controlador.obter_auditoria(_ler_limite(params), ramo)
    correspondencia = ROTA_DO_PROJETO.match(caminho)
    if correspondencia:
        return controlador.obter_projeto(urllib.parse.unquote(correspondencia.group(1)), ramo)
    return None


def tratar_put_governanca(manipulador: ManipuladorComGovernanca, caminho: str) -> bool:
    """Atende as escritas de configuração; False quando o caminho não é de nenhuma delas."""
    correspondencia = ROTA_DO_PROJETO.match(caminho)
    if caminho != CAMINHO_GLOBAL_ESCRITA and not correspondencia:
        return False
    permitidos = CAMPOS_DA_ESCRITA_DO_PROJETO if correspondencia else CAMPOS_DA_ESCRITA_GLOBAL
    payload = manipulador._ler_payload_json()
    if _recusou_o_corpo(manipulador, payload, permitidos):
        return True
    controlador = manipulador.server.governanca_ctrl
    requisicao = converter_governanca(payload)
    if correspondencia:
        resposta = controlador.gravar_projeto(urllib.parse.unquote(correspondencia.group(1)), requisicao)
    else:
        resposta = controlador.gravar_global(requisicao)
    manipulador._responder_json(resposta.corpo, resposta.status)
    return True


def tratar_post_governanca(manipulador: ManipuladorComGovernanca, caminho: str) -> bool:
    """Atende a liberação de posse; False quando o caminho não é dela."""
    correspondencia = ROTA_LIBERAR_POSSE.match(caminho)
    if not correspondencia:
        return False
    payload = manipulador._ler_payload_json()
    if _recusou_o_corpo(manipulador, payload, CAMPOS_DA_LIBERACAO):
        return True
    id_task = urllib.parse.unquote(correspondencia.group(1))
    resposta = manipulador.server.governanca_ctrl.liberar_posse(id_task, extrair_ramo(payload))
    manipulador._responder_json(resposta.corpo, resposta.status)
    return True


def converter_governanca(payload: Mapping[str, Any]) -> RequisicaoGovernanca:
    """Monta o pedido de escrita de governança a partir do corpo recebido."""
    return RequisicaoGovernanca(
        preset=payload.get("preset"),
        personalizada=payload.get("personalizada"),
        operacao=payload.get("operacao"),
        ramo_id=extrair_ramo(payload),
    )


def _ler_limite(params: Mapping[str, list[str]]) -> int:
    """O `limite` pedido na consulta; ausente ou ilegível, o padrão da auditoria."""
    bruto = params.get("limite", [""])[0]
    return int(bruto) if bruto.lstrip("-").isdigit() else LIMITE_PADRAO_DA_AUDITORIA


def _recusou_o_corpo(manipulador: ManipuladorComGovernanca, payload: Any, permitidos: frozenset[str]) -> bool:
    """Responde 400 e devolve True quando o corpo não é objeto, declara identidade ou traz campo desconhecido."""
    if not isinstance(payload, Mapping):
        return _responder_recusa(manipulador, ["O corpo deve ser um objeto JSON"])
    if manipulador._recusar_identidade_declarada(payload):
        return True
    desconhecidos = sorted(set(payload) - permitidos)
    problemas = [f"campo desconhecido {campo!r}: use {', '.join(sorted(permitidos))}" for campo in desconhecidos]
    return bool(problemas) and _responder_recusa(manipulador, problemas)


def _responder_recusa(manipulador: ManipuladorComGovernanca, problemas: list[str]) -> bool:
    """Envia o 400 com cada problema do corpo; sempre True, para o chamador encerrar."""
    corpo = {"sucesso": False, "mensagem": "Corpo invalido: " + "; ".join(problemas), "problemas": problemas}
    manipulador._responder_json(corpo, HTTPStatus.BAD_REQUEST)
    return True
