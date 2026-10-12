"""A sessão de cada papel: o pedido com o prompt e o schema, a saída conferida e a telemetria.

Cada papel roda numa sessão `claude -p` nova, pela peça da fase 0
(graphow.sessoes): o prompt de papel do pacote por `--append-system-prompt-file`,
o schema por `--json-schema`, sem servidor MCP (`--strict-mcp-config`), sem os
hooks, as skills e os subagentes do usuário (`--setting-sources project`), só
com as ferramentas do papel (`--tools`), com o git de escrita negado
(`--disallowedTools` e a trava no ambiente) e com o que resta do orçamento do
Goal (`--max-budget-usd`). O briefing traz tudo; o agente não lê o grafo.
Antes da sessão o clone do Goal é fotografado e, depois dela, volta a ser o
que era: o que o agente mexeu no git do clone é desfeito e vai na resposta
como observação (orquestrador/trava_do_git.py). Nada fora do clone é tocado.

A saída é conferida contra o schema e contra o sentido e, no papel que declara
os comandos que rodou (o verificador), contra as chamadas Bash do stream da
sessão (orquestrador/comandos_do_stream.py). A que não confere volta à mesma
sessão (`--resume`) com a lista de problemas, uma vez; falhando de novo, o
papel falhou. Cada invocação vira uma linha de telemetria, fora do
grafo, que nasce `em_andamento` antes de a sessão abrir e fecha com o
resultado; o stream de cada invocação tem nome próprio, e a refeita não
apaga o da anterior. A linha que ficou em andamento porque o orquestrador
caiu é recuperada do stream na chamada seguinte.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
import json
from pathlib import Path
import secrets
from typing import Any

from graphow.orquestrador.briefing import pedido_de_correcao_da_saida
from graphow.orquestrador.comandos_do_stream import comandos_nao_rodados, problema_dos_comandos
from graphow.orquestrador.esquemas import (
    ESQUEMA_POR_PAPEL,
    PAPEL_AUTOR_DE_ACEITE,
    PAPEL_EXECUTOR,
    PAPEL_PLANEJADOR,
    PAPEL_REVISOR,
    PAPEL_VERIFICADOR,
    caminho_do_prompt,
)
from graphow.orquestrador.trava_do_git import fotografar_clone, regras_que_negam_git, restaurar_o_clone
from graphow.orquestrador.validacao_json import validar_contra_esquema
from graphow.sessoes.leitura_stream import LeituraDoStream, ler_stream
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao, em_iso
from graphow.storage.telemetria_de_sessoes import (
    ESTADO_CONCLUIDA,
    ESTADO_EM_ANDAMENTO,
    ESTADO_RECUPERADA,
    RepositorioTelemetria,
    SessaoRegistrada,
)

FERRAMENTAS_POR_PAPEL: Mapping[str, tuple[str, ...]] = {
    PAPEL_PLANEJADOR: ("Bash", "Read", "Glob", "Grep"),
    PAPEL_AUTOR_DE_ACEITE: ("Bash", "Read", "Edit", "Write", "Glob", "Grep"),
    PAPEL_EXECUTOR: ("Bash", "Read", "Edit", "Write", "Glob", "Grep"),
    PAPEL_REVISOR: ("Bash", "Read", "Glob", "Grep"),
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
    comandos_declarados: Callable[[Mapping[str, Any]], Sequence[str]] | None = None


@dataclass(frozen=True)
class RespostaDePapel:
    """A saída conferida, ou os problemas que sobraram, e as invocações que rodaram."""

    dados: Mapping[str, Any] | None
    problemas: tuple[str, ...] = ()
    resultados: tuple[ResultadoDeSessao, ...] = ()
    desfeito: str = ""


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
        """A sessão conferida, e o clone deixado como estava antes dela; o que foi desfeito vai na resposta."""
        foto = fotografar_clone(pedido.pasta)
        resposta = self._rodar_e_conferir(pedido)
        return replace(resposta, desfeito=restaurar_o_clone(foto))

    def _rodar_e_conferir(self, pedido: PedidoDePapel) -> RespostaDePapel:
        """A sessão, e a retomada com os problemas quando a saída não confere."""
        primeira = self._invocar(pedido, pedido.briefing, "")
        dados, problemas = _conferida(pedido, (primeira,))
        if not problemas:
            return RespostaDePapel(dados, (), (primeira,))
        if not primeira.session_id or primeira.tempo_esgotado:
            return RespostaDePapel(None, problemas, (primeira,))
        segunda = self._invocar(pedido, pedido_de_correcao_da_saida(problemas), primeira.session_id)
        dados, problemas = _conferida(pedido, (primeira, segunda))
        return RespostaDePapel(None if problemas else dados, problemas, (primeira, segunda))

    def _invocar(self, pedido: PedidoDePapel, prompt: str, retomar: str) -> ResultadoDeSessao:
        """Uma invocação de `claude -p`: a linha de telemetria nasce em andamento e fecha com o resultado."""
        sufixo = "-retomada" if retomar else ""
        nome = "-".join(parte for parte in (pedido.papel, pedido.fatia, f"t{pedido.tentativa}") if parte) + sufixo
        arquivo = self._configuracao.pasta_das_sessoes / f"{nome}-{_marca_da_invocacao()}.jsonl"
        modelo = pedido.modelo or self.modelo_do_papel(pedido.papel)
        pedido_de_sessao = PedidoDeSessao(
            prompt=prompt,
            pasta=pedido.pasta,
            arquivo_stream=arquivo,
            modelo=modelo,
            modo_de_permissao=self._configuracao.modo_de_permissao,
            retomar=retomar,
            banco_graphow=self._configuracao.banco_dos_hooks,
            tempo_limite_s=self._configuracao.tempo_limite_s,
            argumentos_extras=argumentos_do_papel(pedido.papel, pedido.orcamento_restante_usd),
            ambiente_extra=self._configuracao.ambiente_da_trava,
        )
        aberta = registro_em_andamento(pedido, arquivo, retomar=retomar, modelo=modelo)
        id_linha = self._telemetria.registrar(aberta)
        resultado = self._executor.rodar(pedido_de_sessao)
        self._telemetria.atualizar(id_linha, com_o_resultado(aberta, resultado))
        return resultado


def _conferida(pedido: PedidoDePapel, resultados: Sequence[ResultadoDeSessao]) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]:
    """A saída da última invocação conferida e, quando o papel declara comandos, conferida contra o stream da sessão."""
    dados, problemas = ler_saida(resultados[-1], pedido)
    if dados is None or pedido.comandos_declarados is None:
        return dados, problemas
    faltando = problema_dos_comandos(comandos_nao_rodados(pedido.comandos_declarados(dados), resultados))
    return (None, faltando) if faltando else (dados, ())


def _marca_da_invocacao() -> str:
    """O instante e um sufixo aleatório: a invocação refeita não sobrescreve o stream da anterior."""
    return f"{datetime.now():%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"


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


def registro_em_andamento(pedido: PedidoDePapel, arquivo: Path, *, retomar: str, modelo: str) -> SessaoRegistrada:
    """A linha da invocação antes de a sessão abrir: quem, onde e desde quando."""
    return SessaoRegistrada(
        id_goal=pedido.id_goal, papel=pedido.papel, fatia=pedido.fatia, tentativa=pedido.tentativa,
        session_id=retomar, retomada=bool(retomar), modelo=modelo, inicio=em_iso(datetime.now().astimezone()),
        arquivo_stream=str(arquivo), estado=ESTADO_EM_ANDAMENTO,
    )


def com_o_resultado(aberta: SessaoRegistrada, resultado: ResultadoDeSessao) -> SessaoRegistrada:
    """A linha da invocação com o fim dela; a sessão retomada que morreu sem dizer o id fica com o id retomado."""
    tokens = resultado.tokens
    return replace(
        aberta, session_id=resultado.session_id or aberta.session_id, modelo=resultado.leitura.modelo or aberta.modelo,
        inicio=em_iso(resultado.inicio), fim=em_iso(resultado.fim), duracao_s=resultado.duracao_s,
        custo_usd=resultado.custo_usd, tokens=tokens.em_dicionario() if tokens else None, turnos=resultado.turnos,
        codigo_saida=resultado.codigo_saida, tempo_esgotado=resultado.tempo_esgotado, is_error=resultado.is_error,
        erro=resultado.motivo_do_erro, arquivo_stream=str(resultado.arquivo_stream), comando=resultado.comando,
        estado=ESTADO_CONCLUIDA,
    )


def recuperar_sessoes_em_andamento(telemetria: RepositorioTelemetria, id_goal: str) -> int:
    """As linhas que ficaram em andamento porque o orquestrador caiu; devolve quantas recuperou.

    A invocação cujo stream chegou ao `result` ganha o custo, os tokens e o id
    dele; a que não chegou fica em andamento, com o custo desconhecido.
    """
    recuperadas = 0
    for registro in telemetria.listar(id_goal):
        relido = _relido(registro) if registro.estado == ESTADO_EM_ANDAMENTO else None
        if relido is not None and relido.leitura.resultado is not None:
            erro = "recuperada do stream: o orquestrador parou antes de registrar o fim"
            linha = replace(com_o_resultado(registro, relido), estado=ESTADO_RECUPERADA, codigo_saida=None,
                            is_error=relido.leitura.resultado.is_error, erro=erro)
            telemetria.atualizar(registro.id_linha, linha)
            recuperadas += 1
    return recuperadas


def _relido(registro: SessaoRegistrada) -> ResultadoDeSessao:
    """A invocação relida do stream gravado; sem fim registrado, o fim é a última escrita do stream."""
    caminho = Path(registro.arquivo_stream)
    leitura = LeituraDoStream()
    inicio = registro.inicio or em_iso(datetime.now().astimezone())
    fim = registro.fim or inicio
    if caminho.is_file():
        with caminho.open(encoding="utf-8", errors="replace") as stream:
            leitura = ler_stream(stream)
        fim = registro.fim or em_iso(datetime.fromtimestamp(caminho.stat().st_mtime).astimezone())
    return ResultadoDeSessao(
        comando=registro.comando, arquivo_stream=caminho, inicio=datetime.fromisoformat(inicio),
        fim=datetime.fromisoformat(fim), codigo_saida=registro.codigo_saida, tempo_esgotado=registro.tempo_esgotado,
        leitura=leitura,
    )


def resultados_da_telemetria(registros: Sequence[SessaoRegistrada]) -> tuple[ResultadoDeSessao, ...]:
    """As invocações relidas dos streams gravados, como a bancada as mede."""
    return tuple(_relido(registro) for registro in registros)
