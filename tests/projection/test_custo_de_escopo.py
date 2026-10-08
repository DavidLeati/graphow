"""Testes do custo por raiz de cadeia: classes, alvos, Runs, reversões e profundidade."""

from typing import Any

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo, OrdemNoLog
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.classificacao_escopo import ClasseDeEscopo
from graphow.projection.custo_de_escopo import (
    custo_do_goal,
    profundidade_da_cadeia,
    tasks_desde_a_referencia,
)
from graphow.projection.graph_view import GrafoView

SEQ_DO_PLANO = 10
TARDE = 20


class _Grafo:
    """Montador de estado de teste: nós com `seq` de criação e arestas com id derivado."""

    def __init__(self, planos: list[dict[str, Any]] | None = None) -> None:
        self.nos: dict[str, NoGrafo] = {}
        self.arestas: dict[str, ArestaGrafo] = {}
        propriedades = {"planos": planos} if planos else {}
        self.no("g", TipoNo.GOAL, 1, **propriedades)
        self.no("crit", TipoNo.CONSTRAINT, 1, tipo="criterio_aceite").liga("crit", TipoAresta.ESCOPA, "g")

    def no(self, id_no: str, tipo_no: TipoNo, seq: int = TARDE, **propriedades: Any) -> "_Grafo":
        """Acrescenta um nó."""
        self.nos[id_no] = NoGrafo(
            id=id_no, tipo=tipo_no, rotulo=id_no, propriedades=propriedades, ordem=OrdemNoLog(seq_criacao=seq)
        )
        return self

    def liga(self, origem: str, tipo_aresta: TipoAresta, destino: str) -> "_Grafo":
        """Acrescenta uma aresta."""
        id_aresta = f"{origem}-{tipo_aresta.value}-{destino}"
        self.arestas[id_aresta] = ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo_aresta)
        return self

    def b3(self, id_task: str, motivo: str, seq: int = TARDE, **propriedades: Any) -> "_Grafo":
        """Task emergente de critério, sob o Goal e motivada por um nó."""
        self.no(id_task, TipoNo.TASK, seq, atende_criterio="crit", **propriedades)
        return self.liga("g", TipoAresta.DECOMPOE, id_task).liga(id_task, TipoAresta.MOTIVADA_POR, motivo)

    def view(self) -> GrafoView:
        """A vista sobre o que foi montado."""
        return GrafoView(GrafoEstado(nos=self.nos, arestas=self.arestas))


def _com_plano() -> _Grafo:
    """Goal com plano humano em SEQ_DO_PLANO, uma Task do plano e uma decisão de origem."""
    plano = [{"versao": 1, "seq": SEQ_DO_PLANO, "aprovado_por": "david", "papel": "humano"}]
    grafo = _Grafo(plano).no("d1", TipoNo.DECISION, 1)
    grafo.no("t-plano", TipoNo.TASK, 5).liga("g", TipoAresta.DECOMPOE, "t-plano")
    return grafo


def _custo(grafo: _Grafo, raiz: str) -> Any:
    """O custo de uma raiz do Goal."""
    return {custo.raiz: custo for custo in custo_do_goal(grafo.view(), "g")}[raiz]


def test_tasks_por_classe_e_alvos_da_raiz_nominal() -> None:
    """A raiz soma as Tasks por classe e une `arquivos_alvo` e `fonte`; a Task do plano fica de fora."""
    grafo = _com_plano()
    grafo.b3("t1", "d1", arquivos_alvo=["a.py", "b.py"]).b3("t2", "d1", arquivos_alvo=["b.py"], fonte="ata-12")
    grafo.no("t-sub", TipoNo.TASK).liga("t-plano", TipoAresta.DECOMPOE, "t-sub")

    custo = _custo(grafo, "d1")

    assert custo.tasks_por_classe == {"b3": 2}
    assert custo.alvos == ("a.py", "ata-12", "b.py")
    assert {task.id for task in tasks_desde_a_referencia(grafo.view(), "g")} == {"t1", "t2", "t-sub"}
    assert {task.id for task in custo.tasks} == {"t1", "t2"}


def test_correcao_e_integracao_herdam_a_raiz_da_task_de_origem_nominal() -> None:
    """A correção que `corrige` uma rejeição de Artifact de uma B3 é debitada na raiz dela."""
    grafo = _com_plano().b3("t1", "d1")
    grafo.no("art", TipoNo.ARTIFACT, 21).liga("art", TipoAresta.DERIVA_DE, "t1")
    grafo.no("ev-rej", TipoNo.EVIDENCE, 22, veredito="rejeitado").liga("ev-rej", TipoAresta.DERIVA_DE, "art")
    grafo.no("t-corr", TipoNo.TASK, 23, corrige="ev-rej").liga("g", TipoAresta.DECOMPOE, "t-corr")
    grafo.no("t-int", TipoNo.TASK, 24).liga("g", TipoAresta.DECOMPOE, "t-int").liga("t-int", TipoAresta.INTEGRA, "t1")

    custo = _custo(grafo, "d1")

    assert custo.tasks_por_classe == {"b3": 1, "correcao": 1, "integracao": 1}


def test_reversao_e_debitada_na_raiz_da_decisao_desfeita_nominal() -> None:
    """A Task que `desfaz` uma Decision substituída entra na raiz dela, ainda que não tenha `motivada_por`."""
    grafo = _com_plano().no("ev0", TipoNo.EVIDENCE, 1).no("d-velha", TipoNo.DECISION, 2).no("d-nova", TipoNo.DECISION, 3)
    grafo.liga("d-velha", TipoAresta.MOTIVADA_POR, "ev0").liga("d-nova", TipoAresta.SUBSTITUI, "d-velha")
    grafo.b3("t1", "d-velha")
    grafo.no("t-rev", TipoNo.TASK, 21).liga("g", TipoAresta.DECOMPOE, "t-rev").liga("t-rev", TipoAresta.DESFAZ, "d-velha")

    custo = _custo(grafo, "ev0")

    assert custo.tasks_por_classe == {"b3": 1, "reversao": 1}
    assert custo.reversoes == 1


def test_custo_dos_runs_divide_os_tokens_entre_as_tasks_do_run_nominal() -> None:
    """O Run que assumiu duas Tasks reparte os tokens entre elas; o Run sem Task não é de ninguém."""
    grafo = _com_plano().b3("t1", "d1").b3("t2", "d1").b3("t3", "d1")
    grafo.no("run-a", TipoNo.RUN, tarefas=["t1", "t2"], tokens_entrada=100, tokens_saida=50)
    grafo.no("run-b", TipoNo.RUN, tarefas=["t3"], tokens_entrada=30, tokens_cache_criacao=10)
    grafo.no("run-sessao", TipoNo.RUN, tokens_entrada=9999)

    custo = _custo(grafo, "d1")

    assert (custo.runs, custo.tokens) == (2, 75 + 75 + 40)


def test_run_sem_token_custa_zero_edge_case() -> None:
    """O Run que o harness não conseguiu medir conta como Run e soma zero."""
    grafo = _com_plano().b3("t1", "d1")
    grafo.no("run-a", TipoNo.RUN, tarefas=["t1"], tokens_entrada="muito")

    custo = _custo(grafo, "d1")

    assert (custo.runs, custo.tokens) == (1, 0)


def test_profundidade_da_cadeia_e_raiz_comum_nominal() -> None:
    """Duas Tasks de decisões encadeadas dividem a raiz; a profundidade é a maior cadeia."""
    grafo = _com_plano().no("d2", TipoNo.DECISION, 2).no("d3", TipoNo.DECISION, 3)
    grafo.liga("d3", TipoAresta.MOTIVADA_POR, "d2").liga("d2", TipoAresta.MOTIVADA_POR, "d1")
    grafo.b3("t1", "d3").b3("t2", "d1")

    custo = _custo(grafo, "d1")

    assert custo.profundidade == 3
    assert profundidade_da_cadeia(grafo.view(), "d1") == 0
    assert len(custo.emergentes) == 2


def test_ciclo_de_motivada_por_nao_trava_edge_case() -> None:
    """Um ciclo de `motivada_por` tem raiz estável e profundidade limitada."""
    grafo = _com_plano().no("d2", TipoNo.DECISION, 2).liga("d1", TipoAresta.MOTIVADA_POR, "d2")
    grafo.liga("d2", TipoAresta.MOTIVADA_POR, "d1").b3("t1", "d2")

    custos = custo_do_goal(grafo.view(), "g")

    assert [custo.raiz for custo in custos] == ["d1"]


def test_sem_plano_toda_task_entra_e_sem_motivo_e_a_propria_raiz_edge_case() -> None:
    """Sem referência humana toda Task conta, e a Task sem `motivada_por` é a raiz dela."""
    grafo = _Grafo().no("t1", TipoNo.TASK, 1).liga("g", TipoAresta.DECOMPOE, "t1")

    tasks = tasks_desde_a_referencia(grafo.view(), "g")

    assert [(task.raiz, task.classe) for task in tasks] == [("t1", ClasseDeEscopo.SEM_LIGACAO)]
