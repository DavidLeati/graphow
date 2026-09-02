"""Testes unitários para a submissão de patches sob a identidade da sessão MCP."""

from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.construcao_operacoes import EspecificacaoNo, montar_operacao_criar_no
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.submissao import (
    ContextoFerramentaMCP,
    PedidoSubmissaoMCP,
    SubmissorPatchMCP,
    extrair_ramo,
)
from graphow.storage.in_memory_store import InMemoryEventStore


def _construir_submissor(papel: str) -> tuple[SubmissorPatchMCP, WriteKernel]:
    """Monta um submissor sobre um kernel em memória com a identidade informada."""
    kernel = WriteKernel(InMemoryEventStore())
    contexto = ContextoFerramentaMCP(kernel=kernel, identidade=IdentidadeSessaoMCP.criar("agente", papel))
    return SubmissorPatchMCP(contexto), kernel


def test_submissao_registra_o_papel_da_sessao_nominal() -> None:
    """O evento persistido carrega o papel da sessão, não o do argumento."""
    submissor, kernel = _construir_submissor("planejador")
    operacao = montar_operacao_criar_no(EspecificacaoNo(id="t1", tipo=TipoNo.TASK, rotulo="Tarefa"))
    recibo = submissor.submeter(PedidoSubmissaoMCP(operacoes=(operacao,), justificativa="teste"))

    assert recibo.sucesso is True
    evento = kernel.obter_evento(recibo.eventos_gerados[0])
    assert evento is not None
    assert evento.papel == PapelAutor.PLANEJADOR
    assert evento.autor == "agente"


def test_relatorio_inclui_identificadores_criados_nominal() -> None:
    """A resposta padronizada devolve os identificadores gerados pela ferramenta."""
    submissor, _ = _construir_submissor("humano")
    operacao = montar_operacao_criar_no(EspecificacaoNo(id="p1", tipo=TipoNo.PROJETO, rotulo="Projeto"))
    resposta = submissor.submeter_e_relatar(
        PedidoSubmissaoMCP(
            operacoes=(operacao,),
            justificativa="criacao",
            identificadores_criados={"id_projeto": "p1"},
        )
    )
    assert resposta["sucesso"] is True
    assert resposta["id_projeto"] == "p1"
    assert resposta["versao_log"] >= 1


def test_relatorio_de_patch_rejeitado_preserva_mensagem_edge_case() -> None:
    """Caso de borda: patch barrado pelos portões devolve sucesso falso e motivo."""
    submissor, _ = _construir_submissor("revisor")
    operacao = montar_operacao_criar_no(EspecificacaoNo(id="t1", tipo=TipoNo.TASK, rotulo="Tarefa"))
    resposta = submissor.submeter_e_relatar(
        PedidoSubmissaoMCP(operacoes=(operacao,), justificativa="tentativa indevida")
    )
    assert resposta["sucesso"] is False
    assert "permissão" in resposta["mensagem"]


def test_submissao_em_ramo_alternativo_edge_case() -> None:
    """Caso de borda: o ramo informado no pedido é respeitado pelo kernel."""
    submissor, kernel = _construir_submissor("humano")
    operacao = montar_operacao_criar_no(EspecificacaoNo(id="n1", tipo=TipoNo.NOTE, rotulo="Nota"))
    recibo = submissor.submeter(
        PedidoSubmissaoMCP(operacoes=(operacao,), justificativa="nota", ramo_id="experimento")
    )
    assert recibo.sucesso is True
    assert kernel.obter_view("experimento").contem_no("n1") is True
    assert kernel.obter_view("main").contem_no("n1") is False


def test_extrai_ramo_com_padrao_main_edge_case() -> None:
    """Caso de borda: ausência de ramo nos argumentos resolve para o ramo principal."""
    assert extrair_ramo({}) == "main"
    assert extrair_ramo({"ramo_id": "experimento"}) == "experimento"
