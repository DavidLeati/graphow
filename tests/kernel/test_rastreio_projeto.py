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
    """Caso de borda: mesmo com ciclo no caminho, o Projeto acessível é encontrado."""
    nos = {
        "proj": _no("proj", TipoNo.PROJETO),
        "a": _no("a", TipoNo.DECISION),
        "b": _no("b", TipoNo.DECISION),
    }
    arestas = {
        "ciclo1": _aresta("ciclo1", "a", "b", TipoAresta.SUBSTITUI),
        "ciclo2": _aresta("ciclo2", "b", "a", TipoAresta.SUBSTITUI),
        "contem": _aresta("contem", "proj", "b", TipoAresta.CONTEM),
    }
    assert RastreadorProjetoAncestral().rastrear("a", GrafoEstado(nos=nos, arestas=arestas)) == "proj"
