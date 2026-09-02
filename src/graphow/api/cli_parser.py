"""Construção do analisador de argumentos da linha de comando do Graphow."""

import argparse

from graphow.core.types import PapelAutor
from graphow.harness.servico_harness import FaseDoHarness

DESCRICAO_PROGRAMA: str = "Graphow - Substrato de Grafo Agentico Bilateral"
PAPEIS_ACEITOS_NO_MCP: tuple[str, ...] = (
    PapelAutor.PLANEJADOR.value,
    PapelAutor.EXECUTOR.value,
    PapelAutor.REVISOR.value,
    PapelAutor.HUMANO.value,
)
FASES_ACEITAS_NO_HARNESS: tuple[str, ...] = tuple(fase.value for fase in FaseDoHarness)


def _construir_parser_base() -> argparse.ArgumentParser:
    """Cria o parser com as opções herdadas por todos os subcomandos.

    O padrão é SUPPRESS porque subparsers criados com `parents` reaplicam os
    defaults e sobrescreveriam com None um --db informado antes do subcomando.
    """
    parser_base = argparse.ArgumentParser(add_help=False)
    parser_base.add_argument(
        "--db",
        default=argparse.SUPPRESS,
        help="Caminho do arquivo SQLite. Padrao: diretorio de dados do usuario",
    )
    parser_base.add_argument(
        "--spans",
        default=argparse.SUPPRESS,
        help="Arquivo NDJSON onde gravar os spans GenAI do kernel. Padrao: nao gravar",
    )
    return parser_base


def _registrar_comandos_de_leitura(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra os subcomandos que apenas consultam o estado do grafo."""
    subparsers.add_parser("task-list", parents=[parser_base], help="Lista tarefas")
    subparsers.add_parser("print", parents=[parser_base], help="Imprime o resumo do grafo")
    subparsers.add_parser("banco-info", parents=[parser_base], help="Mostra o caminho resolvido do banco")


def _registrar_comandos_de_mutacao(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra os subcomandos que alteram o estado persistido."""
    subparsers.add_parser("init", parents=[parser_base], help="Inicializa o banco de dados")

    parser_task = subparsers.add_parser("task-create", parents=[parser_base], help="Cria uma nova tarefa")
    parser_task.add_argument("--titulo", required=True, help="Titulo da tarefa")
    parser_task.add_argument("--sessao", required=True, help="ID da sessao")


def _registrar_comandos_de_manutencao(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra os subcomandos que cuidam do banco e da documentação gerada."""
    subparsers.add_parser(
        "reparar-sequencias",
        parents=[parser_base],
        help="Deduplica e renumera sequencias repetidas no log",
    )

    parser_migracao = subparsers.add_parser(
        "migrar-banco",
        parents=[parser_base],
        help="Copia um banco antigo para o diretorio de dados do usuario",
    )
    parser_migracao.add_argument("--origem", required=True, help="Caminho do banco de origem")

    parser_docs = subparsers.add_parser(
        "docs-gerar",
        parents=[parser_base],
        help="Regenera docs/INDEX.md e os dossies a partir do codigo",
    )
    parser_docs.add_argument(
        "--conferir",
        action="store_true",
        help="Nao grava: apenas informa se os documentos estao em dia",
    )


def _registrar_comando_de_avaliacao(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra a medição da métrica que o plano fixa desde a Fase 3.

    Ela vive fora dos comandos de manutenção porque não cuida do banco do
    usuário: monta o próprio cenário gravado e não escreve nada. Ver A-15.
    """
    subparsers.add_parser(
        "avaliar",
        parents=[parser_base],
        help="Mede tokens por tarefa bem-sucedida sobre o corpus gravado",
    )


def _registrar_comandos_de_servidor(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra os subcomandos que iniciam processos de longa duração."""
    parser_web = subparsers.add_parser("web", parents=[parser_base], help="Inicia o servidor Web")
    parser_web.add_argument("--port", type=int, default=8000, help="Porta HTTP (padrao: 8000)")
    parser_web.add_argument("--host", default="127.0.0.1", help="Host HTTP (padrao: 127.0.0.1)")

    _registrar_comando_harness(subparsers, parser_base)

    parser_mcp = subparsers.add_parser("mcp", parents=[parser_base], help="Inicia o servidor MCP stdio")
    parser_mcp.add_argument(
        "--papel",
        required=True,
        choices=PAPEIS_ACEITOS_NO_MCP,
        help="Papel atribuido a esta sessao MCP. Nao pode ser alterado pelo agente",
    )
    parser_mcp.add_argument(
        "--autor",
        default="agente-mcp",
        help="Identificador do autor registrado no log para esta sessao",
    )


def _registrar_comando_harness(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra a porta pela qual os hooks do ambiente escrevem no grafo.

    É um comando curto e não interativo de propósito: ele roda dentro de um hook
    de início e de fim de sessão, e qualquer espera ali atrasaria o agente.
    """
    parser_harness = subparsers.add_parser(
        "harness",
        parents=[parser_base],
        help="Registra inicio, progresso ou fim de uma execucao de agente",
    )
    parser_harness.add_argument(
        "--fase",
        required=True,
        choices=FASES_ACEITAS_NO_HARNESS,
        help="Momento do ciclo de vida comunicado pelo hook",
    )
    _registrar_origem_da_sessao(parser_harness)
    parser_harness.add_argument("--setor", default="", help="ID do Setor que contem a sessao")
    parser_harness.add_argument("--modelo", default="desconhecido", help="Modelo em execucao")
    parser_harness.add_argument("--resumo", default="", help="Resumo do que a sessao produziu")


def _registrar_origem_da_sessao(parser_harness: argparse.ArgumentParser) -> None:
    """Exige que a sessao venha do argumento ou do payload, nunca de lugar nenhum.

    O arquivo de hooks passava `$CLAUDE_SESSION_ID`, variavel que o ambiente nao
    define: `--sessao ""` chegava ao kernel e estourava em vez de recusar. O
    grupo obrigatorio move a recusa para o analisador. Ver defeito V-02.
    """
    origem = parser_harness.add_mutually_exclusive_group(required=True)
    origem.add_argument(
        "--sessao",
        type=_identificador_nao_vazio,
        help="ID da Sessao no grafo",
    )
    origem.add_argument(
        "--entrada-hook",
        action="store_true",
        help="Le 'session_id' e 'model' do JSON que o hook envia na entrada padrao",
    )


def _identificador_nao_vazio(valor: str) -> str:
    """Recusa um identificador em branco antes que ele vire um caminho vazio."""
    limpo = valor.strip()
    if not limpo:
        raise argparse.ArgumentTypeError("identificador vazio; informe um ID de sessao")
    return limpo


def construir_parser() -> argparse.ArgumentParser:
    """Monta o analisador completo com todos os subcomandos registrados."""
    parser_base = _construir_parser_base()
    parser = argparse.ArgumentParser(parents=[parser_base], description=DESCRICAO_PROGRAMA)
    subparsers = parser.add_subparsers(dest="comando")
    _registrar_comandos_de_leitura(subparsers, parser_base)
    _registrar_comandos_de_mutacao(subparsers, parser_base)
    _registrar_comandos_de_manutencao(subparsers, parser_base)
    _registrar_comando_de_avaliacao(subparsers, parser_base)
    _registrar_comandos_de_servidor(subparsers, parser_base)
    return parser
