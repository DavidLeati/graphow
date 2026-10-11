"""O subcomando `graphow bancada`: rodar uma arquitetura nas demandas do laboratório, auditar e comparar.

Não toca o banco do usuário: cada execução ganha um banco próprio, que vira o
`GRAPHOW_DB` das sessões, porque os hooks do graphow instalados no Claude Code
rodam em toda sessão `claude -p` e, sem isso, escreveriam nele.
"""

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import shlex

from graphow.api.console import EscritorConsole
from graphow.bancada.arquiteturas import RegistroDeArquiteturas, registro_padrao
from graphow.bancada.auditoria import auditar, pedido_do_auditor
from graphow.bancada.execucao import ConfiguracaoDaRodada, ExecucaoGravada, rodar_projetos
from graphow.bancada.formatacao import formatar_dinheiro, formatar_inteiro, formatar_minutos
from graphow.bancada.laboratorio import Laboratorio, formatar_conferencias
from graphow.bancada.placar import formatar_placar, ler_execucoes, ler_linha_de_base
from graphow.bancada.projetos import RAIZ_DA_BANCADA_PADRAO, Bancada
from graphow.bancada.transcricoes import PASTA_DE_PROJETOS_PADRAO
from graphow.sessoes.sessao_claude import ExecutorDeSessao

CODIGO_SUCESSO: int = 0
CODIGO_COM_ERRO: int = 1
TODOS_OS_PROJETOS: str = "todos"
TEMPO_LIMITE_DA_RODADA_MIN: float = 120.0
TEMPO_LIMITE_DO_AUDITOR_MIN: float = 60.0
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
    _registrar_rodar(acoes)
    _registrar_auditar(acoes)
    parser_placar = acoes.add_parser("placar", help="Compara as execucoes de uma saida com a linha de base")
    parser_placar.add_argument("--saida", required=True, help="Pasta com as execucoes (ou uma execucao)")
    parser_placar.add_argument("--bancada", default=str(RAIZ_DA_BANCADA_PADRAO), help="Pasta bancada/ (padrao: a do repositorio)")
    parser_laboratorio = acoes.add_parser(
        "medir-laboratorio", help="Mede de novo, dos logs do laboratorio, cada numero da linha de base e confere"
    )
    parser_laboratorio.add_argument(
        "--laboratorio", required=True, help="Pasta do laboratorio, com _runs/, b/_runs/ e os repositorios das entregas"
    )
    _registrar_opcoes_comuns(parser_laboratorio)


def _registrar_rodar(acoes: argparse._SubParsersAction) -> None:
    """`graphow bancada rodar`."""
    parser_rodar = acoes.add_parser("rodar", help="Monta a execucao da semente, roda a arquitetura e grava execucao.json")
    parser_rodar.add_argument("--arquitetura", required=True, help="Arquitetura registrada (hoje: enxuta)")
    parser_rodar.add_argument("--projeto", required=True, help="Projeto da bancada, ou 'todos' para os tres em paralelo")
    parser_rodar.add_argument("--saida", required=True, help="Pasta onde criar <arquitetura>-<projeto>-<carimbo>/")
    parser_rodar.add_argument(
        "--tempo-limite", type=float, default=TEMPO_LIMITE_DA_RODADA_MIN, help="Minutos por sessao (padrao: 120)"
    )
    _registrar_opcoes_comuns(parser_rodar)


def _registrar_auditar(acoes: argparse._SubParsersAction) -> None:
    """`graphow bancada auditar`."""
    parser_auditar = acoes.add_parser("auditar", help="Roda o auditor sobre uma execucao e grava auditoria.json com o PLACAR")
    parser_auditar.add_argument("--execucao", required=True, help="Pasta de uma execucao, com execucao.json")
    parser_auditar.add_argument(
        "--tempo-limite", type=float, default=TEMPO_LIMITE_DO_AUDITOR_MIN, help="Minutos para o auditor (padrao: 60)"
    )
    parser_auditar.add_argument(
        "--refazer",
        action="store_true",
        help="Audita de novo uma execucao ja auditada; a auditoria anterior fica guardada como auditoria-anterior-N",
    )
    _registrar_opcoes_comuns(parser_auditar)


@dataclass(frozen=True)
class _Dependencias:
    """O registro de arquiteturas e o executor de sessão; o executor só nasce quando uma ação roda sessão."""

    registro: RegistroDeArquiteturas
    sessoes: ExecutorDeSessao | None

    def executor(self) -> ExecutorDeSessao:
        """O executor injetado, ou o que acha o claude em GRAPHOW_CLAUDE ou no PATH."""
        return self.sessoes or ExecutorDeSessao()


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
    acoes: Mapping[str, Callable[[argparse.Namespace, EscritorConsole, _Dependencias], int]] = {
        "rodar": _rodar,
        "auditar": _auditar,
        "placar": _placar,
        "medir-laboratorio": _medir_laboratorio,
    }
    return acoes[argumentos.acao](argumentos, console, _Dependencias(registro or registro_padrao(), sessoes))


def _rodar(argumentos: argparse.Namespace, console: EscritorConsole, dependencias: _Dependencias) -> int:
    """Monta e roda as execuções e imprime, de cada uma, o comando da sessão e as métricas."""
    bancada = _bancada(argumentos)
    nome, registro = argumentos.arquitetura, dependencias.registro
    registro.criar(nome)
    todos = argumentos.projeto == TODOS_OS_PROJETOS
    projetos = bancada.projetos() if todos else (bancada.projeto(argumentos.projeto),)
    configuracao = ConfiguracaoDaRodada(
        bancada=bancada,
        saida=Path(argumentos.saida).expanduser().resolve(),
        raiz_das_transcricoes=Path(argumentos.transcricoes).expanduser(),
        tempo_limite_s=argumentos.tempo_limite * SEGUNDOS_POR_MINUTO,
    )
    execucoes = rodar_projetos(lambda: registro.criar(nome), projetos, configuracao, sessoes=dependencias.executor())
    for execucao in execucoes:
        _imprimir_execucao(execucao, console)
    return CODIGO_SUCESSO if all(_sem_erro(execucao) for execucao in execucoes) else CODIGO_COM_ERRO


def _auditar(argumentos: argparse.Namespace, console: EscritorConsole, dependencias: _Dependencias) -> int:
    """Roda o auditor sobre a execução e imprime o placar extraído."""
    execucao = Path(argumentos.execucao).expanduser().resolve()
    pedido = pedido_do_auditor(execucao, _bancada(argumentos), argumentos.tempo_limite * SEGUNDOS_POR_MINUTO)
    sessoes = dependencias.executor()
    console.escrever_linha(f"Auditor em {execucao}: {shlex.join(sessoes.comando_de(pedido))}")
    registro = auditar(
        execucao, pedido, sessoes, transcricoes=Path(argumentos.transcricoes).expanduser(), refazer=argumentos.refazer
    )
    if registro["auditoria_anterior"]:
        console.escrever_linha(f"  auditoria anterior guardada como {registro['auditoria_anterior']}")
    placar = registro["placar"]
    linha = placar["linha"] if placar else "sem PLACAR"
    console.escrever_linha(f"  {linha}")
    console.escrever_linha(
        f"  auditoria.json gravado | custo do auditor {formatar_dinheiro(registro['metricas']['custo_usd'])}"
        f" | {formatar_minutos(registro['metricas']['minutos'])}"
    )
    if registro["erro"]:
        console.escrever_linha(f"  {registro['erro']}")
    return CODIGO_COM_ERRO if registro["erro"] else CODIGO_SUCESSO


def _placar(argumentos: argparse.Namespace, console: EscritorConsole, dependencias: _Dependencias) -> int:
    """A tabela das execuções da saída contra a linha de base; não roda sessão nenhuma."""
    saida = Path(argumentos.saida).expanduser().resolve()
    bancada = _bancada(argumentos)
    execucoes = ler_execucoes(saida)
    auditadas = sum(1 for execucao in execucoes if execucao.numeros.atende is not None)
    falhas = sum(1 for execucao in execucoes if execucao.falhou)
    console.escrever_linha(
        f"Placar de {saida}: {len(execucoes)} execucoes, {auditadas} auditadas, {falhas} com falha; base {bancada.linha_de_base}"
    )
    console.escrever_linha("")
    for linha in formatar_placar(execucoes, ler_linha_de_base(bancada.linha_de_base)):
        console.escrever_linha(linha)
    return CODIGO_SUCESSO


def _medir_laboratorio(argumentos: argparse.Namespace, console: EscritorConsole, dependencias: _Dependencias) -> int:
    """A conferência da linha de base contra os logs; sai com 1 se algum número divergir. Não roda sessão."""
    laboratorio = Path(argumentos.laboratorio).expanduser().resolve()
    bancada = _bancada(argumentos)
    conferencias = Laboratorio(laboratorio, bancada, Path(argumentos.transcricoes).expanduser()).conferir()
    console.escrever_linha(f"Linha de base {bancada.linha_de_base} medida de novo dos logs de {laboratorio}")
    console.escrever_linha("")
    for linha in formatar_conferencias(conferencias):
        console.escrever_linha(linha)
    return CODIGO_COM_ERRO if any(conferencia.divergencias for conferencia in conferencias) else CODIGO_SUCESSO


def _bancada(argumentos: argparse.Namespace) -> Bancada:
    """A pasta bancada/ pedida, em caminho absoluto."""
    return Bancada(Path(argumentos.bancada).expanduser().resolve())


def _imprimir_execucao(execucao: ExecucaoGravada, console: EscritorConsole) -> None:
    """A pasta, cada sessão com a linha de comando e as métricas gravadas."""
    registro = execucao.registro
    metricas = registro["metricas"]
    ramo = registro["entrega"]["ramo"] if registro["entrega"] else "?"
    console.escrever_linha(f"Execucao: {execucao.diretorio}")
    for sessao in registro["sessoes"]:
        estado = "erro" if sessao["is_error"] else "ok"
        console.escrever_linha(f"  sessao {sessao['session_id'] or '?'} ({estado}): {shlex.join(sessao['comando'])}")
    console.escrever_linha(
        f"  custo {formatar_dinheiro(metricas['custo_usd'])} | tokens {formatar_inteiro(metricas['tokens'])}"
        f" ({metricas['fonte_dos_tokens'] or '-'}) | {formatar_minutos(metricas['minutos'])}"
        f" | {formatar_inteiro(metricas['commits'])} commits no ramo {ramo}"
    )
    if registro["erro"]:
        console.escrever_linha(f"  {registro['erro']}")


def _sem_erro(execucao: ExecucaoGravada) -> bool:
    """A execução rodou e nenhuma sessão terminou com erro."""
    registro = execucao.registro
    return not registro["erro"] and bool(registro["sessoes"]) and not any(sessao["is_error"] for sessao in registro["sessoes"])
