"""Custo, tokens e minutos de uma execução, com as definições do laboratório.

Uma execução é uma ou mais invocações de `claude -p`. No laboratório, o script
de cada raiz anotava no log as marcas `{"_lab": "inicio"}` e `{"_lab": "fim"}`
em volta de cada invocação; na bancada, quem anota início e fim é a sessão.

- Minutos: do primeiro início ao último fim, em tempo de parede, inclusive as
  pausas entre invocações retomadas.
- Tokens: das transcrições de cada sessão e dos subagentes dela (ver
  `graphow.bancada.transcricoes`); sem transcrição, o `modelUsage` do
  resultado, que conta a última entrada de cada mensagem e dá uns 0,5% a mais.
- Custo: o `total_cost_usd` do resultado. Uma sessão retomada com `--resume`
  herda o custo da anterior, e o resultado de cada invocação traz o acumulado
  da sessão. O laboratório somou os resultados e contou duas vezes as
  invocações anteriores de cada sessão retomada: os três projetos do graphow
  0.4.4 saíram com o custo inflado (na agenda, US$ 18,58 em vez de 10,65).
  Aqui vale o último resultado de cada sessão.

Que o resultado é acumulado se confere, em vez de se supor: com transcrição, o
`modelUsage` do último resultado bate com os tokens dela pela última entrada,
e a soma dos resultados não bate; sem transcrição, o acumulado nunca diminui.
Quando a conferência diz que a sessão não acumulou, os custos se somam.

O que não se sabe fica None, e não zero. A invocação que morreu sem `result`
(tempo esgotado, processo morto) gastou, só não disse quanto: o custo da
execução fica desconhecido, e os tokens também, a menos que a transcrição da
sessão esteja em disco. Zero ali faria a execução parecer de graça no placar.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from graphow.bancada.transcricoes import TokensDasTranscricoes, contar_tokens, localizar_transcricoes
from graphow.harness.transcricao import ler_instante
from graphow.sessoes.leitura_stream import ResultadoDoStream, eventos_do_stream, ler_resultado

MARCA_DO_LABORATORIO: str = "_lab"
MARCA_DE_INICIO: str = "inicio"
MARCA_DE_FIM: str = "fim"
FONTE_TRANSCRICOES: str = "transcricoes"
FONTE_MODEL_USAGE: str = "model_usage"
FONTE_MISTA: str = "transcricoes_e_model_usage"
SEGUNDOS_POR_MINUTO: float = 60.0
Numero = TypeVar("Numero", int, float)


@dataclass(frozen=True)
class Invocacao:
    """Uma chamada de `claude -p`: a sessão, quando começou, quando acabou e o resultado que deu.

    A sessão vem do resultado ou, sem ele, do `system/init`: uma invocação que
    morreu antes do fim ainda gastou tokens, e eles estão na transcrição dela.
    """

    sessao: str
    inicio: datetime | None
    fim: datetime | None
    resultado: ResultadoDoStream | None


@dataclass(frozen=True)
class Medicao:
    """Custo, tokens e minutos de uma execução, e de onde saíram os tokens."""

    custo_usd: float | None
    tokens: int | None
    fonte_dos_tokens: str
    minutos: float | None
    sessoes: tuple[str, ...]

    def em_dicionario(self) -> dict[str, Any]:
        """Os números como a bancada os grava, com o custo em centavos e os minutos com uma casa."""
        return {
            "custo_usd": None if self.custo_usd is None else round(self.custo_usd, 2),
            "tokens": self.tokens,
            "fonte_dos_tokens": self.fonte_dos_tokens,
            "minutos": None if self.minutos is None else round(self.minutos, 1),
            "sessoes": list(self.sessoes),
        }


class _LeitorDoLog:
    """Junta os eventos de um log do laboratório em invocações, marca a marca."""

    def __init__(self) -> None:
        self.invocacoes: list[Invocacao] = []
        self._aberta: bool = False
        self._inicio: datetime | None = None
        self._sessao: str = ""
        self._resultado: ResultadoDoStream | None = None

    def acrescentar(self, evento: Mapping[str, Any]) -> None:
        """Marca de início abre, marca de fim fecha; init e result preenchem a invocação aberta."""
        marca = evento.get(MARCA_DO_LABORATORIO)
        if marca == MARCA_DE_INICIO:
            self._aberta, self._inicio, self._sessao, self._resultado = True, ler_instante(evento.get("quando")), "", None
            return
        if marca == MARCA_DE_FIM:
            self._fechar(ler_instante(evento.get("quando")))
            return
        if evento.get("type") == "system" and evento.get("subtype") == "init":
            self._sessao = self._sessao or str(evento.get("session_id") or "")
        if evento.get("type") == "result":
            self._registrar(ler_resultado(evento))

    def _registrar(self, resultado: ResultadoDoStream) -> None:
        """Dentro de marcas, o resultado espera o fim; fora delas, já é uma invocação sem instantes."""
        self._resultado = resultado
        if not self._aberta:
            self._fechar(None)

    def _fechar(self, fim: datetime | None) -> None:
        """A invocação aberta vai para a lista, e o leitor fica pronto para a próxima."""
        sessao = self._resultado.session_id if self._resultado else self._sessao
        self.invocacoes.append(Invocacao(sessao, self._inicio, fim, self._resultado))
        self._aberta, self._inicio, self._sessao, self._resultado = False, None, "", None


def invocacoes_do_log(linhas: Iterable[str]) -> tuple[Invocacao, ...]:
    """As invocações de um log do laboratório: cada par de marcas e o que veio entre elas.

    Sem marcas, cada `result` é uma invocação sem instantes.
    """
    leitor = _LeitorDoLog()
    for evento in eventos_do_stream(linhas):
        leitor.acrescentar(evento)
    return tuple(leitor.invocacoes)


def ler_log(caminho: Path) -> tuple[Invocacao, ...]:
    """As invocações do log em disco."""
    with caminho.open(encoding="utf-8", errors="replace") as linhas:
        return invocacoes_do_log(linhas)


def medir(invocacoes: Sequence[Invocacao], raiz_das_transcricoes: Path | None) -> Medicao:
    """Custo, tokens e minutos das invocações, com as transcrições achadas sob a raiz.

    Sem invocação, ou com uma que morreu antes de abrir a sessão, nada se sabe
    do que foi gasto: custo e tokens ficam None.
    """
    ate = _corte(invocacoes)
    por_sessao = _por_sessao(invocacoes)
    medidas = {sessao: _tokens_da_sessao(sessao, raiz_das_transcricoes, ate) for sessao in por_sessao}
    contam = {sessao: _resultados_que_contam(lista, medidas[sessao]) for sessao, lista in por_sessao.items()}
    sem_sessao = not invocacoes or any(not invocacao.sessao for invocacao in invocacoes)
    custos = [None if resultados is None else sum(r.custo_usd for r in resultados) for resultados in contam.values()]
    tokens = [_tokens_finais(contam[sessao], medidas[sessao]) for sessao in por_sessao]
    return Medicao(
        custo_usd=None if sem_sessao else _soma_conhecida(custos),
        tokens=None if sem_sessao else _soma_conhecida(tokens),
        fonte_dos_tokens=_fonte(medidas.values()),
        minutos=minutos_das_invocacoes(invocacoes),
        sessoes=tuple(por_sessao),
    )


def minutos_das_invocacoes(invocacoes: Sequence[Invocacao]) -> float | None:
    """Do primeiro início ao último fim; None quando falta algum instante."""
    inicios = [invocacao.inicio for invocacao in invocacoes if invocacao.inicio is not None]
    fins = [invocacao.fim for invocacao in invocacoes if invocacao.fim is not None]
    if not invocacoes or len(inicios) < len(invocacoes) or len(fins) < len(invocacoes):
        return None
    return (max(fins) - min(inicios)).total_seconds() / SEGUNDOS_POR_MINUTO


def contar_sessoes_retomadas(invocacoes: Sequence[Invocacao]) -> int:
    """Quantas sessões tiveram mais de um resultado: as que o laboratório contou em dobro."""
    return sum(1 for lista in _por_sessao(invocacoes).values() if sum(1 for i in lista if i.resultado) > 1)


def _corte(invocacoes: Sequence[Invocacao]) -> datetime | None:
    """O fim da última invocação medida: as transcrições não contam o que veio depois dela."""
    fins = [invocacao.fim for invocacao in invocacoes if invocacao.fim is not None]
    return max(fins) if fins else None


def _por_sessao(invocacoes: Sequence[Invocacao]) -> dict[str, list[Invocacao]]:
    """As invocações de cada sessão, na ordem em que rodaram; as sem sessão ficam de fora."""
    por_sessao: dict[str, list[Invocacao]] = {}
    for invocacao in invocacoes:
        por_sessao.setdefault(invocacao.sessao, []).append(invocacao)
    return {sessao: lista for sessao, lista in por_sessao.items() if sessao}


def _tokens_da_sessao(sessao: str, raiz: Path | None, ate: datetime | None) -> TokensDasTranscricoes:
    """As transcrições da sessão e dos subagentes dela, contadas até o corte."""
    if raiz is None:
        return TokensDasTranscricoes()
    return contar_tokens(localizar_transcricoes(raiz, sessao), ate)


def _resultados_que_contam(
    invocacoes: Sequence[Invocacao], transcricoes: TokensDasTranscricoes
) -> tuple[ResultadoDoStream, ...] | None:
    """Os resultados cuja soma é o gasto da sessão: o último, se ela acumulou; todos, se não.

    None quando o gasto não está em resultado nenhum: a última invocação morreu
    sem `result`, ou, numa sessão que não acumula, faltou o de alguma.
    """
    resultados = tuple(invocacao.resultado for invocacao in invocacoes if invocacao.resultado is not None)
    if not resultados or invocacoes[-1].resultado is None:
        return None
    if _acumulou(resultados, transcricoes):
        return resultados[-1:]
    return resultados if len(resultados) == len(invocacoes) else None


def _tokens_finais(resultados: Sequence[ResultadoDoStream] | None, transcricoes: TokensDasTranscricoes) -> int | None:
    """Os tokens das transcrições, que existem mesmo quando a sessão morreu; sem elas, o `modelUsage`."""
    if transcricoes.arquivos:
        return transcricoes.pela_primeira
    return None if resultados is None else sum(resultado.tokens.total for resultado in resultados)


def _soma_conhecida(valores: Sequence[Numero | None]) -> Numero | None:
    """A soma, ou None se algum valor é desconhecido."""
    if any(valor is None for valor in valores):
        return None
    return sum(valor for valor in valores if valor is not None)


def _acumulou(resultados: Sequence[ResultadoDoStream], transcricoes: TokensDasTranscricoes) -> bool:
    """Se o resultado de cada invocação trouxe o acumulado da sessão."""
    if len(resultados) < 2:
        return True
    if transcricoes.arquivos:
        ultimo, soma = resultados[-1].tokens.total, sum(resultado.tokens.total for resultado in resultados)
        return abs(transcricoes.pela_ultima - ultimo) <= abs(transcricoes.pela_ultima - soma)
    custos = [resultado.custo_usd for resultado in resultados]
    return all(anterior <= seguinte for anterior, seguinte in zip(custos, custos[1:]))


def _fonte(medidas: Iterable[TokensDasTranscricoes]) -> str:
    """De onde saíram os tokens: todas as sessões com transcrição, nenhuma, ou parte."""
    com_transcricao = [medida.arquivos > 0 for medida in medidas]
    if com_transcricao and all(com_transcricao):
        return FONTE_TRANSCRICOES
    return FONTE_MISTA if any(com_transcricao) else FONTE_MODEL_USAGE
