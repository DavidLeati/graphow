"""As linhas de `orquestracao-medir --por-rodada`: onde, dentro de um Goal, o tempo e a cota foram gastos.

O total de um Goal diz quanto custou, e não onde. A análise de um goal real
precisou montar à mão a tabela de rodadas para achar as caras; aqui cada Run
do condutor vira uma linha, em ordem de início.

Duas contagens são aproximações, e o relatório diz isso ao fim: a Task não
grava quando fechou, então a conclusão é o último toque dela no log; e a
variação de cota depende de a raiz ter escrito a linha `Cota:` no despacho e
na parada.
"""

from collections.abc import Sequence

from graphow.avaliacao.orquestracao import MedicaoDeGoal
from graphow.avaliacao.rodadas import NaJanela, Rodada

SEM_RODADAS: str = "  rodadas: nenhum Run do condutor atribuido"
DESCONHECIDO: str = "?"
NOTA_DAS_RODADAS: tuple[str, ...] = (
    "Rodadas: a janela vai do inicio ao fim do Run do condutor, e tokens soma os Run do Goal",
    "que comecaram nela, o do condutor incluido. A Task nao grava quando fechou: concluidas",
    "conta a original cujo ultimo toque no log cai na janela, e um toque depois do fechamento",
    "a leva para a rodada desse toque. Cota e o despacho seguinte menos o desta, ou a parada",
    "da raiz menos o desta na ultima da sessao; ? e leitura que falta ou janela que reiniciou.",
)


def linhas_das_rodadas(medicao: MedicaoDeGoal) -> tuple[str, ...]:
    """Uma linha por rodada do Goal, R1 a Rn, depois do bloco dele."""
    if not medicao.rodadas:
        return (SEM_RODADAS,)
    return ("  rodadas:", *(_linha(indice, rodada) for indice, rodada in enumerate(medicao.rodadas, start=1)))


def nota_das_rodadas(medicoes: Sequence[MedicaoDeGoal]) -> tuple[str, ...]:
    """A explicação das colunas, uma vez no fim; some quando nenhum Goal teve rodada."""
    return ("", *NOTA_DAS_RODADAS) if any(medicao.rodadas for medicao in medicoes) else ()


def _linha(indice: int, rodada: Rodada) -> str:
    """A rodada: quando começou, quanto durou, o que caiu na janela e a cota."""
    inicio = rodada.inicio.strftime("%Y-%m-%d %H:%M") if rodada.inicio is not None else "sem inicio"
    duracao = f"{round(rodada.duracao_s / 60)} min" if rodada.duracao_s is not None else "sem duracao"
    cota = f"cota 5h {_pontos(rodada.cota.cinco_horas)}, semana {_pontos(rodada.cota.semanal)}"
    return f"    R{indice} {inicio} | {duracao}{_janela(rodada.na_janela)} | {cota}"


def _janela(janela: NaJanela | None) -> str:
    """O que caiu na janela; sem início ou fim, não há janela para contar."""
    if janela is None:
        return ""
    return (
        f" | concluidas {janela.concluidas} | revisao {janela.aprovados} aprovadas, {janela.rejeitados} rejeitadas"
        f" | tokens {_numero(janela.tokens)} (sem cache {_numero(janela.tokens_sem_cache_leitura)})"
    )


def _pontos(variacao: float | None) -> str:
    """A variação em pontos percentuais, com sinal; `?` quando não se sabe."""
    if variacao is None:
        return DESCONHECIDO
    texto = f"{variacao:g}" if float(variacao).is_integer() else f"{variacao:.1f}"
    return "+" + texto.replace(".", ",")


def _numero(valor: int) -> str:
    """Inteiro com separador de milhar."""
    return f"{valor:,}".replace(",", ".")
