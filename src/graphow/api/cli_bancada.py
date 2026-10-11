"""O subcomando `graphow bancada`: rodar uma arquitetura nas demandas do laboratório.

Não toca o banco do usuário: cada execução ganha um banco próprio, que vira o
`GRAPHOW_DB` das sessões, porque os hooks do graphow instalados no Claude Code
rodam em toda sessão `claude -p` e, sem isso, escreveriam nele.
"""

import argparse
from pathlib import Path
import shlex

from graphow.api.console import EscritorConsole
from graphow.bancada.arquiteturas import RegistroDeArquiteturas, registro_padrao
from graphow.bancada.execucao import ConfiguracaoDaRodada, ExecucaoGravada, rodar_projetos
from graphow.bancada.formatacao import formatar_dinheiro, formatar_inteiro, formatar_minutos
from graphow.bancada.projetos import RAIZ_DA_BANCADA_PADRAO, Bancada
from graphow.bancada.transcricoes import PASTA_DE_PROJETOS_PADRAO
from graphow.sessoes.sessao_claude import ExecutorDeSessao

CODIGO_SUCESSO: int = 0
CODIGO_COM_ERRO: int = 1
TODOS_OS_PROJETOS: str = "todos"
TEMPO_LIMITE_DA_RODADA_MIN: float = 120.0
SEGUNDOS_POR_MINUTO: float = 60.0


def registrar_comando_de_bancada(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra `graphow bancada` e as ações dele."""
    parser_bancada = subparsers.add_parser(
        "bancada",
        parents=[parser_base],
        help="Roda uma arquitetura nas demandas do laboratorio, audita a entrega e compara com a linha de base",
    )
    acoes = parser_bancada.add_subparsers(dest="acao", required=True)
    parser_rodar = acoes.add_parser("rodar", help="Monta a execucao da semente, roda a arquitetura e grava execucao.json")
    parser_rodar.add_argument("--arquitetura", required=True, help="Arquitetura registrada (hoje: enxuta)")
    parser_rodar.add_argument("--projeto", required=True, help="Projeto da bancada, ou 'todos' para os tres em paralelo")
    parser_rodar.add_argument("--saida", required=True, help="Pasta onde criar <arquitetura>-<projeto>-<carimbo>/")
    parser_rodar.add_argument(
        "--tempo-limite", type=float, default=TEMPO_LIMITE_DA_RODADA_MIN, help="Minutos por sessao (padrao: 120)"
    )
    _registrar_opcoes_comuns(parser_rodar)


def _registrar_opcoes_comuns(parser: argparse.ArgumentParser) -> None:
    """De onde ler os dados da bancada e as transcrições das sessões."""
    parser.add_argument("--bancada", default=str(RAIZ_DA_BANCADA_PADRAO), help="Pasta bancada/ (padrao: a do repositorio)")
    parser.add_argument(
        "--transcricoes",
        default=str(PASTA_DE_PROJETOS_PADRAO),
        help=f"Pasta de projetos do Claude Code, de onde os tokens sao lidos (padrao: {PASTA_DE_PROJETOS_PADRAO})",
    )


def executar_bancada(
    argumentos: argparse.Namespace,
    console: EscritorConsole,
    *,
    registro: RegistroDeArquiteturas | None = None,
    sessoes: ExecutorDeSessao | None = None,
) -> int:
    """Executa a ação pedida; o registro e o executor de sessão podem vir de fora, nos testes."""
    return _rodar(argumentos, console, registro=registro or registro_padrao(), sessoes=sessoes)


def _rodar(
    argumentos: argparse.Namespace,
    console: EscritorConsole,
    *,
    registro: RegistroDeArquiteturas,
    sessoes: ExecutorDeSessao | None,
) -> int:
    """Monta e roda as execuções e imprime, de cada uma, o comando da sessão e as métricas."""
    bancada = Bancada(Path(argumentos.bancada).expanduser().resolve())
    nome = argumentos.arquitetura
    registro.criar(nome)
    todos = argumentos.projeto == TODOS_OS_PROJETOS
    projetos = bancada.projetos() if todos else (bancada.projeto(argumentos.projeto),)
    configuracao = ConfiguracaoDaRodada(
        bancada=bancada,
        saida=Path(argumentos.saida).expanduser().resolve(),
        raiz_das_transcricoes=Path(argumentos.transcricoes).expanduser(),
        tempo_limite_s=argumentos.tempo_limite * SEGUNDOS_POR_MINUTO,
    )
    execucoes = rodar_projetos(lambda: registro.criar(nome), projetos, configuracao, sessoes=sessoes or ExecutorDeSessao())
    for execucao in execucoes:
        _imprimir_execucao(execucao, console)
    return CODIGO_SUCESSO if all(_sem_erro(execucao) for execucao in execucoes) else CODIGO_COM_ERRO


def _imprimir_execucao(execucao: ExecucaoGravada, console: EscritorConsole) -> None:
    """A pasta, cada sessão com a linha de comando e as métricas gravadas."""
    registro = execucao.registro
    metricas = registro["metricas"]
    console.escrever_linha(f"Execucao: {execucao.diretorio}")
    for sessao in registro["sessoes"]:
        estado = "erro" if sessao["is_error"] else "ok"
        console.escrever_linha(f"  sessao {sessao['session_id'] or '?'} ({estado}): {shlex.join(sessao['comando'])}")
    console.escrever_linha(
        f"  custo {formatar_dinheiro(metricas['custo_usd'])} | tokens {formatar_inteiro(metricas['tokens'])}"
        f" ({metricas['fonte_dos_tokens']}) | {formatar_minutos(metricas['minutos'])}"
        f" | {metricas['commits']} commits no ramo {registro['entrega']['ramo']}"
    )
    if registro["erro"]:
        console.escrever_linha(f"  {registro['erro']}")


def _sem_erro(execucao: ExecucaoGravada) -> bool:
    """A execução rodou e nenhuma sessão terminou com erro."""
    registro = execucao.registro
    return not registro["erro"] and bool(registro["sessoes"]) and not any(sessao["is_error"] for sessao in registro["sessoes"])
