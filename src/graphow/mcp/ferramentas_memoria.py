"""Ferramentas MCP da memória em camadas: encerrar a sessão, registrar e promover aprendizados.

Encerrar a sessão é o gesto que separa a memória de curto prazo da de longo
prazo: é dele que o fechamento determinístico passa a abrir a vista e que o
motor reativo pede a condensação. O harness já sabia fechar a Sessao pelo hook
de fim; a superfície MCP não tinha como.
"""

from collections.abc import Callable, Mapping
from typing import Any

from graphow.core.types import StatusSessao, TipoNo
from graphow.mcp.construcao_operacoes import montar_operacao_definir_propriedade
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)

CAMPO_RESUMO: str = "resumo"


class FerramentasMemoria:
    """Operações que movem conhecimento entre as camadas de memória do grafo."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto
        self._submissor: SubmissorPatchMCP = SubmissorPatchMCP(contexto)

    def obter_manipuladores(self) -> Mapping[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        """Mapeia os nomes das ferramentas de memória aos seus executores."""
        return {"encerrar_sessao": self.encerrar_sessao}

    def encerrar_sessao(self, argumentos: Mapping[str, Any]) -> dict[str, Any]:
        """Fecha a Sessao e devolve o fechamento que a vista dela passa a abrir."""
        id_sessao = str(argumentos["id_sessao"])
        ramo = extrair_ramo(dict(argumentos))
        sessao = self._contexto.kernel.obter_view(ramo).obter_no(id_sessao)
        if sessao is None or sessao.tipo != TipoNo.SESSAO:
            return {"sucesso": False, "erro": f"Sessao '{id_sessao}' nao existe neste ramo"}
        pedido = PedidoSubmissaoMCP(
            operacoes=self._operacoes_de_encerramento(id_sessao, argumentos),
            justificativa=f"Encerramento da sessao {id_sessao}",
            ramo_id=ramo,
            identificadores_criados={"id_sessao": id_sessao},
        )
        resposta = self._submissor.submeter_e_relatar(pedido)
        if resposta["sucesso"]:
            resposta["fechamento"] = self._descrever_fechamento(id_sessao, ramo)
        return resposta

    def _operacoes_de_encerramento(self, id_sessao: str, argumentos: Mapping[str, Any]) -> tuple[Any, ...]:
        """Status concluida e, quando declarado, o resumo de quem encerra."""
        operacoes = [montar_operacao_definir_propriedade(id_sessao, "status", StatusSessao.CONCLUIDA.value)]
        resumo = str(argumentos.get(CAMPO_RESUMO, "") or "").strip()
        if resumo:
            operacoes.append(montar_operacao_definir_propriedade(id_sessao, CAMPO_RESUMO, resumo))
        return tuple(operacoes)

    def _descrever_fechamento(self, id_sessao: str, ramo: str) -> dict[str, object]:
        """O esqueleto determinístico da sessão recém-fechada, para quem encerrou conferir."""
        resumo = self._contexto.kernel.obter_view(ramo).obter_resumo(id_sessao)
        if resumo is None:
            return {}
        return resumo.fechamento.em_dicionario()
