"""Interface de Linha de Comando (CLI) para operação do Graphow."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import sys
from typing import Any
import uuid

from graphow.api.console import EscritorConsole, EscritorConsolePadrao
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.lineage.lineage_tracer import LineageTracer
from graphow.projection.graph_view import GrafoView
from graphow.storage.localizador_banco import LocalizacaoBanco


@dataclass(frozen=True)
class ResumoTask:
    """Projeção imutável de uma tarefa para exibição na linha de comando."""

    id: str
    rotulo: str
    status: str


class GraphowCLI:
    """Implementação dos comandos de terminal da CLI Graphow."""

    def __init__(self, kernel: WriteKernel, console: EscritorConsole | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._console: EscritorConsole = console or EscritorConsolePadrao()

    def criar_task(self, titulo: str, id_sessao: str, autor: str = "david") -> str:
        """Cria uma nova Task vinculada à Sessão e devolve o identificador gerado."""
        id_task = f"task-{uuid.uuid4()}"
        operacoes = self._montar_operacoes_criacao_task(id_task, titulo, id_sessao)
        dados = DadosPropostaPatch(
            autor=autor,
            papel=PapelAutor.HUMANO,
            operacoes=operacoes,
            justificativa=f"Criacao da task: {titulo}",
        )
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        if not recibo.sucesso:
            raise RuntimeError(f"Erro ao criar task: {recibo.mensagem}")
        return id_task

    def _montar_operacoes_criacao_task(
        self,
        id_task: str,
        titulo: str,
        id_sessao: str,
    ) -> tuple[ItemPatch, ...]:
        """Monta o par de operações que cria a Task e a liga à Sessão de origem."""
        payload_task: dict[str, Any] = {
            "id": id_task,
            "tipo": TipoNo.TASK.value,
            "rotulo": titulo,
            "propriedades": {"status": "pendente"},
        }
        id_aresta = f"prod-{id_task}"
        payload_aresta: dict[str, Any] = {
            "id": id_aresta,
            "origem_id": id_sessao,
            "destino_id": id_task,
            "tipo": TipoAresta.PRODUZ.value,
        }
        return (
            ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_task}", value=payload_task),
            ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=payload_aresta),
        )

    def listar_tasks(self, ramo_id: str = "main") -> tuple[ResumoTask, ...]:
        """Consulta as tarefas existentes no ramo sem alterar estado algum."""
        view = self._kernel.obter_view(ramo_id)
        tarefas = view.listar_nos_por_tipo(TipoNo.TASK)
        return tuple(
            ResumoTask(id=tarefa.id, rotulo=tarefa.rotulo, status=str(tarefa.obter_propriedade("status", "pendente")))
            for tarefa in tarefas
        )

    def montar_sumario_grafo(self, ramo_id: str = "main") -> str:
        """Retorna sumário textual legível do estado do grafo."""
        view = self._kernel.obter_view(ramo_id)
        cabecalho = f"=== GRAFO GRAPHOW (Ramo: {ramo_id} | Versao Log: {view.versao_log}) ==="
        linhas = [cabecalho, f"Nos ({view.total_nos}):"]
        linhas.extend(self._formatar_linhas_de_nos(view))
        linhas.append(f"\nArestas ({view.total_arestas}):")
        linhas.extend(self._formatar_linhas_de_arestas(view))
        return "\n".join(linhas)

    def _formatar_linhas_de_nos(self, view: GrafoView) -> tuple[str, ...]:
        """Formata cada nó da projeção em uma linha legível."""
        return tuple(f"  - [{no.tipo.value}] {no.rotulo} (id: {no.id})" for no in view.listar_todos_os_nos())

    def _formatar_linhas_de_arestas(self, view: GrafoView) -> tuple[str, ...]:
        """Formata cada aresta da projeção em uma linha legível."""
        return tuple(
            f"  - ({aresta.origem_id}) --[{aresta.tipo.value}]--> ({aresta.destino_id})"
            for aresta in view.listar_todas_as_arestas()
        )

    def rastrear_linhagem(self, id_no: str, ramo_id: str = "main") -> tuple[str, ...]:
        """Rastreia os passos causais do nó até o Goal raiz."""
        view = self._kernel.obter_view(ramo_id)
        caminho = LineageTracer().rastrear_linhagem(id_no, view)
        return tuple(caminho.passos)

    def iniciar_servidor_web(self, porta: int = 8000, host: str = "127.0.0.1") -> None:
        """Inicia o servidor web da interface visual interativa."""
        from graphow.web.server import EnderecoServidor, GraphowWebServer

        servidor = GraphowWebServer(self._kernel, EnderecoServidor(host=host, porta=porta))
        self._console.escrever_linha(f"Servidor Web Graphow iniciado em http://{host}:{porta}")
        self._console.escrever_linha("Pressione Ctrl+C para encerrar.")
        try:
            servidor.iniciar(bloqueante=True)
        except KeyboardInterrupt:
            self._console.escrever_linha("Encerrando servidor Web...")
            servidor.parar()


def main(argumentos: Sequence[str] | None = None) -> int:
    """Ponto de entrada principal da linha de comando."""
    from graphow.api.cli_execucao import ExecutorLinhaDeComando
    from graphow.api.cli_parser import construir_parser

    parser: argparse.ArgumentParser = construir_parser()
    parsed = parser.parse_args(list(argumentos if argumentos is not None else sys.argv[1:]))
    if parsed.comando is None:
        parser.print_help()
        return 0
    return ExecutorLinhaDeComando().executar(parsed)


def descrever_localizacao_banco(localizacao: LocalizacaoBanco) -> tuple[str, ...]:
    """Monta as linhas de diagnóstico sobre onde o banco de eventos reside."""
    linhas = [
        f"Banco de eventos: {localizacao.caminho_absoluto_texto}",
        f"Origem do caminho: {localizacao.origem.value}",
    ]
    if localizacao.esta_em_pasta_sincronizada:
        linhas.append(
            "AVISO: este caminho esta em uma pasta sincronizada por nuvem. "
            "O arquivo -wal pode dessincronizar do .db e causar perda de eventos. "
            "Use 'graphow migrar-banco --origem <caminho>' para mover o banco."
        )
    return tuple(linhas)


if __name__ == "__main__":
    sys.exit(main())
