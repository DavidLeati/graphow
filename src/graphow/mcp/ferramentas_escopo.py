"""Ferramentas MCP do escopo governado: aprovar o plano de um Goal e responder ao alerta de desvio.

Cada uma acrescenta uma entrada à lista do Goal (`planos` ou `respostas_de_desvio`).
A entrada tem `seq` igual ao `versao_log` de agora e leva o autor e o papel da
sessão, como o kernel exige (kernel/forma_do_escopo.py); quem monta a entrada
errada à mão, por `propor_patch`, é recusado. O papel é decidido pela política:
o humano sempre, o árbitro quando ela lhe entrega o gesto
(mcp/identidade_sessao.py e kernel/gestos_de_escopo.py).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoNo
from graphow.mcp.construcao_operacoes import montar_operacao_definir_propriedade
from graphow.mcp.submissao import ContextoFerramentaMCP, PedidoSubmissaoMCP, SubmissorPatchMCP, extrair_ramo

# O log pode avançar entre a leitura do `versao_log` e o commit: o `seq` da
# entrada ficaria velho. A ferramenta relê e repete enquanto o log andou.
TENTATIVAS_COM_SEQ_FRESCO: int = 3

MontarEntrada = Callable[[GrafoEstado, list[Any]], dict[str, Any]]


@dataclass(frozen=True)
class AcrescimoNoGoal:
    """Qual lista de qual Goal recebe a entrada nova, em que ramo e com que justificativa."""

    id_goal: str
    campo: str
    ramo_id: str
    justificativa: str


class FerramentasEscopo:
    """Gestos `aprovar_plano` e `responder_desvio`, que o kernel reserva à política."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de escopo aos seus executores."""
        return {
            "aprovar_plano": self.aprovar_plano,
            "responder_desvio": self.responder_desvio,
        }

    def aprovar_plano(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Grava a próxima versão do plano do Goal, com o `seq` do log de agora.

        As Tasks sob o Goal neste ponto do log são o plano da versão. Só a
        versão do humano vira referência do desvio.
        """
        id_goal = str(argumentos["id_goal"])
        sessao = str(argumentos.get("id_sessao") or "")
        justificativa = f"Aprovacao do plano do Goal {id_goal}" + (f" (sessao {sessao})" if sessao else "")
        alvo = AcrescimoNoGoal(id_goal, CAMPO_PLANOS, extrair_ramo(dict(argumentos)), justificativa)
        return self._acrescentar(alvo, self._versao_do_plano)

    def responder_desvio(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Grava a resposta ao alerta de desvio do Goal; com `raiz`, a dada àquela decisão."""
        id_goal = str(argumentos["id_goal"])
        resposta = str(argumentos["resposta"])
        raiz = str(argumentos["raiz"]) if argumentos.get("raiz") else None
        justificativa = f"Resposta ao desvio do Goal {id_goal}" + (f" na raiz {raiz}" if raiz else "")
        alvo = AcrescimoNoGoal(id_goal, CAMPO_RESPOSTAS_DE_DESVIO, extrair_ramo(dict(argumentos)), justificativa)
        return self._acrescentar(alvo, lambda estado, _anteriores: self._entrada_da_resposta(estado, resposta, raiz))

    def _acrescentar(self, alvo: AcrescimoNoGoal, montar_entrada: MontarEntrada) -> dict[str, Any]:
        """Submete a lista do Goal com uma entrada a mais; repete se o log andou e deixou o `seq` velho."""
        kernel = self._contexto.kernel
        resposta: dict[str, Any] = {}
        for _ in range(TENTATIVAS_COM_SEQ_FRESCO):
            estado = kernel.obter_estado(alvo.ramo_id)
            no = estado.nos.get(alvo.id_goal)
            if no is None or no.tipo != TipoNo.GOAL:
                return {"sucesso": False, "erro": f"Goal '{alvo.id_goal}' nao encontrado"}
            atual = no.propriedades.get(alvo.campo)
            anteriores = list(atual) if isinstance(atual, list) else []
            entrada = montar_entrada(estado, anteriores)
            pedido = PedidoSubmissaoMCP(
                operacoes=(montar_operacao_definir_propriedade(alvo.id_goal, alvo.campo, [*anteriores, entrada]),),
                justificativa=alvo.justificativa,
                ramo_id=alvo.ramo_id,
                identificadores_criados={"id_goal": alvo.id_goal, **_resumo_da_entrada(entrada)},
            )
            resposta = self._submissor.submeter_e_relatar(pedido)
            if resposta["sucesso"] or kernel.obter_estado(alvo.ramo_id).versao_log == estado.versao_log:
                break
        return resposta

    def _versao_do_plano(self, estado: GrafoEstado, anteriores: list[Any]) -> dict[str, Any]:
        """A versão seguinte do plano, aprovada por quem tem a sessão e no ponto do log de agora."""
        ultima = max((e["versao"] for e in anteriores if isinstance(e, dict) and isinstance(e.get("versao"), int)), default=0)
        identidade = self._contexto.identidade
        return {"versao": ultima + 1, "seq": estado.versao_log, "aprovado_por": identidade.autor, "papel": identidade.papel.value}

    def _entrada_da_resposta(self, estado: GrafoEstado, resposta: str, raiz: str | None) -> dict[str, Any]:
        """A resposta de desvio assinada por quem tem a sessão, no ponto do log de agora."""
        identidade = self._contexto.identidade
        return {
            "seq": estado.versao_log,
            "respondido_por": identidade.autor,
            "papel": identidade.papel.value,
            "raiz": raiz,
            "resposta": resposta,
        }


def _resumo_da_entrada(entrada: Mapping[str, Any]) -> dict[str, Any]:
    """O que o recibo repete da entrada gravada: a versão do plano e o `seq`."""
    return {chave: entrada[chave] for chave in ("versao", "seq") if chave in entrada}
