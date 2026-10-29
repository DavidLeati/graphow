"""O teste de aceite refeito só vale se falhar contra o código de antes da implementação.

O aceite pode ser refeito depois que fatias já entregaram código: pelo
`--refazer-aceite`, pela resposta `refazer` à dúvida do teste errado ou pelo
`teste_errado` do modo autônomo. Escrito depois da implementação, o teste
refeito pode nascer verde, e assim não prova nada. Por isso, além de passar na
ponta (ou falhar numa asserção dele, como já era), cada teste refeito do
critério roda contra o código do commit anterior à primeira fatia que cobre o
critério (a ponta, quando nenhuma delas commitou ainda), com o `aceite/`
refeito por cima, e tem de falhar ali numa asserção dele, pela regra do
vermelho válido (orquestrador/resultado_de_teste.py).

Essa rodada acontece num checkout temporário: um clone local da área, na pasta
do Goal, ao lado do clone dele, apagado no fim, mesmo quando a rodada falha.
Nada toca o repositório do humano nem a área. O que fazer com o teste que não
falha antes (voltar ao autor, depois ficar com o antigo) mora em
orquestrador/refazer_aceite.py.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import shutil

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.git_do_goal import TRAILER_DA_TASK, GitDoGoal, commits_entre, remover_area
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.saida_do_aceite import (
    PASTA_DO_ACEITE,
    PASTAS_DE_CACHE,
    SUFIXOS_DE_CACHE,
    ExecucaoDeAceite,
    SaidaDoAceite,
    rodar_testes,
)
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite

PASTA_DO_CHECKOUT: str = "antes-do-refeito"


def commit_de_antes(contexto: ContextoDoGoal, estado: EstadoDoGoal, criterio: str) -> str:
    """O commit anterior à primeira fatia que cobre o critério, achada pelo trailer; a ponta, quando nenhuma delas commitou."""
    fatias = {fatia.id for fatia in estado.fatias if criterio in fatia.lista(m.CAMPO_CRITERIOS)}
    delas = [commit.hash for commit in commits_entre(contexto.area, contexto.configuracao.base)
             if any(commit.tem_trailer(TRAILER_DA_TASK, fatia) for fatia in fatias)]
    return contexto.git.rodar("rev-parse", f"{delas[-1]}^").strip() if delas else contexto.git.head()


@contextmanager
def checkout_de_antes(area: Path, destino: Path, commit: str) -> Iterator[Path]:
    """Um clone local da área no commit dado, com o `aceite/` da área por cima; sai no fim, mesmo quando o bloco falha."""
    remover_area(destino)
    try:
        GitDoGoal(area).rodar("clone", "-q", "--local", "--no-checkout", "--no-tags", str(area), str(destino))
        GitDoGoal(destino).rodar("checkout", "-q", "--detach", commit)
        _copiar_o_aceite(area, destino)
        yield destino
    finally:
        remover_area(destino)


def _copiar_o_aceite(area: Path, destino: Path) -> None:
    """O `aceite/` da área (o refeito, ainda fora de commit) no lugar do `aceite/` do commit, sem o cache."""
    shutil.rmtree(destino / PASTA_DO_ACEITE, ignore_errors=True)
    if (area / PASTA_DO_ACEITE).is_dir():
        sem_cache = shutil.ignore_patterns(*PASTAS_DE_CACHE, *(f"*{sufixo}" for sufixo in SUFIXOS_DE_CACHE))
        shutil.copytree(area / PASTA_DO_ACEITE, destino / PASTA_DO_ACEITE, ignore=sem_cache)


def conferir_o_vermelho_de_antes(contexto: ContextoDoGoal, estado: EstadoDoGoal, refeito: SaidaDoAceite, *,
                                 criterio: str) -> tuple[str, ...]:
    """Os testes refeitos do critério que não falham numa asserção contra o código de antes; vazio quando todos falham."""
    commit = commit_de_antes(contexto, estado, criterio)
    destino = contexto.pasta / PASTA_DO_CHECKOUT

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(destino, comando, contexto.banco_descartavel,
                           tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s, do_aceite=True)

    with checkout_de_antes(contexto.area, destino, commit):
        execucoes = rodar_testes(refeito, rodar, (criterio,))
    return tuple(problema for execucao in execucoes if (problema := _problema(execucao, commit)))


def _problema(execucao: ExecucaoDeAceite, commit: str) -> str:
    """O teste que passa contra o código de antes, ou que falha ali fora da asserção; vazio quando o vermelho vale."""
    antes = (f"contra o codigo de antes da implementacao (o commit {commit[:12]}, anterior a primeira fatia que cobre "
             f"{execucao.criterio})")
    if execucao.passou:
        return (f"o teste {execucao.teste} de {execucao.criterio} passa {antes}: escrito depois da implementacao, ele nao "
                "prova o criterio. Reescreva-o para falhar ali numa assercao dele e passar com a implementacao")
    motivo = execucao.vermelho_invalido()
    return f"o teste {execucao.teste} de {execucao.criterio} falha {antes} pelo motivo errado: {motivo}" if motivo else ""
