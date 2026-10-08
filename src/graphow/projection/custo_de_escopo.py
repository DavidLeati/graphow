"""O custo por decisão: de que raiz de `motivada_por` nasceu cada Task depois da referência e quanto ela custou.

A pergunta do escopo governado é "esta decisão e as Tasks que ela gerou cabem no
Goal?". A resposta precisa das Tasks agrupadas pela raiz da cadeia de
`motivada_por`, com a classe de cada uma, os alvos tocados, o custo dos Runs e as
reversões somadas à decisão desfeita. Correção, acompanhamento e integração não
têm `motivada_por` próprio: herdam a raiz da Task que corrigem, acompanham ou
integram. A classe é sempre relativa ao plano de referência (`classificacao_escopo`),
e só as Tasks nascidas depois dele entram. Sem referência humana, toda Task entra.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from graphow.core.models import NoGrafo
from graphow.core.orquestracao import CAMPO_ARQUIVOS_ALVO, CAMPO_CORRIGE, ler_texto, ler_textos
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.projection.classificacao_escopo import (
    BaseDoPlano,
    ClasseDeEscopo,
    ClassificadorDeEscopo,
    raiz_da_cadeia,
)
from graphow.projection.decomposicao import tarefas_da_decomposicao
from graphow.projection.escopo_plano import plano_de_referencia
from graphow.projection.graph_view import GrafoView

# Convenções que o Run e a Task já trazem: o harness grava os tokens nestes campos
# (`harness.transcricao.CHAVES_DE_USO`) e a lista de Tasks que o Run assumiu em
# `tarefas`. A projeção não importa o harness, por isso os nomes ficam aqui.
CAMPO_TAREFAS_DO_RUN: str = "tarefas"
CAMPOS_DE_TOKENS: tuple[str, ...] = (
    "tokens_entrada",
    "tokens_saida",
    "tokens_cache_leitura",
    "tokens_cache_criacao",
)
# No trabalho que não é código a Task declara a fonte onde antes declarava o arquivo.
CAMPO_FONTE: str = "fonte"
# Antes de qualquer aprovação humana nenhum `seq` de criação fica abaixo do corte.
SEM_REFERENCIA: int = -1
PROFUNDIDADE_MAXIMA: int = 64
CLASSES_EMERGENTES: frozenset[ClasseDeEscopo] = frozenset({ClasseDeEscopo.B3, ClasseDeEscopo.SEM_LIGACAO})
CLASSES_QUE_HERDAM_A_RAIZ: frozenset[ClasseDeEscopo] = frozenset(
    {ClasseDeEscopo.CORRECAO, ClasseDeEscopo.ACOMPANHAMENTO, ClasseDeEscopo.INTEGRACAO}
)
PASSOS_PARA_ACHAR_A_ORIGEM: int = 8


@dataclass(frozen=True)
class TaskDoEscopo:
    """Uma Task nascida depois da referência: a classe, quem a criou, a raiz que a debita e a profundidade."""

    id: str
    classe: ClasseDeEscopo
    seq: int
    humana: bool
    status: str
    raiz: str | None
    profundidade: int

    @property
    def eh_emergente(self) -> bool:
        """B3 e Task sem ligação são o que o gatilho de desvio conta."""
        return self.classe in CLASSES_EMERGENTES


@dataclass(frozen=True)
class CustoDaRaiz:
    """O que uma raiz de cadeia gerou: Tasks por classe, alvos, custo dos Runs, reversões e profundidade."""

    raiz: str
    tasks: tuple[TaskDoEscopo, ...]
    tasks_por_classe: Mapping[str, int]
    alvos: tuple[str, ...]
    runs: int
    tokens: int
    profundidade: int

    @property
    def reversoes(self) -> int:
        """As reversões (`desfaz`) debitadas a esta raiz."""
        return self.tasks_por_classe.get(ClasseDeEscopo.REVERSAO.value, 0)

    @property
    def emergentes(self) -> tuple[TaskDoEscopo, ...]:
        """As Tasks B3 e sem ligação da raiz, da mais antiga à mais nova."""
        return tuple(task for task in self.tasks if task.eh_emergente)


def seq_da_referencia(view: GrafoView, id_goal: str) -> int:
    """O `seq` da última aprovação humana do plano; `SEM_REFERENCIA` quando não houve."""
    referencia = plano_de_referencia(view, id_goal)
    return referencia.seq if referencia is not None else SEM_REFERENCIA


def tasks_desde_a_referencia(view: GrafoView, id_goal: str) -> tuple[TaskDoEscopo, ...]:
    """As Tasks do Goal nascidas depois da referência, classificadas contra ela, em ordem de criação."""
    corte = seq_da_referencia(view, id_goal)
    classificador = ClassificadorDeEscopo(view, BaseDoPlano.REFERENCIA)
    atribuidor = _Atribuidor(view)
    tasks: list[TaskDoEscopo] = []
    for no in tarefas_da_decomposicao(view, id_goal):
        classe = classificador.classe_da(no.id)
        if no.ordem.seq_criacao > corte and classe != ClasseDeEscopo.PLANO:
            tasks.append(_task_do_escopo(no, classe, atribuidor))
    return tuple(sorted(tasks, key=lambda task: (task.seq, task.id)))


def custo_por_raiz(view: GrafoView, tasks: Iterable[TaskDoEscopo]) -> tuple[CustoDaRaiz, ...]:
    """O custo de cada raiz que gerou Task, em ordem de identificador da raiz."""
    por_raiz: dict[str, list[TaskDoEscopo]] = defaultdict(list)
    for task in tasks:
        if task.raiz is not None:
            por_raiz[task.raiz].append(task)
    consumo = _consumo_por_task(view)
    return tuple(_custo_da_raiz(view, grupo, consumo) for _, grupo in sorted(por_raiz.items()))


def custo_do_goal(view: GrafoView, id_goal: str) -> tuple[CustoDaRaiz, ...]:
    """O custo por raiz de todo o trabalho do Goal depois da referência."""
    return custo_por_raiz(view, tasks_desde_a_referencia(view, id_goal))


def profundidade_da_cadeia(view: GrafoView, id_no: str) -> int:
    """O maior número de saltos de `motivada_por` a partir do nó; um ciclo para no teto."""
    fronteira = {id_no}
    for passos in range(PROFUNDIDADE_MAXIMA):
        fronteira = {
            aresta.destino_id
            for atual in fronteira
            for aresta in view.obter_arestas_saida(atual, TipoAresta.MOTIVADA_POR)
        }
        if not fronteira:
            return passos
    return PROFUNDIDADE_MAXIMA


def _task_do_escopo(no: NoGrafo, classe: ClasseDeEscopo, atribuidor: "_Atribuidor") -> TaskDoEscopo:
    """A Task como o placar a lê."""
    return TaskDoEscopo(
        id=no.id,
        classe=classe,
        seq=no.ordem.seq_criacao,
        humana=no.proveniencia.papel == PapelAutor.HUMANO.value,
        status=ler_texto(no.propriedades, "status") or StatusTask.PENDENTE.value,
        raiz=atribuidor.raiz_de(no, classe),
        profundidade=profundidade_da_cadeia(atribuidor.view, no.id),
    )


def _custo_da_raiz(
    view: GrafoView,
    tasks: list[TaskDoEscopo],
    consumo: Mapping[str, list[tuple[str, int]]],
) -> CustoDaRaiz:
    """Junta as Tasks de uma raiz: classes, alvos e o consumo dos Runs que as assumiram."""
    ordenadas = tuple(sorted(tasks, key=lambda task: (task.seq, task.id)))
    raiz = str(ordenadas[0].raiz)
    runs = {id_run for task in ordenadas for id_run, _ in consumo.get(task.id, ())}
    tokens = sum(parte for task in ordenadas for _, parte in consumo.get(task.id, ()))
    return CustoDaRaiz(
        raiz=raiz,
        tasks=ordenadas,
        tasks_por_classe=dict(_contar(task.classe.value for task in ordenadas)),
        alvos=_alvos_das_tasks(view, ordenadas),
        runs=len(runs),
        tokens=tokens,
        profundidade=max(task.profundidade for task in ordenadas),
    )


def _contar(valores: Iterable[str]) -> dict[str, int]:
    """Quantas vezes cada valor aparece, em ordem alfabética."""
    contagem: dict[str, int] = defaultdict(int)
    for valor in valores:
        contagem[valor] += 1
    return dict(sorted(contagem.items()))


def _alvos_das_tasks(view: GrafoView, tasks: Iterable[TaskDoEscopo]) -> tuple[str, ...]:
    """A união de `arquivos_alvo` e `fonte` das Tasks, sem repetição e em ordem."""
    alvos: set[str] = set()
    for task in tasks:
        no = view.obter_no(task.id)
        if no is not None:
            alvos.update(ler_textos(no.propriedades.get(CAMPO_ARQUIVOS_ALVO)))
            alvos.update(ler_textos(no.propriedades.get(CAMPO_FONTE)))
    return tuple(sorted(alvos))


def _consumo_por_task(view: GrafoView) -> dict[str, list[tuple[str, int]]]:
    """Por Task, os Runs que a assumiram e a parte deles nos tokens, dividida entre as Tasks do Run.

    O Run da sessão, que não lista Task, não é de ninguém e fica de fora; o Run
    sem token nenhum custa zero.
    """
    consumo: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for run in view.listar_nos_por_tipo(TipoNo.RUN):
        ids = ler_textos(run.propriedades.get(CAMPO_TAREFAS_DO_RUN))
        for id_task in ids:
            consumo[id_task].append((run.id, _tokens_do_run(run) // len(ids)))
    return consumo


def _tokens_do_run(run: NoGrafo) -> int:
    """A soma das quatro categorias de token do Run; zero quando ele não trouxe nenhuma."""
    valores = (run.propriedades.get(campo) for campo in CAMPOS_DE_TOKENS)
    return sum(valor for valor in valores if isinstance(valor, int) and not isinstance(valor, bool))


class _Atribuidor:
    """Acha a raiz que paga por cada Task: a da cadeia de `motivada_por`, a da reversão ou a da Task corrigida."""

    def __init__(self, view: GrafoView) -> None:
        self.view: GrafoView = view

    def raiz_de(self, no: NoGrafo, classe: ClasseDeEscopo) -> str | None:
        """A raiz da Task; None para a subdivisão sem `motivada_por`, que só conta no Goal."""
        if classe == ClasseDeEscopo.REVERSAO:
            desfeita = self._menor_destino(no.id, TipoAresta.DESFAZ)
            if desfeita is not None:
                return raiz_da_cadeia(self.view, desfeita)
        if self._tem_motivo(no.id):
            return raiz_da_cadeia(self.view, no.id)
        if classe in CLASSES_QUE_HERDAM_A_RAIZ:
            return self._raiz_pela_origem(no)
        return None if classe == ClasseDeEscopo.B1 else no.id

    def _raiz_pela_origem(self, no: NoGrafo) -> str:
        """Sobe pela Task corrigida, acompanhada ou integrada até uma que tenha `motivada_por`."""
        atual, vistos = no, {no.id}
        for _ in range(PASSOS_PARA_ACHAR_A_ORIGEM):
            origem = self._origem(atual)
            alvo = self.view.obter_no(origem) if origem is not None and origem not in vistos else None
            if alvo is None:
                break
            vistos.add(alvo.id)
            atual = alvo
            if self._tem_motivo(atual.id):
                break
        return raiz_da_cadeia(self.view, atual.id)

    def _origem(self, no: NoGrafo) -> str | None:
        """A Task que esta corrige, acompanha ou integra; None quando não se acha."""
        evidencia = ler_texto(no.propriedades, CAMPO_CORRIGE) or self._menor_destino(no.id, TipoAresta.ACOMPANHA)
        if evidencia:
            return self._task_avaliada(evidencia)
        return self._menor_destino(no.id, TipoAresta.INTEGRA)

    def _task_avaliada(self, id_evidencia: str) -> str | None:
        """A Task que a Evidence de revisão julgou, direto ou pelo Artifact de que deriva."""
        alvos = [self.view.obter_no(a.destino_id) for a in self.view.obter_arestas_saida(id_evidencia, TipoAresta.DERIVA_DE)]
        achadas = {alvo.id for alvo in alvos if alvo is not None and alvo.tipo == TipoNo.TASK}
        for artifact in (alvo for alvo in alvos if alvo is not None and alvo.tipo == TipoNo.ARTIFACT):
            achadas.update(self._destinos_task(artifact.id, TipoAresta.DERIVA_DE))
        return min(achadas) if achadas else None

    def _destinos_task(self, id_no: str, tipo: TipoAresta) -> set[str]:
        """Os destinos do tipo dado que são Task."""
        destinos = (a.destino_id for a in self.view.obter_arestas_saida(id_no, tipo))
        return {id_destino for id_destino in destinos if self._eh_task(id_destino)}

    def _menor_destino(self, id_no: str, tipo: TipoAresta) -> str | None:
        """O destino de menor identificador entre as arestas do tipo; None sem nenhuma."""
        destinos = [aresta.destino_id for aresta in self.view.obter_arestas_saida(id_no, tipo)]
        return min(destinos) if destinos else None

    def _tem_motivo(self, id_no: str) -> bool:
        """O nó tem ao menos um `motivada_por`."""
        return bool(self.view.obter_arestas_saida(id_no, TipoAresta.MOTIVADA_POR))

    def _eh_task(self, id_no: str) -> bool:
        """O nó existe e é Task."""
        no = self.view.obter_no(id_no)
        return no is not None and no.tipo == TipoNo.TASK
