"""O que fica vermelho depois do rebase: a suíte do plano e os testes de aceite, na configuração entregue.

O rebase limpo rodava só a suíte, sem os testes de aceite, e decidia se a
verificação final segue valendo pelos arquivos das fatias e dos testes. Na
revisão da T3g, a base mudou um `fator.py` de que o teste de aceite dependia,
nenhuma fatia o tocava, e o Goal chegou à base com o aceite vermelho. Agora,
depois de todo rebase, limpo ou resolvido pela fatia de conflito, os testes de
aceite de todos os critérios rodam na área como ela está (a configuração
entregue), sem deixar rastro, como a suíte.

O vermelho conta como conflito (orquestrador/base_que_andou.py): no
supervisionado, o laço para; no autônomo, a fatia de conflito abre com a falha
no objetivo, e a tentativa dela que deixa o aceite vermelho não vale
(orquestrador/fatia_de_conflito.py).
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.saida_do_aceite import ExecucaoDeAceite, SaidaDoAceite, rodar_testes
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite
from graphow.orquestrador.suite_sem_rastro import sem_o_que_a_suite_escreve

MOTIVO_DA_SUITE: str = "suite_vermelha"
MOTIVO_DO_ACEITE: str = "aceite_vermelho"
LIMITE_DA_SAIDA: int = 1500


@dataclass(frozen=True)
class Vermelho:
    """O que ficou vermelho depois do rebase: o motivo que a fatia de conflito grava, a frase e o fim da saída."""

    motivo: str
    resumo: str
    detalhe: str


def da_suite(suite: ResultadoDaSuite) -> Vermelho:
    """A suíte do plano que ficou vermelha."""
    return Vermelho(MOTIVO_DA_SUITE, "deixou a suite vermelha", suite.descrever())


def aceite_vermelho(contexto: ContextoDoGoal, estado: EstadoDoGoal, rastro: Path) -> Vermelho | None:
    """Os testes de aceite de todos os critérios na área como ela está, sem rastro; None quando todos passam."""
    criterios = tuple(dict.fromkeys(criterio for marco in estado.marcos() for criterio in marco.criterios))

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel,
                           tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s, do_aceite=True)

    with sem_o_que_a_suite_escreve(contexto.area, rastro):
        vermelhos = [execucao for execucao in rodar_testes(SaidaDoAceite.do_livro(estado.aceite), rodar, criterios)
                     if not execucao.passou]
    if not vermelhos:
        return None
    nomes = ", ".join(f"{execucao.teste} de {execucao.criterio}" for execucao in vermelhos)
    return Vermelho(MOTIVO_DO_ACEITE, f"deixou vermelho o teste de aceite {nomes}", "\n".join(map(_descrever, vermelhos)))


def _descrever(execucao: ExecucaoDeAceite) -> str:
    """O teste vermelho, o comando, por que não passou e o fim da saída."""
    return (f"O teste de aceite {execucao.teste} de {execucao.criterio} (`{execucao.comando}`) nao passou: {execucao.motivo}. "
            f"Fim da saida:\n{execucao.saida[-LIMITE_DA_SAIDA:]}")
