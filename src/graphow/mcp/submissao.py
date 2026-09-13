"""Submissão de patches originados em ferramentas MCP sob a identidade da sessão."""

from dataclasses import dataclass, field
from typing import Any

from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP

RAMO_PADRAO: str = "main"


@dataclass(frozen=True)
class ContextoFerramentaMCP:
    """Dependências compartilhadas por todas as ferramentas de uma sessão MCP."""

    kernel: WriteKernel
    identidade: IdentidadeSessaoMCP


@dataclass(frozen=True)
class PedidoSubmissaoMCP:
    """Descrição imutável de um lote de operações a submeter ao kernel."""

    operacoes: tuple[ItemPatch, ...]
    justificativa: str
    ramo_id: str = RAMO_PADRAO
    identificadores_criados: dict[str, str] = field(default_factory=dict)


class SubmissorPatchMCP:
    """Encaminha operações ao kernel usando sempre o papel fixado na sessão."""

    def __init__(self, contexto: ContextoFerramentaMCP) -> None:
        self._contexto: ContextoFerramentaMCP = contexto

    def submeter(self, pedido: PedidoSubmissaoMCP) -> ResultadoSubmissao:
        """Constrói a proposta com a identidade da sessão e a envia aos portões."""
        dados = DadosPropostaPatch(
            autor=self._contexto.identidade.autor,
            papel=self._contexto.identidade.papel,
            operacoes=pedido.operacoes,
            justificativa=pedido.justificativa,
            ramo_id=pedido.ramo_id,
        )
        return self._contexto.kernel.submeter_patch(PropostaPatch.criar(dados))

    def submeter_e_relatar(self, pedido: PedidoSubmissaoMCP) -> dict[str, Any]:
        """Submete o lote e devolve a resposta padronizada da ferramenta MCP."""
        recibo = self.submeter(pedido)
        resposta: dict[str, Any] = {
            "sucesso": recibo.sucesso,
            "mensagem": recibo.mensagem,
            "versao_log": recibo.versao_log,
        }
        if recibo.modo_de_falha is not None:
            resposta["modo_de_falha"] = recibo.modo_de_falha
        resposta.update(pedido.identificadores_criados)
        return resposta


def extrair_ramo(argumentos: dict[str, Any]) -> str:
    """Lê o ramo alvo dos argumentos, com o ramo principal como padrão."""
    return str(argumentos.get("ramo_id", RAMO_PADRAO))
