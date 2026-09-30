"""As rodadas de um Goal: cada Run do condutor, com quanto durou e quanto da cota gastou.

Rodada não é nó do grafo. Cada uma é um Run com `agente` igual a
`graphow-condutor`, que o harness grava quando o condutor termina, com o início
e o fim lidos da transcrição e a cota que a raiz escreveu no despacho. O
condutor espera os filhos em primeiro plano, então a janela dele cobre a rodada.

A variação de cota de uma rodada é a cota do despacho seguinte, na mesma
sessão, menos a dela; a da última da sessão é a cota que a raiz escreveu ao
parar o laço, gravada no Run da sessão. Faltando uma das pontas, a variação é
desconhecida. Variação negativa também: é a janela que reiniciou no meio, e o
gasto real não se sabe.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import ler_texto
from graphow.harness.linha_de_cota import (
    MOMENTO_DA_PARADA,
    MOMENTO_DO_DESPACHO,
    PREFIXO_COTA_5H,
    PREFIXO_COTA_SEMANAL,
)
from graphow.harness.transcricao import ler_instante

AGENTE_CONDUTOR: str = "graphow-condutor"


@dataclass(frozen=True)
class VariacaoDeCota:
    """Os pontos percentuais que a rodada gastou de cada janela; None quando não se sabe."""

    cinco_horas: float | None = None
    semanal: float | None = None


@dataclass(frozen=True)
class Rodada:
    """Um Run do condutor situado no tempo, com a parte dele que cabe ao Goal.

    `divisor` é em quantos Goals a sessão da rodada trabalhou, como no custo:
    a soma por Goal divide a duração e a cota entre eles.
    """

    id_run: str
    id_sessao: str
    inicio: datetime | None = None
    fim: datetime | None = None
    duracao_s: int | None = None
    divisor: int = 1
    cota: VariacaoDeCota = field(default_factory=VariacaoDeCota)


def eh_condutor(run: NoGrafo) -> bool:
    """O Run é de uma rodada: o subagente que terminou era o condutor."""
    return ler_texto(run.propriedades, "agente") == AGENTE_CONDUTOR


def eh_run_da_sessao(run: NoGrafo) -> bool:
    """O Run é da sessão, não de um subagente: é nele que a cota da parada fica."""
    return not ler_texto(run.propriedades, "agente")


def montar_rodadas(condutores: Sequence[tuple[NoGrafo, int]], raizes: Mapping[str, NoGrafo]) -> tuple[Rodada, ...]:
    """As rodadas em ordem de início, as sem início no fim, cada uma com a variação de cota.

    `condutores` traz cada Run do condutor com o divisor dele; `raizes`, o Run
    de cada sessão, de onde sai a cota da parada.
    """
    ordenados = sorted(condutores, key=lambda par: _chave_de_ordem(par[0]))
    return tuple(
        Rodada(
            id_run=run.id,
            id_sessao=ler_texto(run.propriedades, "id_sessao"),
            inicio=ler_instante(run.propriedades.get("inicio")),
            fim=ler_instante(run.propriedades.get("fim")),
            duracao_s=_duracao(run),
            divisor=divisor,
            cota=_variacao(run, _cota_seguinte(run, ordenados[posicao + 1:], raizes)),
        )
        for posicao, (run, divisor) in enumerate(ordenados)
    )


def _chave_de_ordem(run: NoGrafo) -> tuple[int, float, str]:
    """Primeiro as rodadas com início, pelo início; depois as sem, pelo id."""
    inicio = ler_instante(run.propriedades.get("inicio"))
    return (0, inicio.timestamp(), run.id) if inicio is not None else (1, 0.0, run.id)


def _duracao(run: NoGrafo) -> int | None:
    """A duração gravada no Run, em segundos; None quando o harness não a leu."""
    valor = run.propriedades.get("duracao_s")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _cota_seguinte(
    run: NoGrafo,
    seguintes: Iterable[tuple[NoGrafo, int]],
    raizes: Mapping[str, NoGrafo],
) -> tuple[float | None, float | None]:
    """A cota que fecha a rodada: a do despacho seguinte na sessão ou, na última, a da parada."""
    id_sessao = ler_texto(run.propriedades, "id_sessao")
    proxima = next((outro for outro, _ in seguintes if ler_texto(outro.propriedades, "id_sessao") == id_sessao), None)
    if proxima is not None:
        return _cota(proxima, MOMENTO_DO_DESPACHO)
    raiz = raizes.get(id_sessao)
    return _cota(raiz, MOMENTO_DA_PARADA) if raiz is not None else (None, None)


def _cota(run: NoGrafo, momento: str) -> tuple[float | None, float | None]:
    """Os dois percentuais do Run num momento: a janela de 5 horas e a semanal."""
    return (
        _numero(run.propriedades.get(f"{PREFIXO_COTA_5H}{momento}")),
        _numero(run.propriedades.get(f"{PREFIXO_COTA_SEMANAL}{momento}")),
    )


def _variacao(run: NoGrafo, depois: tuple[float | None, float | None]) -> VariacaoDeCota:
    """O fim menos o início de cada janela."""
    antes = _cota(run, MOMENTO_DO_DESPACHO)
    return VariacaoDeCota(cinco_horas=_diferenca(antes[0], depois[0]), semanal=_diferenca(antes[1], depois[1]))


def _diferenca(antes: float | None, depois: float | None) -> float | None:
    """Quanto a janela andou; None sem uma das pontas ou quando ela reiniciou no meio."""
    if antes is None or depois is None:
        return None
    variacao = depois - antes
    return variacao if variacao >= 0 else None


def _numero(valor: object) -> float | None:
    """O percentual gravado; bool e texto não contam."""
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None
