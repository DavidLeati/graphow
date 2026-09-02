"""Servidor MCP sobre transporte stdio com protocolo JSON-RPC 2.0."""

import argparse
from collections.abc import Mapping, Sequence
import json
import sys
from typing import Any

from graphow.core.exceptions import GraphowError
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from graphow.mcp.stdio_protocolo import (
    CanalJsonRpc,
    CanalJsonRpcStdio,
    DespachanteJsonRpc,
)
from graphow.storage.localizador_banco import LocalizadorBancoEventos, PreparadorDiretorioBanco
from graphow.storage.sqlite_store import SQLiteEventStore

CODIGO_SUCESSO: int = 0
CODIGO_FALHA_DOMINIO: int = 1


def executar_loop_stdio(despachante: DespachanteJsonRpc, canal: CanalJsonRpc) -> None:
    """Loop principal de leitura de linhas JSON-RPC vindas do transporte."""
    for linha in canal.ler_linhas():
        texto = linha.strip()
        if not texto:
            continue
        _processar_linha(texto, despachante, canal)


def _processar_linha(texto: str, despachante: DespachanteJsonRpc, canal: CanalJsonRpc) -> None:
    """Desserializa e encaminha uma única linha do protocolo."""
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        canal.registrar_falha(f"Linha JSON-RPC malformada: {erro}")
        return
    if not isinstance(dados, Mapping):
        canal.registrar_falha("Requisicao JSON-RPC deve ser um objeto")
        return
    despachante.despachar(dados)


def iniciar_stdio_server(kernel: WriteKernel, identidade: IdentidadeSessaoMCP) -> None:
    """Executa o loop stdio do MCP sobre um kernel e uma identidade já resolvidos."""
    canal = CanalJsonRpcStdio()
    canal.preparar_codificacao()
    servidor = GraphowMCPServer(kernel, identidade)
    executar_loop_stdio(DespachanteJsonRpc(servidor, canal), canal)


def _construir_parser() -> argparse.ArgumentParser:
    """Monta os argumentos aceitos pelo servidor MCP quando iniciado diretamente."""
    parser = argparse.ArgumentParser(description="Graphow MCP Stdio Server")
    parser.add_argument("--db", default=None, help="Caminho do arquivo SQLite")
    parser.add_argument(
        "--papel",
        required=True,
        choices=["planejador", "executor", "revisor", "humano"],
        help="Papel fixado para esta sessao. Agentes nao podem alterá-lo",
    )
    parser.add_argument("--autor", default="agente-mcp", help="Identificador do autor no log")
    return parser


def main(argumentos: Sequence[str] | None = None) -> int:
    """Ponto de entrada do módulo stdio MCP."""
    parsed = _construir_parser().parse_args(list(argumentos if argumentos is not None else sys.argv[1:]))
    localizacao = LocalizadorBancoEventos().resolver(parsed.db)
    PreparadorDiretorioBanco().garantir_diretorio(localizacao)
    try:
        identidade = IdentidadeSessaoMCP.criar(parsed.autor, parsed.papel)
    except GraphowError as erro:
        sys.stderr.write(erro.formatar_para_llm() + "\n")
        return CODIGO_FALHA_DOMINIO
    with SQLiteEventStore(localizacao.caminho_absoluto_texto) as repositorio:
        iniciar_stdio_server(WriteKernel(repositorio), identidade)
    return CODIGO_SUCESSO


if __name__ == "__main__":
    sys.exit(main())
