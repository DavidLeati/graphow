"""Controlador REST do placar de escopo de um Goal: só leitura.

O placar é o mesmo da vista do planejador e do humano: a projeção do grafo com
os limiares K e M que a política do Projeto do Goal entrega. A resposta leva
também, ao lado de cada limiar, de onde ele veio (preset, Projeto, global), para
a UI dizer ao humano o que ele está calibrando antes de responder o desvio.
"""

from http import HTTPStatus
from typing import Any

from graphow.context.escopo_do_goal import limiares_da_politica, tem_plano_aprovado
from graphow.context.governanca_vigente import resolver_politica_na_vista
from graphow.core.governanca import Gesto, PoliticaGovernanca
from graphow.core.types import TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.placar_escopo import montar_placar
from graphow.web.dto import RespostaHttpWeb


class EscopoWebController:
    """Lê o placar de escopo de um Goal do ramo, sem escrever nada."""

    def __init__(self, kernel: WriteKernel) -> None:
        self._kernel: WriteKernel = kernel

    def ler(self, id_goal: str, ramo_id: str = "main") -> RespostaHttpWeb:
        """O placar do Goal, se há plano aprovado e os limiares com a origem; 400 sem id, 404 sem Goal."""
        if not id_goal:
            return _recusa("Informe o Goal em ?goal=<id>", HTTPStatus.BAD_REQUEST)
        view = self._kernel.obter_view(ramo_id)
        no = view.obter_no(id_goal)
        if no is None or no.tipo != TipoNo.GOAL:
            return _recusa(f"'{id_goal}' não é um Goal do ramo '{ramo_id}'", HTTPStatus.NOT_FOUND)
        politica = resolver_politica_na_vista(id_goal, view)
        placar = montar_placar(view, id_goal, limiares_da_politica(politica))
        corpo: dict[str, Any] = {
            **placar.em_dicionario(),
            "sucesso": True,
            "ramo_id": ramo_id,
            "versao_log": view.versao_log,
            "plano_aprovado": tem_plano_aprovado(view, id_goal),
            "linhas": list(placar.linhas()),
            "linhas_de_desvio": list(placar.linhas_de_desvio()),
        }
        corpo["limiares"] = _limiares_com_origem(politica)
        return RespostaHttpWeb(corpo)


def _limiares_com_origem(politica: PoliticaGovernanca) -> dict[str, Any]:
    """K e M da política, cada um com o rótulo de origem que a configuração carrega."""
    return {
        "por_raiz": politica.limiar_desvio_por_raiz,
        "por_goal": politica.limiar_desvio_por_goal,
        "origem_por_raiz": politica.origem(Gesto.LIMIAR_DESVIO_POR_RAIZ),
        "origem_por_goal": politica.origem(Gesto.LIMIAR_DESVIO_POR_GOAL),
    }


def _recusa(mensagem: str, status: HTTPStatus) -> RespostaHttpWeb:
    """A leitura que não pôde ser feita, com o motivo."""
    return RespostaHttpWeb({"sucesso": False, "mensagem": mensagem}, status)
