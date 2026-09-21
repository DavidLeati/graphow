"""Manipuladores dos subcomandos que operam sobre um grafo já aberto."""

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from graphow.api.cli import GraphowCLI
from graphow.api.console import EscritorConsole
from graphow.harness.consumo_do_disparo import descrever_disparo, ler_consumo_do_disparo
from graphow.harness.entrada_hook import (
    MODELO_DESCONHECIDO,
    EntradaDeHook,
    ler_entrada_de_hook,
    preparar_fluxos_do_hook,
)
from graphow.harness.retomada import PedidoDeRetomada, montar_vista_de_retomada
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.montagem import ligar_motor_reativo_padrao
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
            "medir-escala": self._executar_medir_escala,
            "notas-gerar": self._executar_notas_gerar,
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

    def _executar_medir_escala(self, argumentos: argparse.Namespace) -> int:
        """Mede o grafo real: peso do canvas, custo de navegar e custo de buscar.

        Corre contra o banco aberto, e nao contra o cenario gravado de
        `graphow avaliar`: as duas medicoes respondem perguntas diferentes.
        """
        from graphow.avaliacao.escala import medir_escala

        for linha in medir_escala(self._kernel).formatar():
            self._console.escrever_linha(linha)
        return CODIGO_SUCESSO

    def _executar_notas_gerar(self, argumentos: argparse.Namespace) -> int:
        """Projeta os aprendizados promovidos num diretorio de notas, ou confere a deriva.

        Mesmo principio de `docs-gerar`: o grafo e a fonte, o acervo e leitura
        regeneravel do zero, e uma nota escrita a mao no diretorio e deriva.
        """
        from graphow.notas import MontadorAcervoDeNotas

        destino = Path(argumentos.destino)
        montador = MontadorAcervoDeNotas(self._kernel.obter_view(argumentos.ramo), destino)
        if argumentos.conferir:
            return self._conferir_acervo(montador.conferir())
        resultado = montador.publicar()
        self._console.escrever_linha(f"{resultado.documentos_escritos} notas geradas em {destino.resolve()}")
        for removido in resultado.documentos_removidos:
            self._console.escrever_linha(f"Removida (aprendizado sem promocao ou nota escrita a mao): {removido}")
        return CODIGO_SUCESSO

    def _conferir_acervo(self, deriva: tuple[str, ...]) -> int:
        """Relata o que diverge do grafo, sem gravar nada."""
        if not deriva:
            self._console.escrever_linha("Acervo em dia com o grafo.")
            return CODIGO_SUCESSO
        self._console.escrever_linha("Acervo desatualizado. Rode 'graphow notas-gerar':")
        for caminho in deriva:
            self._console.escrever_linha(f"  {caminho}")
        return CODIGO_FALHA_DOMINIO

    def _executar_web(self, argumentos: argparse.Namespace) -> int:
        """Inicia o servidor web bloqueante da interface visual."""
        self._cli.iniciar_servidor_web(porta=argumentos.port, host=argumentos.host)
        return CODIGO_SUCESSO

    def _executar_harness(self, argumentos: argparse.Namespace) -> int:
        """Registra o disparo do hook no log e, no início, imprime a vista de retomada."""
        pedido = self._montar_pedido_de_harness(argumentos, self._ler_payload(argumentos))
        if pedido is None:
            self._console.escrever_linha(
                "Harness sem id de sessao: o JSON do hook nao trouxe 'session_id'"
            )
            return CODIGO_FALHA_DOMINIO
        # O hook de fim encerra a Sessao; ligado o motor, o encerramento abre a
        # Task de condensacao no mesmo processo, sem depender do canvas aberto.
        ligar_motor_reativo_padrao(self._kernel)
        recibo = ServicoHarness(self._kernel).registrar(pedido)
        self._console.escrever_linha(f"[{recibo.id_run}] {recibo.mensagem} (versao {recibo.versao_log})")
        if recibo.id_setor:
            self._console.escrever_linha(f"Sessao {pedido.id_sessao} no setor {recibo.id_setor}")
            self._imprimir_vista_de_retomada(pedido, recibo.id_setor)
        return CODIGO_SUCESSO if recibo.sucesso else CODIGO_FALHA_DOMINIO

    def _imprimir_vista_de_retomada(self, pedido: PedidoDeCicloDeVida, id_setor: str) -> None:
        """No início, o que o hook imprime vira contexto do agente: a memória vai junto do recibo.

        Eram três linhas de recibo, e a memória ficava no banco à espera de
        alguém chamar `ler_vista`. Ver harness/retomada.py.
        """
        if pedido.fase != FaseDoHarness.INICIO:
            return
        view = self._kernel.obter_view(pedido.ramo_id)
        retomada = PedidoDeRetomada(view=view, id_sessao=pedido.id_sessao, id_setor=id_setor)
        for linha in montar_vista_de_retomada(retomada):
            self._console.escrever_linha(linha)

    def _ler_payload(self, argumentos: argparse.Namespace) -> EntradaDeHook:
        """Consome a entrada padrão apenas quando o hook foi declarado como origem."""
        if not argumentos.entrada_hook:
            return EntradaDeHook()
        preparar_fluxos_do_hook()
        return ler_entrada_de_hook(sys.stdin)

    def _montar_pedido_de_harness(
        self,
        argumentos: argparse.Namespace,
        entrada: EntradaDeHook,
    ) -> PedidoDeCicloDeVida | None:
        """Funde argumento, payload e transcrição, recusando o disparo sem sessão identificada."""
        id_sessao = argumentos.sessao or entrada.id_sessao
        if not id_sessao:
            return None
        fase = FaseDoHarness(argumentos.fase)
        consumo = ler_consumo_do_disparo(fase, entrada)
        lido = consumo.modelo_principal if consumo is not None else ""
        return PedidoDeCicloDeVida(
            fase=fase,
            id_sessao=id_sessao,
            id_setor=argumentos.setor,
            modelo=self._resolver_modelo(argumentos.modelo, entrada.modelo, lido),
            resumo=argumentos.resumo,
            motivo=entrada.motivo,
            metadados=descrever_disparo(fase, entrada, consumo),
            # O hook diz de onde rodou; fora de um hook, vale a pasta do processo.
            diretorio_de_trabalho=entrada.diretorio or os.getcwd(),
            id_agente=entrada.id_agente if fase == FaseDoHarness.SUBAGENTE else "",
        )

    def _resolver_modelo(self, declarado: str, do_hook: str, lido: str) -> str:
        """A linha de comando vence; depois o payload; depois o modelo que a transcrição mostra.

        O payload do fim não traz o modelo, e o Run gravava "desconhecido" por
        cima do que o início tinha registrado.
        """
        for candidato in (declarado, do_hook, lido):
            if candidato and candidato != MODELO_DESCONHECIDO:
                return candidato
        return MODELO_DESCONHECIDO

    def _executar_mcp(self, argumentos: argparse.Namespace) -> int:
        """Inicia o servidor MCP com a identidade fixada no momento da abertura."""
        from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP, autor_da_conexao
        from graphow.mcp.stdio_server import iniciar_stdio_server

        autor = autor_da_conexao(argumentos.autor, por_conexao=argumentos.autor_por_conexao)
        identidade = IdentidadeSessaoMCP.criar(autor, argumentos.papel)
        iniciar_stdio_server(self._kernel, identidade)
        return CODIGO_SUCESSO
