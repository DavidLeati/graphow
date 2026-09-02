"""Transporte e despacho do protocolo JSON-RPC 2.0 usado pelo servidor MCP stdio."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping
import json
import sys
from typing import Any

from graphow.mcp.server import GraphowMCPServer

VERSAO_PROTOCOLO_MCP: str = "2024-11-05"
CODIGO_METODO_NAO_ENCONTRADO: int = -32601

METODOS_DE_NOTIFICACAO: frozenset[str] = frozenset(
    {"notifications/initialized", "notifications/cancelled"}
)


class CanalJsonRpc(ABC):
    """Contrato de entrada e saída de mensagens do protocolo JSON-RPC."""

    @abstractmethod
    def ler_linhas(self) -> Iterator[str]:
        """Itera as linhas recebidas do cliente MCP."""
        raise NotImplementedError

    @abstractmethod
    def escrever_mensagem(self, mensagem: Mapping[str, Any]) -> None:
        """Emite uma mensagem JSON-RPC serializada para o cliente."""
        raise NotImplementedError

    @abstractmethod
    def registrar_falha(self, mensagem: str) -> None:
        """Registra uma falha de transporte fora do canal de respostas."""
        raise NotImplementedError


class CanalJsonRpcStdio(CanalJsonRpc):
    """Transporte concreto sobre a entrada e a saída padrão do processo."""

    def preparar_codificacao(self) -> None:
        """Força UTF-8 nos fluxos, pois o protocolo MCP não admite outra codificação."""
        for fluxo in (sys.stdin, sys.stdout):
            reconfigurar = getattr(fluxo, "reconfigure", None)
            if callable(reconfigurar):
                reconfigurar(encoding="utf-8")

    def ler_linhas(self) -> Iterator[str]:
        """Itera as linhas da entrada padrão até o fechamento do canal."""
        return iter(sys.stdin)

    def escrever_mensagem(self, mensagem: Mapping[str, Any]) -> None:
        """Serializa e emite a mensagem em uma única linha na saída padrão."""
        sys.stdout.write(json.dumps(dict(mensagem), ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def registrar_falha(self, mensagem: str) -> None:
        """Escreve a falha na saída de erro, sem poluir o canal do protocolo."""
        sys.stderr.write(mensagem + "\n")
        sys.stderr.flush()


class CanalJsonRpcEmMemoria(CanalJsonRpc):
    """Transporte determinístico para testes, com linhas de entrada pré-definidas."""

    def __init__(self, linhas_de_entrada: tuple[str, ...] = ()) -> None:
        self._linhas_de_entrada: tuple[str, ...] = linhas_de_entrada
        self._mensagens: list[dict[str, Any]] = []
        self._falhas: list[str] = []

    def ler_linhas(self) -> Iterator[str]:
        """Itera as linhas fornecidas na construção."""
        return iter(self._linhas_de_entrada)

    def escrever_mensagem(self, mensagem: Mapping[str, Any]) -> None:
        """Acumula a mensagem emitida para inspeção posterior."""
        self._mensagens.append(dict(mensagem))

    def registrar_falha(self, mensagem: str) -> None:
        """Acumula a falha registrada para inspeção posterior."""
        self._falhas.append(mensagem)

    @property
    def mensagens(self) -> tuple[dict[str, Any], ...]:
        """Cópia imutável das mensagens emitidas."""
        return tuple(self._mensagens)

    @property
    def falhas(self) -> tuple[str, ...]:
        """Cópia imutável das falhas registradas."""
        return tuple(self._falhas)


class DespachanteJsonRpc:
    """Roteia requisições JSON-RPC para as capacidades do servidor MCP."""

    def __init__(self, servidor: GraphowMCPServer, canal: CanalJsonRpc) -> None:
        self._servidor: GraphowMCPServer = servidor
        self._canal: CanalJsonRpc = canal

    def despachar(self, requisicao: Mapping[str, Any]) -> None:
        """Encaminha a requisição ao método correspondente do protocolo."""
        metodo = str(requisicao.get("method", ""))
        identificador = requisicao.get("id")
        if metodo in METODOS_DE_NOTIFICACAO or identificador is None:
            return
        manipulador = self._obter_manipuladores().get(metodo)
        if manipulador is None:
            self._responder_erro(identificador, f"Metodo nao suportado: {metodo}")
            return
        manipulador(identificador, requisicao)

    def _obter_manipuladores(self) -> Mapping[str, Callable[[Any, Mapping[str, Any]], None]]:
        """Mapeia os métodos do protocolo MCP aos seus manipuladores."""
        return {
            "initialize": self._tratar_initialize,
            "ping": self._tratar_ping,
            "tools/list": self._tratar_tools_list,
            "tools/call": self._tratar_tools_call,
        }

    def _tratar_initialize(self, identificador: Any, requisicao: Mapping[str, Any]) -> None:
        """Responde ao aperto de mão inicial declarando as capacidades do servidor."""
        self._responder_sucesso(
            identificador,
            {
                "protocolVersion": VERSAO_PROTOCOLO_MCP,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "graphow",
                    "version": "0.1.0",
                    "papelDaSessao": self._servidor.identidade.papel.value,
                },
            },
        )

    def _tratar_ping(self, identificador: Any, requisicao: Mapping[str, Any]) -> None:
        """Responde ao ping de verificação de vivacidade."""
        self._responder_sucesso(identificador, {})

    def _tratar_tools_list(self, identificador: Any, requisicao: Mapping[str, Any]) -> None:
        """Lista as ferramentas registradas no servidor MCP."""
        self._responder_sucesso(identificador, {"tools": self._servidor.listar_ferramentas()})

    def _tratar_tools_call(self, identificador: Any, requisicao: Mapping[str, Any]) -> None:
        """Executa a ferramenta solicitada e encapsula o retorno como conteúdo textual."""
        parametros = requisicao.get("params", {})
        parametros_validos: Mapping[str, Any] = parametros if isinstance(parametros, Mapping) else {}
        argumentos = parametros_validos.get("arguments", {})
        resultado = self._servidor.executar_ferramenta(
            str(parametros_validos.get("name", "")),
            argumentos if isinstance(argumentos, Mapping) else {},
        )
        texto = json.dumps(resultado, indent=2, ensure_ascii=False)
        self._responder_sucesso(identificador, {"content": [{"type": "text", "text": texto}]})

    def _responder_sucesso(self, identificador: Any, resultado: Mapping[str, Any]) -> None:
        """Emite uma resposta JSON-RPC bem-sucedida."""
        self._canal.escrever_mensagem({"jsonrpc": "2.0", "id": identificador, "result": dict(resultado)})

    def _responder_erro(self, identificador: Any, mensagem: str) -> None:
        """Emite uma resposta JSON-RPC de erro de método."""
        self._canal.escrever_mensagem(
            {
                "jsonrpc": "2.0",
                "id": identificador,
                "error": {"code": CODIGO_METODO_NAO_ENCONTRADO, "message": mensagem},
            }
        )
