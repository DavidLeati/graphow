"""Controlador REST especializado na simulação de orçamentos de tokens e visualização de contexto."""

from typing import Any

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista, VistaMaterializada
from graphow.core.exceptions import ErroEntidadeNaoEncontrada, ErroOrcamentoExcedido
from graphow.core.types import PapelAutor
from graphow.kernel.write_kernel import WriteKernel
from graphow.web.dto import RequisicaoSimularVista


class SimulationWebController:
    """Controlador para simular a visão materializada consumida por agentes de IA."""

    def __init__(self, kernel: WriteKernel, materializador: MaterializadorContexto | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()

    def simular_vista(self, req: RequisicaoSimularVista) -> dict[str, Any]:
        """Gera a vista em Markdown e métricas de tokens para o papel e orçamento solicitados."""
        view = self._kernel.obter_view(req.ramo_id)
        papel_autor = self._parse_papel(req.papel)
        req_interna = RequisicaoVista(
            id_alvo=req.id_alvo,
            papel=papel_autor,
            orcamento_tokens=req.orcamento_tokens,
        )
        try:
            vista: VistaMaterializada = self._materializador.materializar(req_interna, view)
            return {
                "sucesso": True,
                "id_alvo": vista.id_alvo,
                "papel": vista.papel.value,
                "orcamento_tokens": vista.orcamento_tokens,
                "tokens_estimados": vista.tokens_estimados,
                "conteudo_markdown": vista.conteudo_formatado,
                "nos_incluidos": list(vista.nos_incluidos),
                "vizinhos_expansiveis": list(vista.vizinhos_expansiveis),
            }
        except (ErroEntidadeNaoEncontrada, ErroOrcamentoExcedido) as err:
            return {"sucesso": False, "mensagem": str(err), "detalhes": dict(err.contexto)}

    def expandir_no(self, id_no: str, ramo_id: str = "main") -> dict[str, Any]:
        """Executa a ferramenta expandir_no sob demanda revelando propriedades e arestas."""
        view = self._kernel.obter_view(ramo_id)
        try:
            dados = self._materializador.expandir_no(id_no, view)
            return {"sucesso": True, "no": dados}
        except ErroEntidadeNaoEncontrada as err:
            return {"sucesso": False, "mensagem": str(err)}

    def _parse_papel(self, papel_str: str) -> PapelAutor:
        """Converte string de papel em enum com fallback seguro para EXECUTOR."""
        try:
            return PapelAutor(papel_str)
        except ValueError:
            return PapelAutor.EXECUTOR
