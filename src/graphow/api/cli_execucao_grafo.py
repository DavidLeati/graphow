"""Manipuladores dos subcomandos que operam sobre um grafo já aberto."""

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import sys

from graphow.api.cli import GraphowCLI
from graphow.api.console import EscritorConsole
from graphow.harness.entrada_hook import MODELO_DESCONHECIDO, EntradaDeHook, ler_entrada_de_hook
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.localizador_banco import LocalizacaoBanco

CODIGO_SUCESSO: int = 0
CODIGO_FALHA_DOMINIO: int = 1


@dataclass(frozen=True)
class DependenciasComandosGrafo:
    """Dependências já construídas que os subcomandos de grafo consomem."""

    cli: GraphowCLI
    kernel: WriteKernel
    console: EscritorConsole


class ManipuladorComandosGrafo:
    """Executa subcomandos que exigem um kernel de escrita já construído."""

    def __init__(self, dependencias: DependenciasComandosGrafo) -> None:
        self._cli: GraphowCLI = dependencias.cli
        self._kernel: WriteKernel = dependencias.kernel
        self._console: EscritorConsole = dependencias.console

    def executar(self, argumentos: argparse.Namespace, localizacao: LocalizacaoBanco) -> int:
        """Encaminha para o manipulador correspondente ao subcomando informado."""
        manipuladores: Mapping[str, Callable[[argparse.Namespace], int]] = {
            "init": self._executar_init,
            "task-create": self._executar_task_create,
            "task-list": self._executar_task_list,
            "print": self._executar_print,
            "web": self._executar_web,
            "mcp": self._executar_mcp,
            "harness": self._executar_harness,
        }
        manipulador = manipuladores.get(argumentos.comando)
        if manipulador is None:
            self._console.escrever_linha(f"Comando desconhecido: {argumentos.comando}")
            return CODIGO_SUCESSO
        self._registrar_banco_em_uso(localizacao)
        return manipulador(argumentos)

    def _registrar_banco_em_uso(self, localizacao: LocalizacaoBanco) -> None:
        """Informa qual banco está sendo usado, evitando ambiguidade entre cópias."""
        self._console.escrever_linha(f"Banco: {localizacao.caminho_absoluto_texto}")

    def _executar_init(self, argumentos: argparse.Namespace) -> int:
        """Confirma a criação do esquema, já realizada na abertura do repositório."""
        self._console.escrever_linha("Banco de eventos inicializado.")
        return CODIGO_SUCESSO

    def _executar_task_create(self, argumentos: argparse.Namespace) -> int:
        """Cria uma tarefa vinculada à sessão informada."""
        id_criado = self._cli.criar_task(argumentos.titulo, argumentos.sessao)
        self._console.escrever_linha(f"Task criada com sucesso: {id_criado}")
        return CODIGO_SUCESSO

    def _executar_task_list(self, argumentos: argparse.Namespace) -> int:
        """Lista as tarefas existentes no ramo principal."""
        for tarefa in self._cli.listar_tasks():
            self._console.escrever_linha(f"[{tarefa.id}] {tarefa.rotulo} - Status: {tarefa.status}")
        return CODIGO_SUCESSO

    def _executar_print(self, argumentos: argparse.Namespace) -> int:
        """Imprime o sumário textual completo do grafo."""
        self._console.escrever_linha(self._cli.montar_sumario_grafo())
        return CODIGO_SUCESSO

    def _executar_web(self, argumentos: argparse.Namespace) -> int:
        """Inicia o servidor web bloqueante da interface visual."""
        self._cli.iniciar_servidor_web(porta=argumentos.port, host=argumentos.host)
        return CODIGO_SUCESSO

    def _executar_harness(self, argumentos: argparse.Namespace) -> int:
        """Registra o disparo do hook como evento de execução no log."""
        pedido = self._montar_pedido_de_harness(argumentos, self._ler_payload(argumentos))
        if pedido is None:
            self._console.escrever_linha(
                "Harness sem id de sessao: o JSON do hook nao trouxe 'session_id'"
            )
            return CODIGO_FALHA_DOMINIO
        recibo = ServicoHarness(self._kernel).registrar(pedido)
        self._console.escrever_linha(f"[{recibo.id_run}] {recibo.mensagem} (versao {recibo.versao_log})")
        return CODIGO_SUCESSO if recibo.sucesso else CODIGO_FALHA_DOMINIO

    def _ler_payload(self, argumentos: argparse.Namespace) -> EntradaDeHook:
        """Consome a entrada padrão apenas quando o hook foi declarado como origem."""
        if not argumentos.entrada_hook:
            return EntradaDeHook()
        return ler_entrada_de_hook(sys.stdin)

    def _montar_pedido_de_harness(
        self,
        argumentos: argparse.Namespace,
        entrada: EntradaDeHook,
    ) -> PedidoDeCicloDeVida | None:
        """Funde argumento e payload, recusando o disparo sem sessão identificada."""
        id_sessao = argumentos.sessao or entrada.id_sessao
        if not id_sessao:
            return None
        return PedidoDeCicloDeVida(
            fase=FaseDoHarness(argumentos.fase),
            id_sessao=id_sessao,
            id_setor=argumentos.setor,
            modelo=self._resolver_modelo(argumentos.modelo, entrada.modelo),
            resumo=argumentos.resumo or entrada.resumo,
        )

    def _resolver_modelo(self, declarado: str, do_hook: str) -> str:
        """O modelo escrito na linha de comando vence; o payload preenche a lacuna."""
        if declarado and declarado != MODELO_DESCONHECIDO:
            return declarado
        return do_hook

    def _executar_mcp(self, argumentos: argparse.Namespace) -> int:
        """Inicia o servidor MCP com a identidade fixada no momento da abertura."""
        from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
        from graphow.mcp.stdio_server import iniciar_stdio_server

        identidade = IdentidadeSessaoMCP.criar(argumentos.autor, argumentos.papel)
        iniciar_stdio_server(self._kernel, identidade)
        return CODIGO_SUCESSO
