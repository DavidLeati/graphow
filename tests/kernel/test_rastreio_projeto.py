"""Testes unitários para o rastreio do Projeto ancestral resistente a ciclos."""

from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral


def _no(id_no: str, tipo: TipoNo) -> NoGrafo:
    """Cria um nó mínimo do tipo informado."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no)


def _aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Cria uma aresta tipada entre dois nós."""
    return ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo)


def _estado_hierarquico_completo() -> GrafoEstado:
    """Monta Projeto -> Setor -> Sessao -> Task, a hierarquia canônica de navegação."""
    nos = {
        "proj": _no("proj", TipoNo.PROJETO),
        "setor": _no("setor", TipoNo.SETOR),
        "sess": _no("sess", TipoNo.SESSAO),
        "task": _no("task", TipoNo.TASK),
    }
    arestas = {
        "a1": _aresta("a1", "proj", "setor", TipoAresta.CONTEM),
        "a2": _aresta("a2", "setor", "sess", TipoAresta.CONTEM),
        "a3": _aresta("a3", "sess", "task", TipoAresta.PRODUZ),
    }
    return GrafoEstado(nos=nos, arestas=arestas)


def test_encontra_projeto_a_tres_saltos_nominal() -> None:
    """A subida atravessa Sessao e Setor até alcançar o Projeto raiz."""
    assert RastreadorProjetoAncestral().rastrear("task", _estado_hierarquico_completo()) == "proj"


def test_projeto_rastreia_para_si_mesmo_nominal() -> None:
    """Um nó Projeto é seu próprio ancestral."""
    assert RastreadorProjetoAncestral().rastrear("proj", _estado_hierarquico_completo()) == "proj"


def test_no_inexistente_devolve_nulo_edge_case() -> None:
    """Caso de borda: identificador ausente do estado não gera erro."""
    assert RastreadorProjetoAncestral().rastrear("fantasma", _estado_hierarquico_completo()) is None


def test_no_orfao_sem_projeto_devolve_nulo_edge_case() -> None:
    """Caso de borda: nó desconectado da hierarquia não pertence a projeto algum."""
    estado = GrafoEstado(nos={"solto": _no("solto", TipoNo.NOTE)})
    assert RastreadorProjetoAncestral().rastrear("solto", estado) is None


def test_ciclo_em_arestas_nao_dag_nao_causa_recursao_infinita_edge_case() -> None:
    """Caso de borda: 'substitui' pode formar ciclo e a subida precisa terminar mesmo assim."""
    nos = {"d1": _no("d1", TipoNo.DECISION), "d2": _no("d2", TipoNo.DECISION)}
    arestas = {
        "s1": _aresta("s1", "d1", "d2", TipoAresta.SUBSTITUI),
        "s2": _aresta("s2", "d2", "d1", TipoAresta.SUBSTITUI),
    }
    assert RastreadorProjetoAncestral().rastrear("d1", GrafoEstado(nos=nos, arestas=arestas)) is None


def test_ciclo_com_projeto_alcancavel_ainda_encontra_o_projeto_edge_case() -> None:
    """Caso de borda: mesmo com ciclo de contenção no caminho, o Projeto acessível é encontrado."""
    nos = {
        "proj": _no("proj", TipoNo.PROJETO),
        "a": _no("a", TipoNo.DECISION),
        "b": _no("b", TipoNo.DECISION),
    }
    arestas = {
        "ciclo1": _aresta("ciclo1", "a", "b", TipoAresta.CONTEM),
        "ciclo2": _aresta("ciclo2", "b", "a", TipoAresta.CONTEM),
        "contem": _aresta("contem", "proj", "b", TipoAresta.CONTEM),
    }
    assert RastreadorProjetoAncestral().rastrear("a", GrafoEstado(nos=nos, arestas=arestas)) == "proj"


def test_aresta_fora_da_contencao_nao_leva_ao_projeto_edge_case() -> None:
    """Caso de borda: só a contenção sobe; orienta, deriva_de, substitui e bloqueia não decidem o Projeto."""
    nos_a, arestas_a = _hierarquia_de_um_projeto("a")
    nos_b, arestas_b = _hierarquia_de_um_projeto("b")
    nos = {**nos_a, **nos_b, "solto": _no("solto", TipoNo.DECISION), "alheia": _no("alheia", TipoNo.DECISION)}
    arestas = {**arestas_a, **arestas_b}
    arestas["x1"] = _aresta("x1", "proj-b", "solto", TipoAresta.SUBSTITUI)
    arestas["x2"] = _aresta("x2", "alheia", "task-a", TipoAresta.ORIENTA)
    arestas["x3"] = _aresta("x3", "proj-b", "alheia", TipoAresta.CONTEM)
    estado = GrafoEstado(nos=nos, arestas=arestas)

    assert RastreadorProjetoAncestral().rastrear("solto", estado) is None
    assert RastreadorProjetoAncestral().rastrear("task-a", estado) == "proj-a"
    assert RastreadorProjetoAncestral().rastrear("alheia", estado) == "proj-b"


def test_empate_de_projetos_no_mesmo_nivel_escolhe_o_menor_id_edge_case() -> None:
    """Caso de borda: dois Projetos contêm o nó no mesmo nível; vale o menor id, em qualquer ordem de arestas."""
    nos = {
        "proj-a": _no("proj-a", TipoNo.PROJETO),
        "proj-b": _no("proj-b", TipoNo.PROJETO),
        "task": _no("task", TipoNo.TASK),
    }
    de_a = _aresta("de-a", "proj-a", "task", TipoAresta.CONTEM)
    de_b = _aresta("de-b", "proj-b", "task", TipoAresta.CONTEM)

    b_primeiro = GrafoEstado(nos=nos, arestas={"de-b": de_b, "de-a": de_a})
    a_primeiro = GrafoEstado(nos=nos, arestas={"de-a": de_a, "de-b": de_b})

    assert RastreadorProjetoAncestral().rastrear("task", b_primeiro) == "proj-a"
    assert RastreadorProjetoAncestral().rastrear("task", a_primeiro) == "proj-a"


def test_projeto_mais_proximo_vence_o_de_id_menor_mais_distante_edge_case() -> None:
    """Caso de borda: o menor id só desempata dentro do mesmo nível; o Projeto mais próximo vence."""
    nos = {
        "proj-a": _no("proj-a", TipoNo.PROJETO),
        "proj-z": _no("proj-z", TipoNo.PROJETO),
        "sess": _no("sess", TipoNo.SESSAO),
        "task": _no("task", TipoNo.TASK),
    }
    arestas = {
        "p1": _aresta("p1", "sess", "task", TipoAresta.PRODUZ),
        "p2": _aresta("p2", "proj-a", "sess", TipoAresta.CONTEM),
        "p3": _aresta("p3", "proj-z", "task", TipoAresta.CONTEM),
    }

    assert RastreadorProjetoAncestral().rastrear("task", GrafoEstado(nos=nos, arestas=arestas)) == "proj-z"


def _hierarquia_de_um_projeto(sufixo: str) -> tuple[dict[str, NoGrafo], dict[str, ArestaGrafo]]:
    """Projeto, Sessao e Goal ligados por contem e produz, com a Task pendurada por decompoe."""
    nos = {
        f"proj-{sufixo}": _no(f"proj-{sufixo}", TipoNo.PROJETO),
        f"sess-{sufixo}": _no(f"sess-{sufixo}", TipoNo.SESSAO),
        f"goal-{sufixo}": _no(f"goal-{sufixo}", TipoNo.GOAL),
        f"task-{sufixo}": _no(f"task-{sufixo}", TipoNo.TASK),
    }
    arestas = {
        f"c-{sufixo}": _aresta(f"c-{sufixo}", f"proj-{sufixo}", f"sess-{sufixo}", TipoAresta.CONTEM),
        f"p-{sufixo}": _aresta(f"p-{sufixo}", f"sess-{sufixo}", f"goal-{sufixo}", TipoAresta.PRODUZ),
        f"d-{sufixo}": _aresta(f"d-{sufixo}", f"goal-{sufixo}", f"task-{sufixo}", TipoAresta.DECOMPOE),
    }
    return nos, arestas


def test_no_pendurado_por_contem_produz_e_decompoe_acha_o_seu_projeto_nominal() -> None:
    """Caso comum que a regra nova preserva: contem, produz e decompoe levam ao Projeto."""
    nos, arestas = _hierarquia_de_um_projeto("a")
    estado = GrafoEstado(nos=nos, arestas=arestas)

    for id_no in ("sess-a", "goal-a", "task-a"):
        assert RastreadorProjetoAncestral().rastrear(id_no, estado) == "proj-a", id_no


def test_dois_projetos_isolados_cada_no_acha_o_seu_nominal() -> None:
    """Dois Projetos sem aresta entre eles: cada Task acha o Projeto da própria hierarquia."""
    nos_a, arestas_a = _hierarquia_de_um_projeto("a")
    nos_b, arestas_b = _hierarquia_de_um_projeto("b")
    estado = GrafoEstado(nos={**nos_a, **nos_b}, arestas={**arestas_a, **arestas_b})

    assert RastreadorProjetoAncestral().rastrear("task-a", estado) == "proj-a"
    assert RastreadorProjetoAncestral().rastrear("task-b", estado) == "proj-b"
