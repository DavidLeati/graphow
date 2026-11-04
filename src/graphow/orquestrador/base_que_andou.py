"""A base que andou: antes de integrar, o orquestrador refaz a branch do Goal sobre a base nova e roda a suíte e o aceite.

Substitui o portão Integrar e o comando que listava as colisões com a base,
que a fase 3 apagou. Quando a base do repositório do humano não está mais na
história da branch do Goal, não há fast-forward. O orquestrador traz a base
nova ao clone, faz o rebase (orquestrador/rebase_no_clone.py) e roda a suíte
do plano, sem os testes de aceite e sem rastro, como na fatia, e depois os
testes de aceite de todos os critérios, na configuração entregue
(orquestrador/vermelho_do_rebase.py):

- tudo verde: o rebase vai ao livro-razão (orquestrador/registro_do_rebase.py),
  e só então as refs andam. Se ele não mudou arquivo que um critério cobre (os
  das fatias do plano dele e os testes de aceite), a verificação final segue
  valendo; se mudou, ela roda de novo antes de integrar;
- conflito, suíte vermelha ou aceite vermelho: o clone volta à branch como
  estava, e nada se registra. No supervisionado, o laço para em
  `conflito_com_a_base`, com os arquivos ou a falha; no autônomo, abre a fatia
  de conflito sobre a base nova, com a falha no objetivo
  (orquestrador/fatia_de_conflito.py).
"""

from pathlib import Path

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.fatia_de_conflito import abrir_fatia_de_conflito
from graphow.orquestrador.git_do_goal import GitDoGoal, descartar_mudancas
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.rebase_no_clone import ConflitoNoRebase, desfazer_o_rebase, mover_as_refs, rebasear, trazer_a_base
from graphow.orquestrador.registro_do_rebase import rebases_do_goal, registrar_o_rebase
from graphow.orquestrador.suite import ResultadoDaSuite, arquivos_ocultos, rodar_suite
from graphow.orquestrador.suite_sem_rastro import sem_o_que_a_suite_escreve
from graphow.orquestrador.vermelho_do_rebase import Vermelho, aceite_vermelho, da_suite

ARQUIVOS_NA_MENSAGEM: int = 20


def base_andou(contexto: ContextoDoGoal) -> bool:
    """A base do repositório do humano não está na história da branch do Goal: não há fast-forward."""
    configuracao = contexto.configuracao
    return not GitDoGoal(Path(configuracao.repositorio)).e_ancestral(configuracao.base, configuracao.ramo)


def rebasear_o_goal(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """O rebase da branch do Goal sobre a base nova, com a suíte; None quando o laço segue (registrado, ou com a fatia de conflito)."""
    numero = len(rebases_do_goal(contexto.livro.view(), contexto.id_goal)) + 1
    descartar_mudancas(contexto.area, contexto.patch(f"antes-do-rebase-{numero}"))
    trazer_a_base(contexto.area_do_goal)
    feito = rebasear(contexto.area, contexto.configuracao.ramo, contexto.configuracao.base)
    if isinstance(feito, ConflitoNoRebase):
        return _sem_rebase(contexto, estado, feito)
    vermelho = _vermelho_depois_do_rebase(contexto, estado, numero)
    if vermelho is not None:
        desfazer_o_rebase(contexto.area, contexto.configuracao.ramo)
        conflito = ConflitoNoRebase(feito.base_antes, feito.base_depois, feito.antes, ())
        return _sem_rebase(contexto, estado, conflito, vermelho=vermelho)
    registrar_o_rebase(contexto, estado, feito)
    mover_as_refs(contexto.area_do_goal, feito.antes, feito.depois)
    return None


def _vermelho_depois_do_rebase(contexto: ContextoDoGoal, estado: EstadoDoGoal, numero: int) -> Vermelho | None:
    """A suíte do plano e, com ela verde, os testes de aceite na ponta rebaseada; None quando tudo passa."""
    suite = _rodar_a_suite(contexto, estado, numero)
    if not suite.passou:
        return da_suite(suite)
    return aceite_vermelho(contexto, estado, contexto.patch(f"rebase-{numero}-aceite"))


def _rodar_a_suite(contexto: ContextoDoGoal, estado: EstadoDoGoal, numero: int) -> ResultadoDaSuite:
    """A suíte do plano na ponta rebaseada, sem os testes de aceite e sem deixar rastro, como na fatia."""
    comando = str((estado.plano or {}).get("comando_suite", ""))
    with sem_o_que_a_suite_escreve(contexto.area, contexto.patch(f"rebase-{numero}-suite")), arquivos_ocultos(
            contexto.area, estado.arquivos_protegidos(), contexto.pasta / "aceite-oculto"):
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel, tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)


def _sem_rebase(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, conflito: ConflitoNoRebase, *, vermelho: Vermelho | None = None
) -> Parada | None:
    """O rebase que não deu: a fatia de conflito no autônomo, a parada no supervisionado."""
    if contexto.configuracao.modo == m.MODO_AUTONOMO:
        abrir_fatia_de_conflito(contexto, estado, conflito, vermelho=vermelho)
        return None
    return parada_do_conflito(contexto, conflito, vermelho)


def parada_do_conflito(contexto: ContextoDoGoal, conflito: ConflitoNoRebase, vermelho: Vermelho | None = None) -> Parada:
    """O rebase que não deu, no supervisionado: a branch do Goal ficou como estava, e a parada diz por quê e os arquivos."""
    configuracao = contexto.configuracao
    arquivos = ", ".join(conflito.arquivos[:ARQUIVOS_NA_MENSAGEM]) or "(o git nao listou arquivo)"
    problema = (f"{vermelho.resumo}. {vermelho.detalhe}" if vermelho is not None
                else f"deu conflito em {arquivos}" + (f". O git disse: {conflito.erro}" if not conflito.arquivos and conflito.erro else ""))
    return Parada(
        contexto.id_goal, MotivoDaParada.CONFLITO_COM_A_BASE,
        f"A base {configuracao.base} andou para {conflito.base_depois[:12]} desde que a branch do Goal saiu dela (em "
        f"{conflito.base_antes[:12]}), e o rebase da branch {configuracao.ramo} sobre ela {problema}. O orquestrador desfez o "
        f"rebase: a branch do Goal ficou como estava, em {conflito.antes[:12]}. Saidas do humano: `graphow orquestrar --goal "
        f"{contexto.id_goal} --modo autonomo` (o orquestrador abre uma fatia de conflito sobre a base nova e a resolve), ou "
        f"`--cancelar --motivo \"...\"`.",
    )
