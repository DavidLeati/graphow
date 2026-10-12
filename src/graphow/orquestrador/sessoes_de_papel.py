"""A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria.

Cada papel roda numa sessão `claude -p` nova, pela peça da fase 0
(graphow.sessoes): o prompt de papel do pacote por `--append-system-prompt-file`,
o schema por `--json-schema`, sem servidor MCP (`--strict-mcp-config`), sem os
hooks, as skills e os subagentes do usuário (`--setting-sources project`), só
com as ferramentas do papel (`--tools`), com o git de escrita negado
(`--disallowedTools` e a trava no ambiente) e com o que resta do orçamento do
Goal (`--max-budget-usd`). O briefing traz tudo; o agente não lê o grafo.

A saída é conferida contra o schema e contra o sentido. A que não confere
volta à mesma sessão (`--resume`) com a lista de problemas, uma vez; falhando
de novo, o papel falhou. Cada invocação vira uma linha de telemetria, fora do
grafo.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from graphow.orquestrador.briefing import pedido_de_correcao_da_saida
from graphow.orquestrador.esquemas import (
    ESQUEMA_POR_PAPEL,
    PAPEL_EXECUTOR,
    PAPEL_PLANEJADOR,
    PAPEL_VERIFICADOR,
    caminho_do_prompt,
)
from graphow.orquestrador.git_do_goal import regras_que_negam_git
from graphow.orquestrador.validacao_json import validar_contra_esquema
from graphow.sessoes.leitura_stream import LeituraDoStream, ler_stream
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao, em_iso
from graphow.storage.telemetria_de_sessoes import RepositorioTelemetria, SessaoRegistrada

FERRAMENTAS_POR_PAPEL: Mapping[str, tuple[str, ...]] = {
    PAPEL_PLANEJADOR: ("Bash", "Read", "Glob", "Grep"),
    PAPEL_EXECUTOR: ("Bash", "Read", "Edit", "Write", "Glob", "Grep"),
    PAPEL_VERIFICADOR: ("Bash", "Read", "Glob", "Grep"),
}
MODO_DE_PERMISSAO_PADRAO: str = "bypassPermissions"
MODELO_PADRAO: str = "opus"
FONTES_DE_CONFIGURACAO: str = "project"
ORCAMENTO_MINIMO_DA_SESSAO_USD: float = 0.05

Conferencia = Callable[[Mapping[str, Any]], tuple[str, ...]]


@dataclass(frozen=True)
class ConfiguracaoDasSessoes:
    """O que vale para toda sessão de agente do Goal."""

    pasta_das_sessoes: Path
    ambiente_da_trava: Mapping[str, str]
    modelos: Mapping[str, str] = field(default_factory=dict)
    modo_de_permissao: str = MODO_DE_PERMISSAO_PADRAO
    tempo_limite_s: float = 3600.0
    banco_dos_hooks: Path | None = None


@dataclass(frozen=True)
class PedidoDePapel:
    """Uma sessão a rodar: o papel, onde, com que briefing e como conferir a saída."""

    papel: str
    id_goal: str
    pasta: Path
    briefing: str
    conferir: Conferencia
    fatia: str = ""
    tentativa: int = 1
    modelo: str = ""
    orcamento_restante_usd: float = 0.0


@dataclass(frozen=True)
class RespostaDePapel:
    """A saída conferida, ou os problemas que sobraram, e as invocações que rodaram."""

    dados: Mapping[str, Any] | None
    problemas: tuple[str, ...] = ()
    resultados: tuple[ResultadoDeSessao, ...] = ()

    @property
    def valida(self) -> bool:
        """A saída conferiu e pode ser gravada."""
        return self.dados is not None


class SessoesDePapel:
    """Roda as sessões dos papéis e registra cada invocação na telemetria."""

    def __init__(self, executor: ExecutorDeSessao, telemetria: RepositorioTelemetria, configuracao: ConfiguracaoDasSessoes) -> None:
        self._executor: ExecutorDeSessao = executor
        self._telemetria: RepositorioTelemetria = telemetria
        self._configuracao: ConfiguracaoDasSessoes = configuracao

    def modelo_do_papel(self, papel: str) -> str:
        """O modelo configurado para o papel; Opus quando a configuração não diz."""
        return self._configuracao.modelos.get(papel) or MODELO_PADRAO

    def rodar(self, pedido: PedidoDePapel) -> RespostaDePapel:
        """A sessão, e a retomada com os problemas quando a saída não confere."""
        primeira = self._invocar(pedido, pedido.briefing, "")
        dados, problemas = ler_saida(primeira, pedido)
        if not problemas:
            return RespostaDePapel(dados, (), (primeira,))
        if not primeira.session_id or primeira.tempo_esgotado:
            return RespostaDePapel(None, problemas, (primeira,))
        segunda = self._invocar(pedido, pedido_de_correcao_da_saida(problemas), primeira.session_id)
        dados, problemas = ler_saida(segunda, pedido)
        return RespostaDePapel(None if problemas else dados, problemas, (primeira, segunda))

    def _invocar(self, pedido: PedidoDePapel, prompt: str, retomar: str) -> ResultadoDeSessao:
        """Uma invocação de `claude -p`, registrada na telemetria."""
        sufixo = "-retomada" if retomar else ""
        nome = "-".join(parte for parte in (pedido.papel, pedido.fatia, f"t{pedido.tentativa}") if parte) + sufixo
        pedido_de_sessao = PedidoDeSessao(
            prompt=prompt,
            pasta=pedido.pasta,
            arquivo_stream=self._configuracao.pasta_das_sessoes / f"{nome}.jsonl",
            modelo=pedido.modelo or self.modelo_do_papel(pedido.papel),
            modo_de_permissao=self._configuracao.modo_de_permissao,
            retomar=retomar,
            banco_graphow=self._configuracao.banco_dos_hooks,
            tempo_limite_s=self._configuracao.tempo_limite_s,
            argumentos_extras=argumentos_do_papel(pedido.papel, pedido.orcamento_restante_usd),
            ambiente_extra=self._configuracao.ambiente_da_trava,
        )
        resultado = self._executor.rodar(pedido_de_sessao)
        self._telemetria.registrar(registro_da_invocacao(pedido, resultado, retomada=bool(retomar)))
        return resultado


def argumentos_do_papel(papel: str, orcamento_restante_usd: float) -> tuple[str, ...]:
    """O que o comando da sessão leva além do que o pedido de sessão já nomeia; a lista variádica vai por último."""
    return (
        "--append-system-prompt-file", str(caminho_do_prompt(papel)),
        "--json-schema", json.dumps(ESQUEMA_POR_PAPEL[papel], separators=(",", ":")),
        "--strict-mcp-config",
        "--setting-sources", FONTES_DE_CONFIGURACAO,
        "--tools", ",".join(FERRAMENTAS_POR_PAPEL[papel]),
        "--max-budget-usd", f"{max(orcamento_restante_usd, ORCAMENTO_MINIMO_DA_SESSAO_USD):.2f}",
        "--disallowedTools", *regras_que_negam_git(("Bash",)),
    )


def ler_saida(resultado: ResultadoDeSessao, pedido: PedidoDePapel) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]:
    """O JSON da sessão conferido, ou os problemas: o `structured_output`, senão o texto final como JSON."""
    dados = _dados_da_leitura(resultado.leitura)
    if dados is None:
        motivo = resultado.motivo_do_erro or "a sessao nao devolveu JSON"
        return None, (f"sem saida estruturada: {motivo}",)
    problemas = validar_contra_esquema(dados, ESQUEMA_POR_PAPEL[pedido.papel])
    if problemas:
        return None, problemas
    problemas = pedido.conferir(dados)
    return (None, problemas) if problemas else (dados, ())


def _dados_da_leitura(leitura: LeituraDoStream) -> dict[str, Any] | None:
    """O objeto que a sessão devolveu: o `structured_output`, senão o texto final como JSON."""
    resultado = leitura.resultado
    if resultado is None:
        return None
    if isinstance(resultado.saida_estruturada, dict):
        return resultado.saida_estruturada
    return _json_do_texto(resultado.texto)


def saida_conferida_da_telemetria(
    registros: Sequence[SessaoRegistrada], papel: str, problemas: Conferencia
) -> Mapping[str, Any] | None:
    """A saída mais nova do papel, relida do stream gravado, que passa na conferência; None sem nenhuma.

    É o que salva a sessão paga quando o processo caiu entre o fim dela e a
    gravação do que ela devolveu.
    """
    for registro in reversed([registro for registro in registros if registro.papel == papel]):
        caminho = Path(registro.arquivo_stream)
        if not caminho.is_file():
            continue
        with caminho.open(encoding="utf-8", errors="replace") as stream:
            dados = _dados_da_leitura(ler_stream(stream))
        if dados is not None and not problemas(dados):
            return dados
    return None


def _json_do_texto(texto: str) -> dict[str, Any] | None:
    """O objeto JSON do texto final, do primeiro abre-chaves ao último fecha-chaves; None quando não há."""
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim <= inicio:
        return None
    try:
        valor = json.loads(texto[inicio:fim + 1])
    except json.JSONDecodeError:
        return None
    return valor if isinstance(valor, dict) else None


def registro_da_invocacao(pedido: PedidoDePapel, resultado: ResultadoDeSessao, *, retomada: bool) -> SessaoRegistrada:
    """A invocação como linha de telemetria."""
    tokens = resultado.tokens
    return SessaoRegistrada(
        id_goal=pedido.id_goal, papel=pedido.papel, fatia=pedido.fatia, tentativa=pedido.tentativa,
        session_id=resultado.session_id, retomada=retomada, modelo=resultado.leitura.modelo,
        inicio=em_iso(resultado.inicio), fim=em_iso(resultado.fim), duracao_s=resultado.duracao_s,
        custo_usd=resultado.custo_usd, tokens=tokens.em_dicionario() if tokens else None, turnos=resultado.turnos,
        codigo_saida=resultado.codigo_saida, tempo_esgotado=resultado.tempo_esgotado, is_error=resultado.is_error,
        erro=resultado.motivo_do_erro, arquivo_stream=str(resultado.arquivo_stream), comando=resultado.comando,
    )


def resultados_da_telemetria(registros: Sequence[SessaoRegistrada]) -> tuple[ResultadoDeSessao, ...]:
    """As invocações relidas dos streams gravados, como a bancada as mede."""
    resultados: list[ResultadoDeSessao] = []
    for registro in registros:
        caminho = Path(registro.arquivo_stream)
        leitura = LeituraDoStream()
        if caminho.is_file():
            with caminho.open(encoding="utf-8", errors="replace") as stream:
                leitura = ler_stream(stream)
        resultados.append(ResultadoDeSessao(
            comando=registro.comando, arquivo_stream=caminho, inicio=datetime.fromisoformat(registro.inicio),
            fim=datetime.fromisoformat(registro.fim), codigo_saida=registro.codigo_saida,
            tempo_esgotado=registro.tempo_esgotado, leitura=leitura,
        ))
    return tuple(resultados)
