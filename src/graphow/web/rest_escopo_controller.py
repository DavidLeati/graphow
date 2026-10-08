"""Controlador REST do escopo de um Goal: o placar e os dois gestos do humano, aprovar o plano e responder o desvio.

O placar é o mesmo da vista do planejador e do humano: a projeção do grafo com
os limiares K e M que a política do Projeto do Goal entrega. A resposta leva
também, ao lado de cada limiar, de onde ele veio (preset, Projeto, global), para
a UI dizer ao humano o que ele está calibrando antes de responder o desvio.

Os gestos passam pelas mesmas ferramentas do MCP (mcp/ferramentas_escopo.py), que
montam a entrada com o `seq` do log de agora e a repetem se o log andou; a web só
dá a elas a identidade fixada no servidor. O kernel continua sendo quem recusa.
"""

from http import HTTPStatus
from typing import Any

from graphow.context.escopo_do_goal import limiares_da_politica, tem_plano_aprovado
from graphow.context.governanca_vigente import resolver_politica_na_vista
from graphow.core.governanca import Gesto, PoliticaGovernanca
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.ferramentas_escopo import FerramentasEscopo
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.submissao import ContextoFerramentaMCP
from graphow.projection.escopo_plano import VersaoDoPlano, planos_do_goal, tasks_do_plano
from graphow.projection.graph_view import GrafoView
from graphow.projection.placar_escopo import montar_placar
from graphow.web.dto import RequisicaoRespostaDeDesvio, RespostaHttpWeb
from graphow.web.identidade_web import IdentidadeSessaoWeb


class EscopoWebController:
    """Lê o placar de escopo de um Goal do ramo e recebe do humano os gestos que o movem."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeSessaoWeb | None = None) -> None:
        self._kernel: WriteKernel = kernel
        identidade = identidade or IdentidadeSessaoWeb()
        sessao = IdentidadeSessaoMCP(autor=identidade.autor, papel=identidade.papel)
        self._gestos: FerramentasEscopo = FerramentasEscopo(ContextoFerramentaMCP(kernel, sessao))

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
        corpo["para_aprovar"] = _o_que_o_aprovar_congela(view, id_goal)
        return RespostaHttpWeb(corpo)

    def aprovar_plano(self, id_goal: str, ramo_id: str = "main") -> RespostaHttpWeb:
        """Congela as Tasks atuais do Goal como a próxima versão do plano; devolve o placar de depois."""
        recusa = self._recusar_goal(id_goal, ramo_id)
        if recusa is not None:
            return recusa
        recibo = self._gestos.aprovar_plano({"id_goal": id_goal, "ramo_id": ramo_id})
        return self._com_o_placar(recibo, id_goal, ramo_id)

    def responder_desvio(self, req: RequisicaoRespostaDeDesvio) -> RespostaHttpWeb:
        """Grava a resposta do humano ao desvio, com a raiz quando ela é de uma decisão; devolve o placar de depois."""
        recusa = self._recusar_goal(req.id_goal, req.ramo_id)
        if recusa is None and not req.resposta.strip():
            recusa = _recusa("Escreva a resposta ao desvio: o que se decide diante das Tasks novas.", HTTPStatus.BAD_REQUEST)
        if recusa is not None:
            return recusa
        argumentos = {"id_goal": req.id_goal, "resposta": req.resposta.strip(), "raiz": req.raiz, "ramo_id": req.ramo_id}
        return self._com_o_placar(self._gestos.responder_desvio(argumentos), req.id_goal, req.ramo_id)

    def _recusar_goal(self, id_goal: str, ramo_id: str) -> RespostaHttpWeb | None:
        """A recusa de o alvo não ser um Goal do ramo (400 sem id, 404 sem Goal); None quando ele existe."""
        if not id_goal:
            return _recusa("Informe o Goal em 'goal'", HTTPStatus.BAD_REQUEST)
        no = self._kernel.obter_view(ramo_id).obter_no(id_goal)
        if no is None or no.tipo != TipoNo.GOAL:
            return _recusa(f"'{id_goal}' não é um Goal do ramo '{ramo_id}'", HTTPStatus.NOT_FOUND)
        return None

    def _com_o_placar(self, recibo: dict[str, Any], id_goal: str, ramo_id: str) -> RespostaHttpWeb:
        """O placar de depois do gesto com o recibo dele; a recusa do kernel leva o motivo e um status que o diz."""
        if not recibo.get("sucesso"):
            return RespostaHttpWeb({**recibo, "sucesso": False}, _status_da_recusa(recibo))
        corpo = {**self.ler(id_goal, ramo_id).corpo, "recibo": recibo, "mensagem": recibo.get("mensagem", "")}
        return RespostaHttpWeb(corpo, HTTPStatus.OK)


def _status_da_recusa(recibo: dict[str, Any]) -> HTTPStatus:
    """403 quando o kernel nega o gesto ao papel; 422 para o resto, que é a forma ou a regra."""
    if recibo.get("modo_de_falha") == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value:
        return HTTPStatus.FORBIDDEN
    return HTTPStatus.UNPROCESSABLE_ENTITY


def _o_que_o_aprovar_congela(view: GrafoView, id_goal: str) -> dict[str, int]:
    """A versão que o próximo `aprovar_plano` grava e quantas Tasks do Goal ele congela agora."""
    versoes = planos_do_goal(view, id_goal)
    de_agora = VersaoDoPlano(versao=0, seq=view.versao_log, aprovado_por="", papel="")
    return {
        "versao": (versoes[-1].versao if versoes else 0) + 1,
        "tasks": len(tasks_do_plano(view, id_goal, de_agora)),
    }


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
