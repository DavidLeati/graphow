"""A regressão do escopo governado sobre o histórico real anonimizado: A a E numa medição só.

Reproduz a validação da seção 7 da proposta com o placar, o classificador e a fila
de produção, lidos sobre o corpus de logs reais (`corpus_escopo`). O log é anterior à
ontologia 1.5.0, então o plano e a `motivada_por` são aproximações injetadas numa
cópia do estado (`escopo_sintetico`). Cada Goal do corpus gera:

- A, eventos de desvio com K = 3 e M = 5, e a mesma contagem só com o K da seção 7;
- B, a antecedência do alerta sobre as Tasks emergentes que ele cobre;
- C, a fila: emergente escolhida com plano parado e a posição do plano, antes e depois;
- D, a cobertura de origem: o que o kernel 1.5.0 recusaria por falta de ligação.

E, o caso 14 para 121, é o cenário sintético montado pelos portões reais.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from graphow.avaliacao.cenario_expansao_lateral import ResultadoDaExpansaoLateral, medir_expansao_lateral
from graphow.avaliacao.corpus_escopo import CorpusEscopo, carregar_corpus
from graphow.avaliacao.escopo_cobertura import CoberturaDoGoal, medir_cobertura
from graphow.avaliacao.escopo_desvio import (
    SO_O_GATILHO_POR_RAIZ,
    ConfiguracaoDoDesvio,
    DesvioDoGoal,
    medir_desvio,
)
from graphow.avaliacao.escopo_fila_historica import FilaDoGoal, medir_fila
from graphow.avaliacao.escopo_historia import HistoriaDoGoal, historia_do_goal
from graphow.avaliacao.escopo_sintetico import EscolhaDoMotivo
from graphow.core.types import TipoNo

HIPOTESES_DE_MOTIVO: tuple[EscolhaDoMotivo, ...] = (
    EscolhaDoMotivo.MAIS_RECENTE,
    EscolhaDoMotivo.MAIS_ANTIGA,
    EscolhaDoMotivo.MAIS_ABRANGENTE,
    EscolhaDoMotivo.TODAS,
)


@dataclass(frozen=True)
class MedicaoDoGoal:
    """Tudo que a regressão mede de um Goal do corpus."""

    id_goal: str
    plano: int
    total: int
    lotes: int
    desvio: DesvioDoGoal
    desvio_sem_resposta: DesvioDoGoal
    so_k: Mapping[str, DesvioDoGoal]
    fila: FilaDoGoal
    cobertura: CoberturaDoGoal


@dataclass(frozen=True)
class MedicaoDeEscopo:
    """A regressão inteira: um bloco por Goal do corpus e o cenário do caso 14 para 121."""

    eventos_do_corpus: int
    goals: tuple[MedicaoDoGoal, ...]
    expansao: ResultadoDaExpansaoLateral


def medir_escopo(corpus: CorpusEscopo | None = None) -> MedicaoDeEscopo:
    """Mede cada Goal do corpus, do menor para o maior, e monta o cenário sintético."""
    corpus = corpus or carregar_corpus()
    historias = sorted((historia_do_goal(corpus, id_goal) for id_goal in _goals(corpus)), key=lambda h: len(h.tasks))
    return MedicaoDeEscopo(
        eventos_do_corpus=len(corpus.eventos),
        goals=tuple(medir_goal(corpus, historia) for historia in historias),
        expansao=medir_expansao_lateral(),
    )


def medir_goal(corpus: CorpusEscopo, historia: HistoriaDoGoal) -> MedicaoDoGoal:
    """As medições A a D do Goal: o desvio pelo desenho final e só pelo K, a fila e a cobertura."""
    return MedicaoDoGoal(
        id_goal=historia.id_goal,
        plano=len(historia.plano),
        total=len(historia.tasks),
        lotes=len(historia.lotes),
        desvio=medir_desvio(corpus, historia),
        desvio_sem_resposta=medir_desvio(corpus, historia, ConfiguracaoDoDesvio(com_resposta=False)),
        so_k={motivo.value: medir_desvio(corpus, historia, _so_k(motivo)) for motivo in HIPOTESES_DE_MOTIVO},
        fila=medir_fila(corpus, historia),
        cobertura=medir_cobertura(corpus, historia),
    )


def _so_k(motivo: EscolhaDoMotivo) -> ConfiguracaoDoDesvio:
    """A seção 7 mediu só o K por raiz; a hipótese de motivo diz qual Decision é a raiz da Task."""
    return ConfiguracaoDoDesvio(motivo=motivo, gatilhos=SO_O_GATILHO_POR_RAIZ)


def _goals(corpus: CorpusEscopo) -> tuple[str, ...]:
    """Os Goals do corpus com Tasks, em ordem de identificador."""
    return tuple(sorted(id_no for id_no, no in corpus.estado.nos.items() if no.tipo == TipoNo.GOAL))
