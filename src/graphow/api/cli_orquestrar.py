"""O subcomando `graphow orquestrar`: rodar um Goal de uma spec ou do gerente, aprovar o plano e ver o status.

`--spec <arquivo.md> --repo <pasta>` cria o Goal da spec e roda; `--goal <id>`
roda ou retoma um Goal que já existe (o do gerente pede `--repo` na primeira
vez). `--aprovar-plano` é o portão do modo supervisionado: aprova pelo mesmo
gesto `aprovar_plano` do humano e segue o laço. `--status` só lê. O estado de
cada Goal (área de trabalho, streams das sessões, patches e a trava do git)
fica em `<pasta do banco>/orquestrar/<goal>/`.

Sai com 0 quando o Goal fecha (ou no status), com 3 quando o laço para num
portão que espera o humano ou o orçamento, e com 1 na falha.
"""

import argparse
from dataclasses import dataclass
import getpass
from pathlib import Path
import sqlite3

from graphow.api.console import EscritorConsole
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador.contexto_do_laco import DependenciasDoLaco, MotivoDaParada, OpcoesDoLaco, Parada
from graphow.orquestrador.esquemas import PAPEIS
from graphow.orquestrador.laco import Orquestrador, PedidoInvalido
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.modelo_do_goal import MODOS
from graphow.orquestrador.sessoes_de_papel import MODELO_PADRAO, MODO_DE_PERMISSAO_PADRAO
from graphow.orquestrador.status import formatar_status
from graphow.sessoes.sessao_claude import ExecutorDeSessao
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria

CODIGO_FECHADO: int = 0
CODIGO_FALHA: int = 1
CODIGO_PARADO: int = 3
SEGUNDOS_POR_MINUTO: float = 60.0
PASTA_DO_ESTADO: str = "orquestrar"


def registrar_comando_de_orquestrar(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra `graphow orquestrar` e as opções dele."""
    parser = subparsers.add_parser(
        "orquestrar",
        parents=[parser_base],
        help="Planeja, executa, verifica e fecha um Goal num laco em codigo, com sessoes claude -p por papel",
    )
    alvo = parser.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--spec", help="Spec em Markdown (pedido, perguntas e respostas): cria o Goal e roda")
    alvo.add_argument("--goal", help="ID de um Goal que ja existe (do gerente ou de uma chamada anterior): roda ou retoma")
    acao = parser.add_mutually_exclusive_group()
    acao.add_argument("--status", action="store_true", help="So mostra onde o Goal esta e quanto as sessoes custaram")
    acao.add_argument("--aprovar-plano", action="store_true", help="Aprova o plano (gesto aprovar_plano do humano) e segue")
    parser.add_argument("--repo", default="", help="Repositorio git do trabalho (padrao: o diretorio atual)")
    parser.add_argument("--modo", choices=MODOS, default=None, help="supervisionado (padrao) ou autonomo; fica gravado no Goal")
    parser.add_argument("--ramo", default="", help="Branch do Goal (padrao: graphow/<slug>)")
    parser.add_argument("--base", default="", help="Branch base (padrao: a branch atual do repositorio)")
    parser.add_argument("--orcamento-usd", type=float, default=None, help="Teto de custo do Goal em dolares (padrao: 30)")
    parser.add_argument("--area", default="", help="Pasta do worktree do Goal (padrao: na pasta de estado do Goal)")
    for papel in PAPEIS:
        parser.add_argument(f"--modelo-{papel}", default=MODELO_PADRAO, help=f"Modelo do {papel} (padrao: {MODELO_PADRAO})")
    parser.add_argument("--permissao", default=MODO_DE_PERMISSAO_PADRAO, help="Modo de permissao das sessoes (padrao: bypassPermissions)")
    parser.add_argument("--tempo-limite", type=float, default=60.0, help="Minutos por sessao de agente (padrao: 60)")
    parser.add_argument("--tempo-limite-suite", type=float, default=30.0, help="Minutos para a suite do projeto (padrao: 30)")
    parser.add_argument("--autor", default="", help="Quem aprova o plano (padrao: o usuario do sistema)")


@dataclass(frozen=True)
class AmbienteDoOrquestrar:
    """O que a CLI já abriu: o kernel, a conexão do banco, o console e onde o banco mora."""

    kernel: WriteKernel
    conexao: sqlite3.Connection
    console: EscritorConsole
    pasta_do_banco: Path
    executor: ExecutorDeSessao | None = None


def executar_orquestrar(argumentos: argparse.Namespace, ambiente: AmbienteDoOrquestrar) -> int:
    """Executa a ação pedida e devolve o código de saída."""
    telemetria = RepositorioTelemetria(ambiente.conexao)
    if argumentos.status:
        return _status(argumentos, ambiente, telemetria)
    orquestrador = Orquestrador(_dependencias(argumentos, ambiente, telemetria))
    opcoes = _opcoes(argumentos)
    repositorio = Path(argumentos.repo).expanduser() if argumentos.repo else Path.cwd()
    try:
        if argumentos.aprovar_plano:
            _exigir_goal(argumentos)
            ambiente.console.escrever_linha(orquestrador.aprovar_plano(argumentos.goal, argumentos.autor or getpass.getuser()))
        if argumentos.spec:
            parada = orquestrador.iniciar_da_spec(Path(argumentos.spec).expanduser(), repositorio, opcoes)
        else:
            parada = orquestrador.rodar(argumentos.goal, opcoes, repositorio if argumentos.repo else None)
    except PedidoInvalido as erro:
        ambiente.console.escrever_linha(erro.formatar_para_llm())
        return CODIGO_FALHA
    return _relatar(parada, ambiente, telemetria)


def _dependencias(argumentos: argparse.Namespace, ambiente: AmbienteDoOrquestrar, telemetria: RepositorioTelemetria) -> DependenciasDoLaco:
    """As dependências do laço a partir das opções da chamada."""
    return DependenciasDoLaco(
        kernel=ambiente.kernel,
        executor=ambiente.executor or ExecutorDeSessao(),
        telemetria=telemetria,
        pasta_de_estado=ambiente.pasta_do_banco / PASTA_DO_ESTADO,
        modelos={papel: getattr(argumentos, f"modelo_{papel}") for papel in PAPEIS},
        modo_de_permissao=argumentos.permissao,
        tempo_limite_da_sessao_s=argumentos.tempo_limite * SEGUNDOS_POR_MINUTO,
    )


def _opcoes(argumentos: argparse.Namespace) -> OpcoesDoLaco:
    """O que a chamada pede para o laço."""
    return OpcoesDoLaco(
        modo=argumentos.modo,
        ramo=argumentos.ramo,
        base=argumentos.base,
        orcamento_usd=argumentos.orcamento_usd,
        area=Path(argumentos.area).expanduser() if argumentos.area else None,
        tempo_limite_da_suite_s=argumentos.tempo_limite_suite * SEGUNDOS_POR_MINUTO,
    )


def _exigir_goal(argumentos: argparse.Namespace) -> None:
    """`--status` e `--aprovar-plano` falam de um Goal que já existe."""
    if not argumentos.goal:
        raise PedidoInvalido("esta acao pede --goal <id>", {})


def _status(argumentos: argparse.Namespace, ambiente: AmbienteDoOrquestrar, telemetria: RepositorioTelemetria) -> int:
    """Imprime o status do Goal."""
    if not argumentos.goal:
        ambiente.console.escrever_linha("ERRO: --status pede --goal <id>")
        return CODIGO_FALHA
    estado = ler_estado(ambiente.kernel.obter_view(), argumentos.goal)
    if estado is None:
        ambiente.console.escrever_linha(f"ERRO: Goal '{argumentos.goal}' nao encontrado")
        return CODIGO_FALHA
    for linha in formatar_status(estado, telemetria.listar(argumentos.goal)):
        ambiente.console.escrever_linha(linha)
    return CODIGO_FECHADO


def _relatar(parada: Parada, ambiente: AmbienteDoOrquestrar, telemetria: RepositorioTelemetria) -> int:
    """A parada e o status do Goal; o código diz se fechou, parou num portão ou falhou."""
    ambiente.console.escrever_linha(f"Parada: {parada.motivo.value}")
    ambiente.console.escrever_linha(parada.mensagem)
    estado = ler_estado(ambiente.kernel.obter_view(), parada.id_goal)
    if estado is not None:
        for linha in formatar_status(estado, telemetria.listar(parada.id_goal)):
            ambiente.console.escrever_linha(linha)
    if parada.fechou:
        return CODIGO_FECHADO
    return CODIGO_FALHA if parada.motivo == MotivoDaParada.FALHA else CODIGO_PARADO
