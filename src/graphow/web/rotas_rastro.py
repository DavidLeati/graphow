"""A rota GET /api/rastro: o rastro dos critérios de um Goal, o mesmo dado do `graphow orquestrar --rastro`.

O dado vem de orquestrador/rastro.py:ler_rastro, a leitura que a CLI também
usa. A conferência da verificação usa a leitura do canvas
(`LeituraPorGoal`) com a memória das pontas do controlador do canvas: o
inspetor pede o rastro a cada Criterio selecionado, e o git só roda de novo
quando a ponta da branch do Goal anda.

`?goal=<id>` devolve todos os critérios do plano; `?criterio=<id>` (o nó
Criterio, o que o inspetor tem à mão) acha o Goal que ele escopa e devolve só
ele. 400 sem nenhum dos dois, 404 quando o Goal não existe e quando os dois
vêm e o Criterio não é do Goal pedido (a mensagem diz de qual Goal ele é):
antes, a resposta era 200 com a lista vazia, como se o critério não tivesse
rastro.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Protocol

from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador.conferencia_na_leitura import LeituraPorGoal, MemoriaDasPontas
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.rastro import ler_rastro
from graphow.projection.graph_view import GrafoView
from graphow.web.dto import RespostaHttpWeb

RAMO_PADRAO: str = "main"


class ManipuladorComRastro(Protocol):
    """O que esta rota usa do manipulador HTTP: o servidor e a resposta JSON."""

    server: Any

    def _responder_json(self, conteudo: Mapping[str, Any], status: HTTPStatus) -> None:
        """Envia a resposta JSON com o status informado."""


class RastroWebController:
    """Lê o rastro dos critérios de um Goal do ramo, com a conferência guardada entre pedidos."""

    def __init__(self, kernel: WriteKernel, memoria: MemoriaDasPontas | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._memoria: MemoriaDasPontas = memoria or MemoriaDasPontas()

    def ler(self, id_goal: str, id_criterio: str = "", ramo_id: str = RAMO_PADRAO) -> RespostaHttpWeb:
        """O rastro do Goal (ou só do critério pedido); 400 sem alvo, 404 sem Goal."""
        if not id_goal and not id_criterio:
            return _recusa("Informe o Goal em ?goal=<id> ou o Criterio em ?criterio=<id>", HTTPStatus.BAD_REQUEST)
        view = self._kernel.obter_view(ramo_id)
        goals = _goals_do_criterio(view, id_criterio) if id_criterio else ()
        alvo = id_goal or next(iter(goals), "")
        estado = ler_estado(view, alvo) if alvo else None
        if estado is None:
            return _recusa(f"'{id_goal or id_criterio}' nao leva a um Goal do ramo '{ramo_id}'", HTTPStatus.NOT_FOUND)
        if id_criterio and alvo not in goals:
            return _recusa(_de_outro_goal(id_criterio, alvo, goals), HTTPStatus.NOT_FOUND)
        rastro = ler_rastro(view, estado, LeituraPorGoal(view, self._memoria)).em_json()
        if id_criterio:
            rastro["criterios"] = [criterio for criterio in rastro["criterios"] if criterio["no"] == id_criterio]
        return RespostaHttpWeb({"sucesso": True, "ramo_id": ramo_id, "versao_log": view.versao_log, **rastro})


def tratar_get_rastro(manipulador: ManipuladorComRastro, params: Mapping[str, list[str]]) -> None:
    """Publica o rastro pedido em `goal` ou `criterio`, no ramo de `ramo`."""
    goal = params.get("goal", [""])[0].strip()
    criterio = params.get("criterio", [""])[0].strip()
    ramo = params.get("ramo", [RAMO_PADRAO])[0]
    resposta = manipulador.server.rastro_ctrl.ler(goal, criterio, ramo)
    manipulador._responder_json(resposta.corpo, resposta.status)


def _goals_do_criterio(view: GrafoView, id_criterio: str) -> tuple[str, ...]:
    """Os Goals que o Criterio escopa; nenhum quando o nó não é Criterio ou não escopa Goal."""
    no = view.obter_no(id_criterio)
    if no is None or no.tipo != TipoNo.CRITERIO:
        return ()
    goals = (view.obter_no(aresta.destino_id) for aresta in view.obter_arestas_saida(id_criterio, TipoAresta.ESCOPA))
    return tuple(goal.id for goal in goals if goal is not None and goal.tipo == TipoNo.GOAL)


def _de_outro_goal(id_criterio: str, id_goal: str, goals: tuple[str, ...]) -> str:
    """A recusa do Criterio pedido com um Goal que não é o dele, dizendo de qual ele é."""
    if not goals:
        return f"'{id_criterio}' nao e Criterio de um Goal; o Goal '{id_goal}' nao o tem"
    return f"o Criterio '{id_criterio}' e do Goal {', '.join(repr(goal) for goal in goals)}, e nao do Goal '{id_goal}'"


def _recusa(mensagem: str, status: HTTPStatus) -> RespostaHttpWeb:
    """A leitura que não pôde ser feita, com o motivo."""
    return RespostaHttpWeb({"sucesso": False, "mensagem": mensagem}, status)
