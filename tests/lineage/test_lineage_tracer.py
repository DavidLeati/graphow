"""Testes unitários para LineageTracer."""

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.lineage.lineage_tracer import CaminhoLinhagem, LineageTracer
from graphow.projection.graph_view import GrafoView


def test_lineage_tracer_caminho_completo_nominal() -> None:
    """Testa rastreamento causal de Artifact -> Task -> Goal."""
    nos = {
        "goal-1": NoGrafo("goal-1", TipoNo.GOAL, "Objetivo Raiz"),
        "task-1": NoGrafo("task-1", TipoNo.TASK, "Tarefa de Implementação"),
        "art-1": NoGrafo("art-1", TipoNo.ARTIFACT, "codigo.py"),
    }
    arestas = {
        "e1": ArestaGrafo("e1", "goal-1", "task-1", TipoAresta.DECOMPOE),
        "e2": ArestaGrafo("e2", "art-1", "task-1", TipoAresta.DERIVA_DE),
    }
    view = GrafoView(GrafoEstado(nos=nos, arestas=arestas))
    tracer = LineageTracer()

    caminho: CaminhoLinhagem = tracer.rastrear_linhagem("art-1", view)
    assert caminho.id_alvo == "art-1"
    assert caminho.goal_raiz is not None
    assert caminho.goal_raiz.id == "goal-1"
    assert len(caminho.nos_cadeia) >= 2


def test_lineage_tracer_alvo_sem_goal_edge_case() -> None:
    """Caso de borda: nó desconectado de Goal retorna trilha truncada sem erro."""
    nos = {"isolado": NoGrafo("isolado", TipoNo.NOTE, "Nota Solta")}
    view = GrafoView(GrafoEstado(nos=nos))
    tracer = LineageTracer()

    caminho = tracer.rastrear_linhagem("isolado", view)
    assert caminho.goal_raiz is None
    assert len(caminho.nos_cadeia) == 1


def test_lineage_tracer_decisao_substituida() -> None:
    """Testa rastreamento causal atravessando aresta de substituição."""
    nos = {
        "goal-1": NoGrafo("goal-1", TipoNo.GOAL, "Objetivo Persistencia"),
        "t-v1": NoGrafo("t-v1", TipoNo.TASK, "Task Original"),
        "t-v2": NoGrafo("t-v2", TipoNo.TASK, "Task Substituta"),
        "art-1": NoGrafo("art-1", TipoNo.ARTIFACT, "db.py"),
    }
    arestas = {
        "e_decomp": ArestaGrafo("e_decomp", "goal-1", "t-v1", TipoAresta.DECOMPOE),
        "e_subst": ArestaGrafo("e_subst", "t-v2", "t-v1", TipoAresta.SUBSTITUI),
        "e_deriv": ArestaGrafo("e_deriv", "art-1", "t-v2", TipoAresta.DERIVA_DE),
    }
    view = GrafoView(GrafoEstado(nos=nos, arestas=arestas))
    tracer = LineageTracer()

    caminho = tracer.rastrear_linhagem("art-1", view)
    assert caminho.goal_raiz is not None
    assert caminho.goal_raiz.id == "goal-1"
    assert [n.id for n in caminho.nos_cadeia] == ["art-1", "t-v2", "t-v1", "goal-1"]


def test_lineage_tracer_artefatos_encadeados_e_irmaos() -> None:
    """Testa rastreamento com artefatos encadeados e múltiplos nós irmãos."""
    nos = {
        "goal-1": NoGrafo("goal-1", TipoNo.GOAL, "Objetivo Engine"),
        "t-1": NoGrafo("t-1", TipoNo.TASK, "Task Engine"),
        "art-1": NoGrafo("art-1", TipoNo.ARTIFACT, "base.py"),
        "art-2": NoGrafo("art-2", TipoNo.ARTIFACT, "derived.py"),
        "art-sib": NoGrafo("art-sib", TipoNo.ARTIFACT, "other.py"),
    }
    arestas = {
        "e_sib": ArestaGrafo("e_sib", "art-sib", "t-1", TipoAresta.DERIVA_DE),
        "e_decomp": ArestaGrafo("e_decomp", "goal-1", "t-1", TipoAresta.DECOMPOE),
        "e_base": ArestaGrafo("e_base", "art-1", "t-1", TipoAresta.DERIVA_DE),
        "e_derived": ArestaGrafo("e_derived", "art-2", "art-1", TipoAresta.DERIVA_DE),
    }
    view = GrafoView(GrafoEstado(nos=nos, arestas=arestas))
    tracer = LineageTracer()

    caminho = tracer.rastrear_linhagem("art-2", view)
    assert caminho.goal_raiz is not None
    assert caminho.goal_raiz.id == "goal-1"
    assert [n.id for n in caminho.nos_cadeia] == ["art-2", "art-1", "t-1", "goal-1"]
