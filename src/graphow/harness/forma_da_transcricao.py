"""A forma do contexto de uma execução: quanto cada turno carregou, o que as ferramentas devolveram, onde parou e o que leu.

Os tokens totais diziam quanto um executor gastou, não por quê. Os executores
caros (49 a 75 min, 240 a 280 turnos) chegaram a ~350 a 400 mil tokens de
contexto por turno, e cada causa observada deixa uma marca própria na
transcrição:

- o contexto de cada turno é a entrada que a resposta pagou, com a leitura e a
  criação de cache: a média mostra o peso que se arrasta, o máximo o pico;
- a saída de ferramenta grande (9 a 33 mil caracteres) entra no contexto e fica
  lá até o fim, então se conta a maior e quantas passam de 2.000 caracteres;
- a pausa longa entre duas respostas do modelo faz o cache de prompt expirar
  (5 min), e a retomada paga a recriação: conta-se a pausa acima de 300 s, do
  último bloco de uma resposta ao primeiro da seguinte;
- os caminhos que o agente leu (Read, e o `path` de Grep e Glob) mostram, contra
  os `arquivos_alvo` da Task, quanto ele releu do repositório fora do alvo; o
  cruzamento é da avaliação, aqui só se coleta a lista. A leitura por Bash e
  PowerShell (`cat`, `sed -n`, `Get-Content`) vai num campo próprio, porque sai
  de heurística sobre o texto do comando; ver harness/leitura_por_shell.py;
- as saídas grandes se contam também por ferramenta, para separar o problema
  do fluxo (Bash, Read) do da vista do graphow (`ler_vista`, `expandir_no`).

Cada mensagem do modelo conta uma vez, pelo id, como no consumo; cada resposta
de ferramenta conta uma vez, pelo id da chamada que ela responde. As
propriedades só aparecem quando há dado, para o Run antigo não ganhar zero
inventado.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from graphow.harness.leitura_por_shell import caminhos_lidos_no_comando

# A entrada de cada turno: o que ele pagou sem cache, o que releu e o que gravou nele.
CHAVES_DE_CONTEXTO: tuple[str, ...] = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
LIMITE_DE_SAIDA_GRANDE: int = 2000
# O cache de prompt expira em 5 minutos; a pausa maior que isso paga a recriação.
PAUSA_LONGA_S: int = 300
# A lista vai para o Run; o limite evita inflá-lo com a varredura de um explorador.
LIMITE_DE_CAMINHOS_LIDOS: int = 200
CAMPO_DE_CAMINHO_POR_FERRAMENTA: Mapping[str, str] = {"Read": "file_path", "Grep": "path", "Glob": "path"}
FERRAMENTAS_DE_SHELL: frozenset[str] = frozenset({"Bash", "PowerShell"})
CAMPO_DO_COMANDO: str = "command"
# O nome MCP `mcp__<servidor>__<ferramenta>` encurta para a ferramenta.
SEPARADOR_DO_NOME_MCP: str = "__"
FERRAMENTA_DESCONHECIDA: str = "?"

CAMPO_CONTEXTO_MEDIO: str = "contexto_medio_turno"
CAMPO_CONTEXTO_MAXIMO: str = "contexto_maximo_turno"
CAMPO_MAIOR_SAIDA: str = "maior_saida_ferramenta"
CAMPO_SAIDAS_GRANDES: str = "saidas_acima_2000"
CAMPO_PAUSAS_LONGAS: str = "pausas_acima_5min"
CAMPO_MAIOR_PAUSA: str = "maior_pausa_s"
CAMPO_CAMINHOS_LIDOS: str = "caminhos_lidos"
CAMPO_CAMINHOS_LIDOS_SHELL: str = "caminhos_lidos_shell"
CAMPO_SAIDAS_GRANDES_POR_FERRAMENTA: str = "saidas_grandes_por_ferramenta"


@dataclass(frozen=True)
class FormaDoContexto:
    """O contexto de cada turno, o tamanho de cada saída de ferramenta, as pausas e os caminhos lidos."""

    contextos: tuple[int, ...] = ()
    saidas_de_ferramenta: tuple[int, ...] = ()
    pausas_s: tuple[int, ...] = ()
    caminhos_lidos: tuple[str, ...] = ()
    caminhos_lidos_shell: tuple[str, ...] = ()
    ferramentas_das_saidas: tuple[str, ...] = ()

    def em_propriedades(self) -> dict[str, Any]:
        """As propriedades do Run, cada grupo só quando a transcrição trouxe o dado."""
        propriedades: dict[str, Any] = {}
        if self.contextos:
            propriedades[CAMPO_CONTEXTO_MEDIO] = sum(self.contextos) // len(self.contextos)
            propriedades[CAMPO_CONTEXTO_MAXIMO] = max(self.contextos)
        if self.saidas_de_ferramenta:
            propriedades[CAMPO_MAIOR_SAIDA] = max(self.saidas_de_ferramenta)
            propriedades[CAMPO_SAIDAS_GRANDES] = sum(1 for tamanho in self.saidas_de_ferramenta if tamanho > LIMITE_DE_SAIDA_GRANDE)
            propriedades.update(self._grandes_por_ferramenta())
        if self.pausas_s:
            propriedades[CAMPO_PAUSAS_LONGAS] = sum(1 for pausa in self.pausas_s if pausa > PAUSA_LONGA_S)
            propriedades[CAMPO_MAIOR_PAUSA] = max(self.pausas_s)
        if self.caminhos_lidos:
            propriedades[CAMPO_CAMINHOS_LIDOS] = list(self.caminhos_lidos)
        if self.caminhos_lidos_shell:
            propriedades[CAMPO_CAMINHOS_LIDOS_SHELL] = list(self.caminhos_lidos_shell)
        return propriedades

    def _grandes_por_ferramenta(self) -> dict[str, Any]:
        """Quantas saídas acima do limite cada ferramenta deu, da que mais deu à que menos; nada sem nenhuma."""
        contagem = Counter(
            ferramenta
            for ferramenta, tamanho in zip(self.ferramentas_das_saidas, self.saidas_de_ferramenta)
            if tamanho > LIMITE_DE_SAIDA_GRANDE
        )
        return {CAMPO_SAIDAS_GRANDES_POR_FERRAMENTA: dict(contagem.most_common())} if contagem else {}


@dataclass
class _JanelaDaMensagem:
    """O primeiro e o último instante em que os blocos de uma mesma mensagem foram gravados."""

    inicio: datetime
    fim: datetime


class AcumuladorDeForma:
    """Junta, entrada por entrada, o que dá a forma do contexto; o contexto por turno vem dos usos já deduplicados."""

    def __init__(self) -> None:
        self._janelas: dict[str, _JanelaDaMensagem] = {}
        self._saidas: dict[str, int] = {}
        self._caminhos: list[str] = []
        self._caminhos_shell: list[str] = []
        self._ferramentas: dict[str, str] = {}

    def registrar_resposta(self, identificador: str, instante: datetime | None, conteudo: object) -> None:
        """O instante de um bloco da resposta do modelo e os caminhos que as chamadas dele leem."""
        if instante is not None:
            janela = self._janelas.setdefault(identificador, _JanelaDaMensagem(instante, instante))
            janela.inicio, janela.fim = min(janela.inicio, instante), max(janela.fim, instante)
        chamadas = _chamadas(conteudo)
        self._ferramentas.update((str(chamada.get("id") or ""), _nome_curto(chamada.get("name"))) for chamada in chamadas)
        self._caminhos.extend(_caminhos_das_chamadas(chamadas))
        self._caminhos_shell.extend(_caminhos_do_shell(chamadas))

    def registrar_resultados(self, conteudo: object) -> None:
        """O tamanho do texto de cada resposta de ferramenta, uma vez por chamada respondida."""
        if not isinstance(conteudo, list):
            return
        for bloco in conteudo:
            if isinstance(bloco, dict) and bloco.get("type") == "tool_result":
                chave = str(bloco.get("tool_use_id") or f"sem-id-{len(self._saidas)}")
                self._saidas[chave] = _tamanho_do_texto(bloco.get("content"))

    def consolidar(self, usos: Iterable[Mapping[str, Any]]) -> FormaDoContexto:
        """A forma do que foi registrado, com o contexto de cada mensagem do modelo.

        A mensagem sintética do ambiente vem com uso zerado; contexto zero não é
        turno e puxaria a média para baixo.
        """
        contextos = (sum(_inteiro(uso.get(chave)) for chave in CHAVES_DE_CONTEXTO) for uso in usos)
        return FormaDoContexto(
            contextos=tuple(contexto for contexto in contextos if contexto),
            saidas_de_ferramenta=tuple(self._saidas.values()),
            ferramentas_das_saidas=tuple(self._ferramentas.get(chave, FERRAMENTA_DESCONHECIDA) for chave in self._saidas),
            pausas_s=_pausas(self._janelas.values()),
            caminhos_lidos=tuple(dict.fromkeys(self._caminhos))[:LIMITE_DE_CAMINHOS_LIDOS],
            caminhos_lidos_shell=tuple(dict.fromkeys(self._caminhos_shell))[:LIMITE_DE_CAMINHOS_LIDOS],
        )


def _pausas(janelas: Iterable[_JanelaDaMensagem]) -> tuple[int, ...]:
    """Do fim de cada resposta ao início da seguinte, em segundos; a sobreposição conta zero."""
    ordenadas = sorted(janelas, key=lambda janela: janela.inicio)
    return tuple(
        max(0, int((seguinte.inicio - anterior.fim).total_seconds()))
        for anterior, seguinte in zip(ordenadas, ordenadas[1:])
    )


def _chamadas(conteudo: object) -> tuple[Mapping[str, Any], ...]:
    """Os blocos de chamada de ferramenta com entrada legível."""
    if not isinstance(conteudo, list):
        return ()
    return tuple(
        bloco
        for bloco in conteudo
        if isinstance(bloco, dict) and bloco.get("type") == "tool_use" and isinstance(bloco.get("input"), dict)
    )


def _nome_curto(nome: object) -> str:
    """O nome da ferramenta, com o MCP encurtado ao que vem depois do último `__`."""
    return str(nome or FERRAMENTA_DESCONHECIDA).split(SEPARADOR_DO_NOME_MCP)[-1] or FERRAMENTA_DESCONHECIDA


def _caminhos_do_shell(chamadas: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """Os caminhos que os comandos de Bash e PowerShell leem, pela heurística conservadora."""
    comandos = (chamada["input"].get(CAMPO_DO_COMANDO) for chamada in chamadas if chamada.get("name") in FERRAMENTAS_DE_SHELL)
    return tuple(caminho for comando in comandos if isinstance(comando, str) for caminho in caminhos_lidos_no_comando(comando))


def _caminhos_das_chamadas(chamadas: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """O caminho de cada chamada de leitura: `file_path` do Read, `path` do Grep e do Glob, quando houver."""
    caminhos = (
        chamada["input"].get(CAMPO_DE_CAMINHO_POR_FERRAMENTA.get(str(chamada.get("name")), ""))
        for chamada in chamadas
    )
    return tuple(caminho for caminho in caminhos if isinstance(caminho, str) and caminho.strip())


def _tamanho_do_texto(resposta: object) -> int:
    """Os caracteres de texto de uma resposta de ferramenta, gravada como texto solto ou como blocos."""
    if isinstance(resposta, str):
        return len(resposta)
    if not isinstance(resposta, list):
        return 0
    return sum(len(str(bloco.get("text", ""))) for bloco in resposta if isinstance(bloco, dict) and bloco.get("type") == "text")


def _inteiro(valor: object) -> int:
    """Contagem de tokens como inteiro; o que não é número conta zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
