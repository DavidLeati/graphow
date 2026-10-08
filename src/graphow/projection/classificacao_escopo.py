"""A classe de escopo de cada Task: de onde ela veio em relação ao plano aprovado do Goal.

O kernel (recusa de Task sem ligação), a fila (faixas), o placar e a avaliação
leem a mesma função. Cada classe se prova pela ligação estrutural e pelo TIPO do
alvo dela: uma Task chamada "Correção" sem `corrige`, ou um `corrige` que aponta
uma Evidence aprovada, não é correção. A classe pode ser lida contra o plano de
referência (a última aprovação humana, que mede o desvio) ou contra o vigente
(o que o kernel confere quando a Task nasce).
"""

from collections.abc import Callable
from enum import Enum

from graphow.core.escopo import (
    CAMPO_ATENDE_CRITERIO,
    CAMPO_TIPO_CONSTRAINT,
    CONSTRAINT_CRITERIO_ACEITE,
)
from graphow.core.models import NoGrafo
from graphow.core.orquestracao import (
    ACAO_ACEITE_APOS_REPROVACAO,
    CAMPO_ACAO,
    CAMPO_CORRIGE,
    CAMPO_VEREDITO,
    VEREDITO_REJEITADO,
    ler_texto,
    ler_textos,
)
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.escopo_plano import (
    IndiceDeDecomposicao,
    VersaoDoPlano,
    goal_da_task,
    plano_de_referencia,
    plano_vigente,
    tasks_do_plano,
)
from graphow.projection.graph_view import GrafoView
from graphow.projection.revisao import artefatos_da_tarefa

STATUS_DE_DECISAO_REVOGADA: str = "revogada"
ALVOS_DE_MOTIVACAO: frozenset[TipoNo] = frozenset(
    {TipoNo.DECISION, TipoNo.EVIDENCE, TipoNo.TASK, TipoNo.QUESTION}
)


class ClasseDeEscopo(str, Enum):
    """De onde a Task veio, em relação ao plano aprovado do Goal."""

    PLANO = "plano"
    B1 = "b1"
    CORRECAO = "correcao"
    ACOMPANHAMENTO = "acompanhamento"
    INTEGRACAO = "integracao"
    REVERSAO = "reversao"
    B3 = "b3"
    SEM_LIGACAO = "sem_ligacao"
    FORA_DE_GOAL = "fora_de_goal"


class BaseDoPlano(str, Enum):
    """Contra que versão do plano a classe é lida."""

    REFERENCIA = "referencia"
    VIGENTE = "vigente"


# O que o kernel aceita como ligação, na ordem em que a classificação confere.
LIGACOES_ACEITAS: dict[ClasseDeEscopo, str] = {
    ClasseDeEscopo.B1: "decompoe vindo de uma Task do plano vigente, ou de uma subdivisão dela",
    ClasseDeEscopo.CORRECAO: "corrige apontando uma Evidence de veredito rejeitado",
    ClasseDeEscopo.ACOMPANHAMENTO: (
        "acompanha apontando uma Evidence rejeitada que uma Decision aceite_apos_reprovacao justifica"
    ),
    ClasseDeEscopo.INTEGRACAO: "integra apontando uma Task do mesmo Goal que tem Artifact",
    ClasseDeEscopo.REVERSAO: "desfaz apontando uma Decision substituida ou revogada",
    ClasseDeEscopo.B3: (
        "motivada_por (Decision, Evidence, Task ou Question) e atende_criterio apontando "
        "uma Constraint criterio_aceite que escopa o Goal"
    ),
}


class ClassificadorDeEscopo:
    """Classifica Tasks de uma vista, indexando a decomposição e guardando o plano de cada Goal."""

    def __init__(self, view: GrafoView, base: BaseDoPlano = BaseDoPlano.REFERENCIA) -> None:
        self._view: GrafoView = view
        self._base: BaseDoPlano = base
        self._indice: IndiceDeDecomposicao = IndiceDeDecomposicao(view)
        self._planos: dict[str, tuple[VersaoDoPlano | None, frozenset[str]]] = {}
        self._provas: dict[ClasseDeEscopo, Callable[[NoGrafo, str], bool]] = {
            ClasseDeEscopo.CORRECAO: self._e_correcao,
            ClasseDeEscopo.ACOMPANHAMENTO: self._e_acompanhamento,
            ClasseDeEscopo.INTEGRACAO: self._e_integracao,
            ClasseDeEscopo.REVERSAO: self._e_reversao,
            ClasseDeEscopo.B3: self._e_emergente_por_criterio,
        }

    @property
    def view(self) -> GrafoView:
        """A vista que o classificador indexa."""
        return self._view

    def goal_da(self, id_task: str) -> str | None:
        """O Goal da Task por `decompoe`, ou None."""
        return goal_da_task(self._view, id_task, indice=self._indice)

    def tem_plano(self, id_goal: str) -> bool:
        """O Goal tem alguma versão de plano aprovada, de qualquer papel."""
        return plano_vigente(self._view, id_goal) is not None

    def classe_da(self, id_task: str) -> ClasseDeEscopo:
        """A classe da Task; `fora_de_goal` quando nenhum Goal a contém."""
        no = self._view.obter_no(id_task)
        id_goal = self.goal_da(id_task) if no is not None and no.tipo == TipoNo.TASK else None
        if no is None or id_goal is None:
            return ClasseDeEscopo.FORA_DE_GOAL
        no_plano = self._conjunto_do_plano(id_goal)
        if id_task in no_plano:
            return ClasseDeEscopo.PLANO
        if self._e_subdivisao(id_task, no_plano):
            return ClasseDeEscopo.B1
        return self._classe_pela_ligacao(no, id_goal)

    def ligacao_valida(self, id_task: str) -> bool:
        """A Task não precisa de ligação, ou tem uma que o kernel aceita.

        Não precisa quando está fora de Goal ou o Goal não tem plano aprovado:
        a ligação obrigatória começa com o plano.
        """
        id_goal = self.goal_da(id_task)
        if id_goal is None or not self.tem_plano(id_goal):
            return True
        return self.classe_da(id_task) != ClasseDeEscopo.SEM_LIGACAO

    def _classe_pela_ligacao(self, no: NoGrafo, id_goal: str) -> ClasseDeEscopo:
        """A primeira classe de ligação que o alvo de fato sustenta; `sem_ligacao` sem nenhuma."""
        for classe, prova in self._provas.items():
            if prova(no, id_goal):
                return classe
        return ClasseDeEscopo.SEM_LIGACAO

    def _conjunto_do_plano(self, id_goal: str) -> frozenset[str]:
        """As Tasks do plano da base escolhida, guardadas por Goal; vazio sem plano."""
        if id_goal not in self._planos:
            escolher = plano_de_referencia if self._base == BaseDoPlano.REFERENCIA else plano_vigente
            versao = escolher(self._view, id_goal)
            conjunto = frozenset()
            if versao is not None:
                conjunto = tasks_do_plano(self._view, id_goal, versao, indice=self._indice)
            self._planos[id_goal] = (versao, conjunto)
        return self._planos[id_goal][1]

    def _e_subdivisao(self, id_task: str, no_plano: frozenset[str]) -> bool:
        """Algum ancestral Task da Task, por `decompoe`, está no plano."""
        visitados = {id_task}
        fronteira = [id_task]
        while fronteira:
            pais = {pai for id_no in fronteira for pai in self._indice.pais(id_no)} - visitados
            if pais & no_plano:
                return True
            visitados |= pais
            fronteira = [pai for pai in pais if self._eh_do_tipo(pai, TipoNo.TASK)]
        return False

    def _e_correcao(self, no: NoGrafo, id_goal: str) -> bool:
        """`corrige` aponta uma Evidence cujo veredito é rejeitado."""
        return self._e_evidencia_rejeitada(ler_texto(no.propriedades, CAMPO_CORRIGE))

    def _e_acompanhamento(self, no: NoGrafo, id_goal: str) -> bool:
        """`acompanha` aponta uma Evidence rejeitada que uma Decision de aceite justifica."""
        alvos = (a.destino_id for a in self._view.obter_arestas_saida(no.id, TipoAresta.ACOMPANHA))
        return any(self._e_evidencia_rejeitada(alvo) and self._tem_aceite(alvo) for alvo in alvos)

    def _e_integracao(self, no: NoGrafo, id_goal: str) -> bool:
        """`integra` aponta uma Task do mesmo Goal que já tem Artifact."""
        alvos = (a.destino_id for a in self._view.obter_arestas_saida(no.id, TipoAresta.INTEGRA))
        return any(
            self._eh_do_tipo(alvo, TipoNo.TASK)
            and self.goal_da(alvo) == id_goal
            and artefatos_da_tarefa(self._view, alvo)
            for alvo in alvos
        )

    def _e_reversao(self, no: NoGrafo, id_goal: str) -> bool:
        """`desfaz` aponta uma Decision substituída ou revogada."""
        alvos = (a.destino_id for a in self._view.obter_arestas_saida(no.id, TipoAresta.DESFAZ))
        return any(self._e_decisao_desfazivel(alvo) for alvo in alvos)

    def _e_emergente_por_criterio(self, no: NoGrafo, id_goal: str) -> bool:
        """`motivada_por` de um alvo do tipo certo e `atende_criterio` de um critério do Goal."""
        motivos = self._view.obter_arestas_saida(no.id, TipoAresta.MOTIVADA_POR)
        motivada = any(self._tem_tipo_em(a.destino_id, ALVOS_DE_MOTIVACAO) for a in motivos)
        criterios = ler_textos(no.propriedades.get(CAMPO_ATENDE_CRITERIO))
        return motivada and any(self._e_criterio_do_goal(criterio, id_goal) for criterio in criterios)

    def _e_criterio_do_goal(self, id_constraint: str, id_goal: str) -> bool:
        """A Constraint é um critério de aceite e escopa o Goal."""
        no = self._view.obter_no(id_constraint)
        if no is None or no.tipo != TipoNo.CONSTRAINT:
            return False
        if ler_texto(no.propriedades, CAMPO_TIPO_CONSTRAINT) != CONSTRAINT_CRITERIO_ACEITE:
            return False
        return any(a.destino_id == id_goal for a in self._view.obter_arestas_saida(id_constraint, TipoAresta.ESCOPA))

    def _e_evidencia_rejeitada(self, id_no: str) -> bool:
        """O nó é uma Evidence de veredito rejeitado."""
        no = self._view.obter_no(id_no)
        if no is None or no.tipo != TipoNo.EVIDENCE:
            return False
        return ler_texto(no.propriedades, CAMPO_VEREDITO).lower() == VEREDITO_REJEITADO

    def _tem_aceite(self, id_evidencia: str) -> bool:
        """A Evidence justifica uma Decision de aceite após a reprovação."""
        destinos = (a.destino_id for a in self._view.obter_arestas_saida(id_evidencia, TipoAresta.JUSTIFICA))
        return any(self._e_decisao_de_aceite(id_no) for id_no in destinos)

    def _e_decisao_de_aceite(self, id_no: str) -> bool:
        """O nó é uma Decision de ação aceite_apos_reprovacao."""
        no = self._view.obter_no(id_no)
        if no is None or no.tipo != TipoNo.DECISION:
            return False
        return ler_texto(no.propriedades, CAMPO_ACAO) == ACAO_ACEITE_APOS_REPROVACAO

    def _e_decisao_desfazivel(self, id_no: str) -> bool:
        """A Decision foi substituída por outra ou está revogada."""
        no = self._view.obter_no(id_no)
        if no is None or no.tipo != TipoNo.DECISION:
            return False
        revogada = ler_texto(no.propriedades, "status").lower() == STATUS_DE_DECISAO_REVOGADA
        return revogada or bool(self._view.obter_arestas_entrada(id_no, TipoAresta.SUBSTITUI))

    def _eh_do_tipo(self, id_no: str, tipo: TipoNo) -> bool:
        """O nó existe e é do tipo pedido."""
        return self._tem_tipo_em(id_no, frozenset({tipo}))

    def _tem_tipo_em(self, id_no: str, tipos: frozenset[TipoNo]) -> bool:
        """O nó existe e é de um dos tipos pedidos."""
        no = self._view.obter_no(id_no)
        return no is not None and no.tipo in tipos


def classificar_tarefa(view: GrafoView, id_task: str) -> ClasseDeEscopo:
    """A classe da Task relativa ao plano de referência: a última aprovação humana, sem ela tudo é emergente."""
    return ClassificadorDeEscopo(view, BaseDoPlano.REFERENCIA).classe_da(id_task)


def classificar_tarefa_vigente(view: GrafoView, id_task: str) -> ClasseDeEscopo:
    """A classe da Task relativa ao plano vigente, de qualquer papel: o que a fila e o kernel conferem."""
    return ClassificadorDeEscopo(view, BaseDoPlano.VIGENTE).classe_da(id_task)


def ligacao_valida(view: GrafoView, id_task: str) -> bool:
    """A Task tem a ligação que o plano vigente exige, ou não precisa de nenhuma."""
    return ClassificadorDeEscopo(view, BaseDoPlano.VIGENTE).ligacao_valida(id_task)


def ligacoes_faltantes(view: GrafoView, id_task: str) -> tuple[str, ...]:
    """As ligações aceitas que a Task não tem; vazio quando ela já está válida."""
    if ligacao_valida(view, id_task):
        return ()
    return tuple(LIGACOES_ACEITAS.values())


def raiz_da_cadeia(view: GrafoView, id_no: str) -> str:
    """O nó de onde a cadeia de `motivada_por` parte: o primeiro sem `motivada_por` saindo dele.

    Com mais de um `motivada_por` segue-se o de menor identificador. Num ciclo
    não há raiz: devolve-se o menor identificador do ciclo, que não muda com o
    ponto de entrada.
    """
    caminho = [id_no]
    while True:
        saidas = view.obter_arestas_saida(caminho[-1], TipoAresta.MOTIVADA_POR)
        if not saidas:
            return caminho[-1]
        proximo = min(aresta.destino_id for aresta in saidas)
        if proximo in caminho:
            return min(caminho[caminho.index(proximo):])
        caminho.append(proximo)
