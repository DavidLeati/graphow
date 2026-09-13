"""Testes unitários para o transporte e o despacho JSON-RPC do servidor MCP stdio."""

import json

from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from graphow.mcp.stdio_protocolo import (
    CODIGO_METODO_NAO_ENCONTRADO,
    CanalJsonRpcEmMemoria,
    DespachanteJsonRpc,
)
from graphow.mcp.stdio_server import executar_loop_stdio
from graphow.storage.in_memory_store import InMemoryEventStore


def _montar_servidor(papel: str = "executor") -> GraphowMCPServer:
    """Cria um servidor MCP sobre um kernel em memória com o papel informado."""
    kernel = WriteKernel(InMemoryEventStore())
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("agente", papel))


def _montar_despachante(papel: str = "executor") -> tuple[DespachanteJsonRpc, CanalJsonRpcEmMemoria]:
    """Cria um despachante ligado a um canal de memória inspecionável."""
    canal = CanalJsonRpcEmMemoria()
    return DespachanteJsonRpc(_montar_servidor(papel), canal), canal


def test_initialize_anuncia_papel_da_sessao_nominal() -> None:
    """O aperto de mão declara o papel fixado, para o cliente não supor outro."""
    despachante, canal = _montar_despachante("planejador")
    despachante.despachar({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    resultado = canal.mensagens[0]["result"]
    assert resultado["serverInfo"]["papelDaSessao"] == "planejador"
    assert resultado["protocolVersion"] == "2024-11-05"


def test_tools_list_devolve_as_ferramentas_nominal() -> None:
    """A listagem de ferramentas atravessa o protocolo sem alteração."""
    despachante, canal = _montar_despachante()
    despachante.despachar({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    nomes = {ferramenta["name"] for ferramenta in canal.mensagens[0]["result"]["tools"]}
    assert "ler_vista" in nomes


def test_tools_call_encapsula_resultado_como_texto_nominal() -> None:
    """A resposta de uma ferramenta chega ao cliente como conteúdo textual JSON."""
    despachante, canal = _montar_despachante("humano")
    despachante.despachar(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "criar_projeto", "arguments": {"rotulo": "Projeto Teste"}},
        }
    )
    conteudo = json.loads(canal.mensagens[0]["result"]["content"][0]["text"])
    assert conteudo["sucesso"] is True
    assert conteudo["id_projeto"].startswith("proj-")


def test_metodo_desconhecido_retorna_erro_de_protocolo_edge_case() -> None:
    """Caso de borda: método fora do protocolo devolve o código JSON-RPC correto."""
    despachante, canal = _montar_despachante()
    despachante.despachar({"jsonrpc": "2.0", "id": 4, "method": "metodo/inventado"})
    erro = canal.mensagens[0]["error"]
    assert erro["code"] == CODIGO_METODO_NAO_ENCONTRADO
    assert "metodo/inventado" in erro["message"]


def test_notificacoes_nao_geram_resposta_edge_case() -> None:
    """Caso de borda: notificações e mensagens sem id não produzem resposta."""
    despachante, canal = _montar_despachante()
    despachante.despachar({"jsonrpc": "2.0", "method": "notifications/initialized"})
    despachante.despachar({"jsonrpc": "2.0", "method": "tools/list"})
    assert canal.mensagens == ()


def test_loop_ignora_linhas_vazias_e_registra_json_invalido_edge_case() -> None:
    """Caso de borda: linha em branco é ignorada e JSON quebrado vira falha registrada."""
    canal_de_entrada = CanalJsonRpcEmMemoria(
        linhas_de_entrada=("", "   ", "{isso nao e json}", '{"jsonrpc":"2.0","id":9,"method":"ping"}')
    )
    executar_loop_stdio(DespachanteJsonRpc(_montar_servidor(), canal_de_entrada), canal_de_entrada)
    assert len(canal_de_entrada.falhas) == 1
    assert "malformada" in canal_de_entrada.falhas[0]
    assert canal_de_entrada.mensagens[0]["id"] == 9


def test_requisicao_que_nao_e_objeto_e_registrada_edge_case() -> None:
    """Caso de borda: um array JSON válido não é uma requisição e é recusado."""
    canal_de_entrada = CanalJsonRpcEmMemoria(linhas_de_entrada=("[1, 2, 3]",))
    executar_loop_stdio(DespachanteJsonRpc(_montar_servidor(), canal_de_entrada), canal_de_entrada)
    assert canal_de_entrada.falhas == ("Requisicao JSON-RPC deve ser um objeto",)
