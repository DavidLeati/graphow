"""As faixas de escopo da fila: o plano primeiro, o emergente que o plano pede depois, o resto no fim.

A fila só reordena e não bloqueia nada. Task sem Goal, ou de Goal sem plano
aprovado, fica na faixa 1: sem plano não há o que preferir. Com plano, a faixa 1
é o plano vigente, as subdivisões dele e o que termina trabalho já feito
(correção, acompanhamento, integração e reversão); a faixa 2, o que o humano criou e o
emergente de que uma Task da faixa 1 depende, direta ou transitivamente; a
faixa 3, o resto.
"""

from collections import defaultdict
from collections.abc import Iterable

from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusTask, TipoAresta
from graphow.projection.classificacao_escopo import (
    BaseDoPlano,
    ClasseDeEscopo,
    ClassificadorDeEscopo,
)
from graphow.projection.graph_view import GrafoView

FAIXA_DO_PLANO: int = 1
FAIXA_DO_QUE_O_PLANO_PEDE: int = 2
FAIXA_DO_RESTO: int = 3
# Correção, acompanhamento, integração e reversão terminam trabalho que já
# existe: deixá-las atrás do pendente do plano manteria aberta a Task que elas fecham.
CLASSES_DA_FAIXA_DO_PLANO: frozenset[ClasseDeEscopo] = frozenset({
    ClasseDeEscopo.PLANO,
    ClasseDeEscopo.B1,
    ClasseDeEscopo.CORRECAO,
    ClasseDeEscopo.ACOMPANHAMENTO,
    ClasseDeEscopo.INTEGRACAO,
    ClasseDeEscopo.REVERSAO,
})


class FaixasDaFila:
    """Classe de escopo e faixa de cada Task de uma sessão, calculadas uma vez por consulta."""

    def __init__(self, view: GrafoView, tarefas: Iterable[NoGrafo]) -> None:
        self._classificador: ClassificadorDeEscopo = ClassificadorDeEscopo(view, BaseDoPlano.VIGENTE)
        self._tarefas: dict[str, NoGrafo] = {no.id: no for no in tarefas}
        self._classes: dict[str, ClasseDeEscopo] = {
            id_task: self._classificador.classe_da(id_task) for id_task in self._tarefas
        }
        self._sem_plano: frozenset[str] = frozenset(
            id_task for id_task in self._tarefas if self._nao_tem_plano(id_task)
        )
        self._puxadas: frozenset[str] = self._dependencias_da_faixa_do_plano(view)

    def escopo(self, id_task: str) -> str:
        """A classe de escopo da Task; vazia quando o Goal dela não tem plano para medir."""
        classe = self._classes.get(id_task, ClasseDeEscopo.FORA_DE_GOAL)
        if classe != ClasseDeEscopo.FORA_DE_GOAL and id_task in self._sem_plano:
            return ""
        return classe.value

    def faixa(self, id_task: str) -> int:
        """A faixa de atendimento da Task entre as pendentes: 1, 2 ou 3."""
        if self._esta_na_faixa_do_plano(id_task):
            return FAIXA_DO_PLANO
        no = self._tarefas.get(id_task)
        criada_por_humano = no is not None and no.proveniencia.papel == PapelAutor.HUMANO.value
        if criada_por_humano or id_task in self._puxadas:
            return FAIXA_DO_QUE_O_PLANO_PEDE
        return FAIXA_DO_RESTO

    def _nao_tem_plano(self, id_task: str) -> bool:
        """A Task está fora de Goal, ou o Goal dela ainda não tem plano aprovado."""
        id_goal = self._classificador.goal_da(id_task)
        return id_goal is None or not self._classificador.tem_plano(id_goal)

    def _esta_na_faixa_do_plano(self, id_task: str) -> bool:
        """Sem plano nada se prefere; com plano, o plano, as subdivisões e o que fecha trabalho feito."""
        classe = self._classes.get(id_task, ClasseDeEscopo.FORA_DE_GOAL)
        return id_task in self._sem_plano or classe in CLASSES_DA_FAIXA_DO_PLANO

    def _dependencias_da_faixa_do_plano(self, view: GrafoView) -> frozenset[str]:
        """O que as Tasks abertas da faixa 1 pedem por `depende_de`, transitivamente."""
        pedidos: dict[str, list[str]] = defaultdict(list)
        for aresta in view.listar_todas_as_arestas():
            if aresta.tipo == TipoAresta.DEPENDE_DE:
                pedidos[aresta.origem_id].append(aresta.destino_id)
        fronteira = [id_task for id_task in sorted(self._tarefas) if self._esta_aberta_no_plano(id_task)]
        alcancadas: set[str] = set()
        while fronteira:
            novas = {d for id_task in fronteira for d in pedidos.get(id_task, ())} - alcancadas
            alcancadas |= novas
            fronteira = sorted(novas)
        return frozenset(alcancadas)

    def _esta_aberta_no_plano(self, id_task: str) -> bool:
        """A Task é da faixa 1 e ainda não foi concluída, então ainda espera suas dependências."""
        status = self._tarefas[id_task].obter_propriedade("status", StatusTask.PENDENTE.value)
        return status != StatusTask.CONCLUIDO.value and self._esta_na_faixa_do_plano(id_task)
