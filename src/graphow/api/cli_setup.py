"""O subcomando `graphow setup`: o ambiente do Claude Code inteiro num comando só.

Antes o setup eram cinco passos em três guias: `skill-instalar`, duas cópias à
mão, o bloco de hooks colado e as permissões escritas em prosa. Cada passo
esquecido falhava calado. O setup copia skills e subagentes, mescla hooks e
permissões no settings.json quando pedido e imprime o que segue manual, com o
caminho do executável já resolvido.
"""

import argparse
import getpass
import json
from pathlib import Path

from graphow.api.console import EscritorConsole
from graphow.documentacao.ambiente import ConfiguracaoDoAmbiente, resolver_executavel
from graphow.documentacao.instalacao_ambiente import DIRETORIO_CLAUDE_PADRAO, InstaladorDoAmbiente
from graphow.documentacao.settings_claude import MescladorDeSettings

CODIGO_EM_DIA: int = 0
CODIGO_DESATUALIZADO: int = 1
ARQUIVO_DE_SETTINGS: str = "settings.json"
OPCOES_DE_MODO: tuple[tuple[str, str], ...] = (
    ("--escrever-settings", "Mescla hooks e permissoes no settings.json, com copia .graphow.bak do anterior"),
    ("--conferir", "So confere se skills e subagentes instalados estao em dia (sai com 1 se nao estiverem)"),
)


def registrar_comando_de_setup(
    subparsers: argparse._SubParsersAction,
    parser_base: argparse.ArgumentParser,
) -> None:
    """Registra o setup do ambiente, que não toca o banco."""
    parser_setup = subparsers.add_parser(
        "setup",
        parents=[parser_base],
        help="Instala skills e subagentes no Claude Code e mostra (ou mescla) hooks, permissoes e servidor MCP",
    )
    parser_setup.add_argument(
        "--claude-dir",
        default=DIRETORIO_CLAUDE_PADRAO,
        help=f"Diretorio do Claude Code (padrao: {DIRETORIO_CLAUDE_PADRAO})",
    )
    parser_setup.add_argument("--origem", default="", help="Checkout do graphow (padrao: o repositorio do pacote)")
    parser_setup.add_argument(
        "--executavel", default="", help="Executavel graphow que hooks e servidores chamam (padrao: o deste processo)"
    )
    parser_setup.add_argument(
        "--autor", default="", help="Autor do servidor MCP da sessao principal (padrao: usuario do sistema)"
    )
    for opcao, ajuda in OPCOES_DE_MODO:
        parser_setup.add_argument(opcao, action="store_true", help=ajuda)


def executar_setup(argumentos: argparse.Namespace, console: EscritorConsole, raiz_padrao: Path) -> int:
    """Instala ou confere o ambiente e imprime o que segue manual."""
    configuracao = ConfiguracaoDoAmbiente(
        executavel=argumentos.executavel or resolver_executavel(),
        autor=argumentos.autor or getpass.getuser(),
    )
    diretorio_claude = Path(argumentos.claude_dir).expanduser()
    origem = Path(argumentos.origem).expanduser() if argumentos.origem else raiz_padrao
    instalador = InstaladorDoAmbiente(origem, diretorio_claude, configuracao.executavel)
    if argumentos.conferir:
        return _conferir(instalador, console)
    console.escrever_linha(f"Executavel: {configuracao.executavel}")
    resultado = instalador.instalar()
    for nome, quantidade in resultado.arquivos_por_skill:
        console.escrever_linha(f"Skill {nome}: {quantidade} arquivos em {diretorio_claude / 'skills' / nome}")
    console.escrever_linha(f"Subagentes: {len(resultado.agentes)} em {diretorio_claude / 'agents'}")
    _configurar_settings(
        configuracao, diretorio_claude / ARQUIVO_DE_SETTINGS, console, escrever=argumentos.escrever_settings
    )
    _imprimir_passos_manuais(configuracao, console)
    return CODIGO_EM_DIA


def _conferir(instalador: InstaladorDoAmbiente, console: EscritorConsole) -> int:
    """Lista o que falta ou envelheceu; sem nada, diz que está em dia."""
    desatualizados = instalador.desatualizados()
    if not desatualizados:
        console.escrever_linha("Skills e subagentes em dia com o repositorio.")
        return CODIGO_EM_DIA
    for caminho in desatualizados:
        console.escrever_linha(f"Desatualizado: {caminho}")
    console.escrever_linha("Rode 'graphow setup' para atualizar.")
    return CODIGO_DESATUALIZADO


def _configurar_settings(
    configuracao: ConfiguracaoDoAmbiente, caminho: Path, console: EscritorConsole, *, escrever: bool
) -> None:
    """Mescla no settings.json quando pedido; senão, imprime o bloco para colar."""
    if escrever:
        resultado = MescladorDeSettings(caminho, configuracao).mesclar()
        console.escrever_linha(
            f"settings.json: hooks e {len(resultado.permissoes_acrescentadas)} permissoes novas em {resultado.caminho}"
        )
        if resultado.copia is not None:
            console.escrever_linha(f"  copia do anterior: {resultado.copia}")
        return
    console.escrever_linha(f"settings.json nao alterado. Mescle com --escrever-settings, ou cole em {caminho}:")
    console.escrever_linha(json.dumps(configuracao.bloco_do_settings(), indent=2, ensure_ascii=False))


def _imprimir_passos_manuais(configuracao: ConfiguracaoDoAmbiente, console: EscritorConsole) -> None:
    """O que o setup não faz sozinho, porque é do humano decidir."""
    console.escrever_linha("")
    console.escrever_linha("Falta, uma vez por usuario:")
    console.escrever_linha("1. Registrar o servidor MCP da sessao principal (papel humano, so leitura liberada):")
    console.escrever_linha(f"   {configuracao.comando_do_servidor_da_sessao()}")
    console.escrever_linha("2. Gravar a politica de governanca do projeto (graphow web, aba Configuracoes);")
    console.escrever_linha("   sem ela vale a governanca_maxima e o arbitro recusa todo gesto.")
    console.escrever_linha("3. Reiniciar o Claude Code e conferir a linha 'Banco:' que o hook de inicio imprime.")
    console.escrever_linha("Depois de cada 'git pull', rode 'graphow setup' de novo: as copias nao se atualizam sozinhas.")
