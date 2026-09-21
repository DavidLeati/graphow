"""Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo.

Sem isto a divisão de modelos fica no palpite. Para cada Goal, a medição lê do
grafo a configuração com que ele foi orquestrado (`configuracao`), as tarefas
da decomposição, quantas fecharam sem retrabalho, os vereditos da revisão e os
tokens gastos, somados dos Run que o harness grava: o de cada subagente pelas
tarefas que ele assumiu, e o do orquestrador pelas sessões em que o trabalho do
Goal foi produzido. Uma sessão que serviu a vários Goals divide o custo entre
eles em partes iguais.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import (
    CAMPO_CONFIGURACAO,
    CAMPO_CORRIGE,
    CAMPO_MODELO,
    CAMPO_VEREDITO,
    VEREDITO_APROVADO,
    VEREDITO_REJEITADO,
    ler_texto,
    ler_textos,
)
from graphow.core.types import StatusTask, TipoAresta, TipoNo
from graphow.harness.transcricao import CHAVES_DE_USO
from graphow.projection.graph_view import GrafoView

SEM_CONFIGURACAO: str = "sem configuracao"
SEM_MODELO: str = "sem modelo"
AGENTE_ORQUESTRADOR: str = "orquestrador"
CAMPOS_DE_TOKENS: tuple[str, ...] = tuple(CHAVES_DE_USO.values())


@dataclass(frozen=True)
class MedicaoDeGoal:
    """O que um Goal custou e rendeu sob a configuração com que foi orquestrado."""

    id_goal: str
    rotulo: str
    configuracao: str
    tarefas: int = 0
    concluidas: int = 0
    concluidas_sem_retrabalho: int = 0
    com_retrabalho: int = 0
    correcoes: int = 0
    rejeicoes: int = 0
    aprovacoes: int = 0
    modelos_por_tarefa: Mapping[str, int] = field(default_factory=dict)
    tokens_por_agente: Mapping[str, int] = field(default_factory=dict)
    runs_sem_tokens: int = 0

    @property
    def tokens(self) -> int:
        """Todos os tokens atribuídos ao Goal, de todos os agentes."""
        return sum(self.tokens_por_agente.values())


@dataclass(frozen=True)
class TrabalhoDoGoal:
    """Os nós que pertencem ao Goal: tarefas, artefatos, vereditos e as sessões que os produziram."""

    tarefas: tuple[NoGrafo, ...]
    artefatos: frozenset[str]
    vereditos: tuple[NoGrafo, ...]
    sessoes: frozenset[str]

    @property
    def ids_tarefas(self) -> frozenset[str]:
        """Os ids das tarefas do Goal, correções incluídas."""
        return frozenset(no.id for no in self.tarefas)


class MedidorDeOrquestracao:
    """Consulta pura sobre a projeção: nada é escrito, e o mesmo grafo dá sempre o mesmo número."""

    def __init__(self, view: GrafoView) -> None:
        self._view: GrafoView = view

    def medir(self, ids_goals: Iterable[str] = ()) -> tuple[MedicaoDeGoal, ...]:
        """Uma medição por Goal pedido; sem pedido, todo Goal que tem tarefas decompostas."""
        todos = {no.id: self._coletar_trabalho(no.id) for no in self._view.listar_nos_por_tipo(TipoNo.GOAL)}
        pedidos = tuple(ids_goals) or tuple(sorted(id_goal for id_goal, trabalho in todos.items() if trabalho.tarefas))
        goals_por_sessao = self._goals_por_sessao(todos)
        return tuple(self._medir_goal(id_goal, todos[id_goal], goals_por_sessao) for id_goal in pedidos if id_goal in todos)

    def _coletar_trabalho(self, id_goal: str) -> TrabalhoDoGoal:
        """A decomposição do Goal e o que deriva dela: artefatos, vereditos e sessões produtoras."""
        tarefas = self._descendentes_por_decomposicao(id_goal)
        ids_tarefas = frozenset(no.id for no in tarefas)
        artefatos = frozenset(
            aresta.origem_id
            for id_task in ids_tarefas
            for aresta in self._view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE)
            if self._eh_do_tipo(aresta.origem_id, TipoNo.ARTIFACT)
        )
        vereditos = self._vereditos_sobre(ids_tarefas | artefatos)
        produzidos = ids_tarefas | artefatos | {no.id for no in vereditos} | self._decisoes_que_orientam(ids_tarefas | {id_goal})
        return TrabalhoDoGoal(tarefas=tarefas, artefatos=artefatos, vereditos=vereditos, sessoes=self._sessoes_de(produzidos))

    def _descendentes_por_decomposicao(self, id_raiz: str) -> tuple[NoGrafo, ...]:
        """Todas as Tasks abaixo do nó por `decompoe`, em ordem estável."""
        encontradas: dict[str, NoGrafo] = {}
        fronteira = [id_raiz]
        while fronteira:
            filhos = [a.destino_id for id_no in fronteira for a in self._view.obter_arestas_saida(id_no, TipoAresta.DECOMPOE)]
            fronteira = [id_no for id_no in filhos if id_no not in encontradas and self._eh_do_tipo(id_no, TipoNo.TASK)]
            encontradas.update({id_no: self._view.obter_no(id_no) for id_no in fronteira})
        return tuple(sorted(encontradas.values(), key=lambda no: no.id))

    def _vereditos_sobre(self, alvos: frozenset[str]) -> tuple[NoGrafo, ...]:
        """As Evidence com veredito que derivam de alguma tarefa ou artefato do Goal."""
        candidatas = {
            aresta.origem_id
            for id_alvo in alvos
            for aresta in self._view.obter_arestas_entrada(id_alvo, TipoAresta.DERIVA_DE)
        }
        nos = (self._view.obter_no(id_no) for id_no in sorted(candidatas))
        return tuple(no for no in nos if no is not None and no.tipo == TipoNo.EVIDENCE and ler_texto(no.propriedades, CAMPO_VEREDITO))

    def _decisoes_que_orientam(self, alvos: Iterable[str]) -> set[str]:
        """As Decision ligadas por `orienta` ao Goal ou às tarefas dele."""
        return {aresta.origem_id for id_alvo in alvos for aresta in self._view.obter_arestas_entrada(id_alvo, TipoAresta.ORIENTA)}

    def _sessoes_de(self, ids: Iterable[str]) -> frozenset[str]:
        """As sessões que produziram algum dos nós."""
        return frozenset(
            aresta.origem_id
            for id_no in ids
            for aresta in self._view.obter_arestas_entrada(id_no, TipoAresta.PRODUZ)
            if self._eh_do_tipo(aresta.origem_id, TipoNo.SESSAO)
        )

    def _goals_por_sessao(self, todos: Mapping[str, TrabalhoDoGoal]) -> Mapping[str, int]:
        """Em quantos Goals cada sessão trabalhou: é o divisor do custo dela."""
        contagem: Counter[str] = Counter()
        for trabalho in todos.values():
            contagem.update(trabalho.sessoes)
        return contagem

    def _medir_goal(self, id_goal: str, trabalho: TrabalhoDoGoal, goals_por_sessao: Mapping[str, int]) -> MedicaoDeGoal:
        """Junta a contagem de tarefas, os vereditos e o custo do Goal."""
        goal = self._view.obter_no(id_goal)
        originais = [no for no in trabalho.tarefas if not ler_texto(no.propriedades, CAMPO_CORRIGE)]
        concluidas = [no for no in originais if no.obter_propriedade("status") == StatusTask.CONCLUIDO.value]
        retrabalhadas = {no.id for no in originais if self._tem_correcao(no.id)}
        vereditos = Counter(ler_texto(no.propriedades, CAMPO_VEREDITO) for no in trabalho.vereditos)
        tokens, sem_tokens = self._custo(trabalho, goals_por_sessao)
        return MedicaoDeGoal(
            id_goal=id_goal,
            rotulo=goal.rotulo if goal is not None else id_goal,
            configuracao=_configuracao(goal),
            tarefas=len(originais),
            concluidas=len(concluidas),
            concluidas_sem_retrabalho=sum(1 for no in concluidas if no.id not in retrabalhadas),
            com_retrabalho=len(retrabalhadas),
            correcoes=len(trabalho.tarefas) - len(originais),
            rejeicoes=vereditos[VEREDITO_REJEITADO],
            aprovacoes=vereditos[VEREDITO_APROVADO],
            modelos_por_tarefa=dict(Counter(ler_texto(no.propriedades, CAMPO_MODELO).lower() or SEM_MODELO for no in originais)),
            tokens_por_agente=tokens,
            runs_sem_tokens=sem_tokens,
        )

    def _tem_correcao(self, id_task: str) -> bool:
        """Alguma tarefa de correção abaixo desta pela decomposição."""
        return any(ler_texto(no.propriedades, CAMPO_CORRIGE) for no in self._descendentes_por_decomposicao(id_task))

    def _custo(self, trabalho: TrabalhoDoGoal, goals_por_sessao: Mapping[str, int]) -> tuple[dict[str, int], int]:
        """Tokens por agente: subagentes pelas tarefas assumidas, o resto pela sessão, dividida entre Goals."""
        tokens: dict[str, int] = defaultdict(int)
        sem_tokens = 0
        for run in self._view.listar_nos_por_tipo(TipoNo.RUN):
            divisor = self._divisor_do_run(run, trabalho, goals_por_sessao)
            if divisor == 0:
                continue
            total = _tokens_do_run(run)
            sem_tokens += 1 if total is None else 0
            tokens[str(run.obter_propriedade("agente") or AGENTE_ORQUESTRADOR)] += (total or 0) // divisor
        return dict(sorted(tokens.items())), sem_tokens

    def _divisor_do_run(self, run: NoGrafo, trabalho: TrabalhoDoGoal, goals_por_sessao: Mapping[str, int]) -> int:
        """1 para o Run que assumiu tarefa do Goal; o número de Goals da sessão para o Run sem tarefa; 0 fora."""
        tarefas = set(ler_textos(run.propriedades.get("tarefas")))
        if tarefas:
            return 1 if tarefas & trabalho.ids_tarefas else 0
        id_sessao = ler_texto(run.propriedades, "id_sessao")
        return goals_por_sessao.get(id_sessao, 0) if id_sessao in trabalho.sessoes else 0

    def _eh_do_tipo(self, id_no: str, tipo: TipoNo) -> bool:
        """O nó existe e é do tipo pedido."""
        no = self._view.obter_no(id_no)
        return no is not None and no.tipo == tipo


def _configuracao(goal: NoGrafo | None) -> str:
    """O rótulo da configuração declarado no Goal, ou a marca de que ninguém o declarou."""
    declarada = ler_texto(goal.propriedades, CAMPO_CONFIGURACAO) if goal is not None else ""
    return declarada or SEM_CONFIGURACAO


def _tokens_do_run(run: NoGrafo) -> int | None:
    """A soma das quatro categorias; None quando o Run não traz token nenhum."""
    valores = [run.propriedades.get(campo) for campo in CAMPOS_DE_TOKENS]
    numeros = [valor for valor in valores if isinstance(valor, int) and not isinstance(valor, bool)]
    return sum(numeros) if numeros else None
