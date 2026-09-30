"""Medição da orquestração: o mesmo conjunto de tarefas sob configurações diferentes de modelo.

Sem isto a divisão de modelos fica no palpite. Para cada Goal, a medição lê do
grafo a configuração com que ele foi orquestrado (`configuracao`), as tarefas
da decomposição, quantas fecharam sem retrabalho, os vereditos da revisão e os
tokens gastos, somados dos Run que o harness grava: o de cada subagente pelas
tarefas que ele assumiu, e o do orquestrador pelas sessões em que o trabalho do
Goal foi produzido. Uma sessão que serviu a vários Goals divide o custo entre
eles em partes iguais. Conta também os aceites pelo teto de correções: a
correção reprovada de novo que o condutor aceitou, sem critério bloqueante,
por uma Decision marcada com `acao`. E separa as tarefas da trilha leve na
contagem de modelos: elas rodam em Sonnet sob qualquer configuração, e contadas
junto fariam um arranjo parecer mais Sonnet só por ter mais tarefa trivial.

A leitura de cache fica à parte do total: ela domina a soma e custa uma fração
do token de entrada, e comparar arranjos só pelo total é comparar quanto
contexto cada um releu. Os Run sem tokens se contam pelo motivo que o harness
gravou, e as rodadas do condutor dão a duração e a cota; ver rodadas.py.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from graphow.avaliacao.rodadas import Rodada, eh_condutor, eh_run_da_sessao, montar_rodadas
from graphow.core.models import NoGrafo
from graphow.core.orquestracao import (
    ACAO_ACEITE_APOS_REPROVACAO,
    CAMPO_ACAO,
    CAMPO_CONFIGURACAO,
    CAMPO_CORRIGE,
    CAMPO_MODELO,
    CAMPO_TRILHA,
    CAMPO_VEREDITO,
    TRILHA_LEVE,
    VEREDITO_APROVADO,
    VEREDITO_REJEITADO,
    ler_texto,
    ler_textos,
)
from graphow.core.types import StatusTask, TipoAresta, TipoNo
from graphow.harness.transcricao import CAMPO_MOTIVO_SEM_CONSUMO, CHAVES_DE_USO
from graphow.projection.decomposicao import tarefas_da_decomposicao
from graphow.projection.graph_view import GrafoView
from graphow.projection.revisao import artefatos_da_tarefa, vereditos_sobre

SEM_CONFIGURACAO: str = "sem configuracao"
SEM_MODELO: str = "sem modelo"
AGENTE_ORQUESTRADOR: str = "orquestrador"
CAMPOS_DE_TOKENS: tuple[str, ...] = tuple(CHAVES_DE_USO.values())
CAMPO_CACHE_LEITURA: str = CHAVES_DE_USO["cache_read_input_tokens"]
SEM_MOTIVO: str = "sem motivo"


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
    aceites_pelo_teto: int = 0
    modelos_por_tarefa: Mapping[str, int] = field(default_factory=dict)
    tarefas_leves: int = 0
    tokens_por_agente: Mapping[str, int] = field(default_factory=dict)
    tokens_cache_leitura: int = 0
    runs_sem_tokens_por_motivo: Mapping[str, int] = field(default_factory=dict)
    rodadas: tuple[Rodada, ...] = ()

    @property
    def tokens(self) -> int:
        """Todos os tokens atribuídos ao Goal, de todos os agentes."""
        return sum(self.tokens_por_agente.values())

    @property
    def tokens_sem_cache_leitura(self) -> int:
        """Os tokens sem a leitura de cache, que domina o total e custa bem menos que os outros."""
        return self.tokens - self.tokens_cache_leitura

    @property
    def runs_sem_tokens(self) -> int:
        """Quantos Run atribuídos ao Goal não trouxeram token nenhum, por qualquer motivo."""
        return sum(self.runs_sem_tokens_por_motivo.values())

    @property
    def segundos_de_rodada(self) -> float:
        """A soma das durações conhecidas dos condutores, na parte que cabe ao Goal."""
        return sum(rodada.duracao_s / rodada.divisor for rodada in self.rodadas if rodada.duracao_s is not None)

    @property
    def pontos_de_cota_semanal(self) -> float | None:
        """A soma das variações conhecidas da cota semanal, na parte do Goal; None sem nenhuma conhecida."""
        conhecidas = [rodada.cota.semanal / rodada.divisor for rodada in self.rodadas if rodada.cota.semanal is not None]
        return sum(conhecidas) if conhecidas else None


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
        tarefas = tarefas_da_decomposicao(self._view, id_goal)
        ids_tarefas = frozenset(no.id for no in tarefas)
        artefatos = frozenset(id_artefato for id_task in ids_tarefas for id_artefato in artefatos_da_tarefa(self._view, id_task))
        vereditos = vereditos_sobre(self._view, ids_tarefas | artefatos)
        produzidos = ids_tarefas | artefatos | {no.id for no in vereditos} | self._decisoes_que_orientam(ids_tarefas | {id_goal})
        return TrabalhoDoGoal(tarefas=tarefas, artefatos=artefatos, vereditos=vereditos, sessoes=self._sessoes_de(produzidos))

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
            aceites_pelo_teto=self._aceites_pelo_teto(trabalho.ids_tarefas | {id_goal}),
            modelos_por_tarefa=_modelos_da_trilha_completa(originais),
            tarefas_leves=sum(1 for no in originais if _eh_leve(no)),
            **self._custo(trabalho, goals_por_sessao),
        )

    def _aceites_pelo_teto(self, alvos: Iterable[str]) -> int:
        """As Decision de aceite pelo teto que orientam o Goal ou tarefas dele, cada uma contada uma vez.

        A mesma Decision orienta a original, as correções e a tarefa de
        acompanhamento: o que se conta é o aceite, não as arestas.
        """
        decisoes = (self._view.obter_no(id_no) for id_no in self._decisoes_que_orientam(alvos))
        return sum(
            1
            for no in decisoes
            if no is not None
            and no.tipo == TipoNo.DECISION
            and ler_texto(no.propriedades, CAMPO_ACAO) == ACAO_ACEITE_APOS_REPROVACAO
        )

    def _tem_correcao(self, id_task: str) -> bool:
        """Alguma tarefa de correção abaixo desta pela decomposição."""
        return any(ler_texto(no.propriedades, CAMPO_CORRIGE) for no in tarefas_da_decomposicao(self._view, id_task))

    def _custo(self, trabalho: TrabalhoDoGoal, goals_por_sessao: Mapping[str, int]) -> dict[str, Any]:
        """Os campos de custo da medição: tokens por agente, cache, Run sem tokens por motivo e rodadas.

        Subagentes entram pelas tarefas assumidas, o resto pela sessão,
        dividida entre os Goals que ela serviu.
        """
        atribuidos = self._runs_atribuidos(trabalho, goals_por_sessao)
        tokens: dict[str, int] = defaultdict(int)
        for run, divisor in atribuidos:
            tokens[str(run.obter_propriedade("agente") or AGENTE_ORQUESTRADOR)] += (_tokens_do_run(run) or 0) // divisor
        sem_tokens = Counter(_motivo_sem_consumo(run) for run, _ in atribuidos if _tokens_do_run(run) is None)
        raizes = {ler_texto(run.propriedades, "id_sessao"): run for run, _ in atribuidos if eh_run_da_sessao(run)}
        return {
            "tokens_por_agente": dict(sorted(tokens.items())),
            "tokens_cache_leitura": sum(_inteiro(run.propriedades.get(CAMPO_CACHE_LEITURA)) // divisor for run, divisor in atribuidos),
            "runs_sem_tokens_por_motivo": dict(sorted(sem_tokens.items())),
            "rodadas": montar_rodadas([par for par in atribuidos if eh_condutor(par[0])], raizes),
        }

    def _runs_atribuidos(self, trabalho: TrabalhoDoGoal, goals_por_sessao: Mapping[str, int]) -> list[tuple[NoGrafo, int]]:
        """Cada Run que cabe ao Goal, com o divisor da parte dele."""
        pares = ((run, self._divisor_do_run(run, trabalho, goals_por_sessao)) for run in self._view.listar_nos_por_tipo(TipoNo.RUN))
        return [(run, divisor) for run, divisor in pares if divisor > 0]

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


def _eh_leve(tarefa: NoGrafo) -> bool:
    """A Task marcada na trilha leve; a sem trilha é da completa."""
    return ler_texto(tarefa.propriedades, CAMPO_TRILHA).lower() == TRILHA_LEVE


def _modelos_da_trilha_completa(originais: Iterable[NoGrafo]) -> dict[str, int]:
    """Quantas tarefas originais da trilha completa marcaram cada modelo."""
    completas = (no for no in originais if not _eh_leve(no))
    return dict(Counter(ler_texto(no.propriedades, CAMPO_MODELO).lower() or SEM_MODELO for no in completas))


def _tokens_do_run(run: NoGrafo) -> int | None:
    """A soma das quatro categorias; None quando o Run não traz token nenhum."""
    valores = [run.propriedades.get(campo) for campo in CAMPOS_DE_TOKENS]
    numeros = [valor for valor in valores if isinstance(valor, int) and not isinstance(valor, bool)]
    return sum(numeros) if numeros else None


def _motivo_sem_consumo(run: NoGrafo) -> str:
    """Por que o harness não leu tokens; o Run gravado antes do motivo existir fica sem motivo."""
    return ler_texto(run.propriedades, CAMPO_MOTIVO_SEM_CONSUMO) or SEM_MOTIVO


def _inteiro(valor: object) -> int:
    """Contagem de tokens como inteiro; o que não é número conta zero."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
