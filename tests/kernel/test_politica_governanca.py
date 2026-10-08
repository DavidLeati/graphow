"""Testes da resolução da política de governança sobre o estado do grafo."""

from typing import Any

from graphow.core.governanca import ID_GOVERNANCA_GLOBAL, Gesto
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.politica_governanca import (
    resolver_politica_do_no,
    resolver_politica_do_projeto,
    resolver_politica_global,
)
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral


def _no(id_no: str, tipo: TipoNo, **propriedades: Any) -> NoGrafo:
    """Nó mínimo com as propriedades dadas."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades)


def _estado(*nos: NoGrafo, arestas: tuple[ArestaGrafo, ...] = ()) -> GrafoEstado:
    """Estado com os nós e as arestas dados."""
    return GrafoEstado(nos={no.id: no for no in nos}, arestas={aresta.id: aresta for aresta in arestas})


def _hierarquia(projeto: NoGrafo, *extras: NoGrafo) -> GrafoEstado:
    """Projeto -> Setor -> Sessao -> Task, mais os nós extras."""
    arestas = (
        ArestaGrafo(id="a1", origem_id=projeto.id, destino_id="setor", tipo=TipoAresta.CONTEM),
        ArestaGrafo(id="a2", origem_id="setor", destino_id="sess", tipo=TipoAresta.CONTEM),
        ArestaGrafo(id="a3", origem_id="sess", destino_id="task", tipo=TipoAresta.PRODUZ),
    )
    return _estado(
        projeto, _no("setor", TipoNo.SETOR), _no("sess", TipoNo.SESSAO), _no("task", TipoNo.TASK), *extras,
        arestas=arestas,
    )


def _global(**propriedades: Any) -> NoGrafo:
    """O nó singleton da política global."""
    return _no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA, **propriedades)


def test_sem_no_global_vale_governanca_maxima_nominal() -> None:
    """Grafo sem `governanca-global` resolve para governança máxima."""
    politica = resolver_politica_global(GrafoEstado())
    assert all(politica.valor(gesto) in ("humano", "estrito", 2, 3, 5, 0) for gesto in Gesto)
    assert not politica.estrutura_ilimitada


def test_no_global_com_preset_arbitragem_nominal() -> None:
    """O preset do nó global define a política global."""
    politica = resolver_politica_global(_estado(_global(preset="arbitragem_maxima")))
    assert politica.valor(Gesto.EXCLUIR) == "arbitro"
    assert politica.estrutura_ilimitada


def test_no_global_personalizada_parcial_nominal() -> None:
    """Personalizada parcial completa com governança máxima."""
    estado = _estado(_global(preset="personalizada", personalizada={"fechar_goal": "arbitro"}))
    politica = resolver_politica_global(estado)
    assert politica.valor(Gesto.FECHAR_GOAL) == "arbitro"
    assert politica.origem(Gesto.FECHAR_GOAL) == "global"
    assert politica.valor(Gesto.CONSTRAINT) == "humano"


def test_resolucao_ignora_personalizada_com_preset_fixo_edge_case() -> None:
    """Caso de borda: a personalizada preservada no nó não vale sob preset fixo."""
    estado = _estado(_global(preset="governanca_maxima", personalizada={"excluir": "arbitro"}))
    assert resolver_politica_global(estado).valor(Gesto.EXCLUIR) == "humano"


def test_no_com_o_id_global_mas_de_outro_tipo_e_ignorado_edge_case() -> None:
    """Caso de borda: só um nó do tipo Governanca vale como política global."""
    estado = _estado(_no(ID_GOVERNANCA_GLOBAL, TipoNo.NOTE, preset="arbitragem_maxima"))
    assert not resolver_politica_global(estado).estrutura_ilimitada


def test_projeto_herda_a_global_nominal() -> None:
    """Projeto sem `governanca` resolve para a global."""
    estado = _estado(_global(preset="arbitragem_maxima"), _no("proj", TipoNo.PROJETO))
    politica = resolver_politica_do_projeto("proj", estado)
    assert politica.valor(Gesto.EXCLUIR) == "arbitro"
    assert politica.origem(Gesto.EXCLUIR) == "global"


def test_projeto_preset_fixo_e_personalizada_parcial_nominal() -> None:
    """Preset fixo do projeto vale o preset; personalizada parcial sobrepõe a global."""
    estado = _estado(
        _global(preset="arbitragem_maxima"),
        _no("fixo", TipoNo.PROJETO, governanca={"preset": "governanca_maxima"}),
        _no("parcial", TipoNo.PROJETO, governanca={"preset": "personalizada", "personalizada": {"excluir": "humano"}}),
    )
    fixo = resolver_politica_do_projeto("fixo", estado)
    assert fixo.valor(Gesto.EXCLUIR) == "humano"
    assert fixo.origem(Gesto.EXCLUIR) == "preset:governanca_maxima"
    parcial = resolver_politica_do_projeto("parcial", estado)
    assert parcial.valor(Gesto.EXCLUIR) == "humano"
    assert parcial.origem(Gesto.EXCLUIR) == "projeto"
    assert parcial.valor(Gesto.CONSTRAINT) == "arbitro"


def test_legado_ilimitado_sem_governanca_e_com_preset_proprio_edge_case() -> None:
    """Caso de borda: o legado vale sem governança e deixa de valer com preset próprio."""
    estado = _estado(
        _no("legado", TipoNo.PROJETO, nivel_autonomia="ilimitado"),
        _no("herda", TipoNo.PROJETO, nivel_autonomia="ilimitado", governanca={"preset": "herdar"}),
        _no("proprio", TipoNo.PROJETO, nivel_autonomia="ilimitado", governanca={"preset": "governanca_maxima"}),
    )
    assert resolver_politica_do_projeto("legado", estado).origem(Gesto.ESTRUTURA) == "legado:nivel_autonomia"
    assert resolver_politica_do_projeto("herda", estado).estrutura_ilimitada
    assert not resolver_politica_do_projeto("proprio", estado).estrutura_ilimitada


def test_id_que_nao_e_projeto_resolve_para_a_global_edge_case() -> None:
    """Caso de borda: id inexistente ou de outro tipo cai na global."""
    estado = _estado(_global(preset="arbitragem_maxima"), _no("nota", TipoNo.NOTE))
    assert resolver_politica_do_projeto("fantasma", estado).estrutura_ilimitada
    assert resolver_politica_do_projeto("nota", estado).estrutura_ilimitada


def test_no_resolve_pela_politica_do_projeto_ancestral_nominal() -> None:
    """Uma Task resolve pela política do Projeto que a contém."""
    projeto = _no("proj", TipoNo.PROJETO, governanca={"preset": "arbitragem_maxima"})
    estado = _hierarquia(projeto, _global(preset="governanca_maxima"))
    politica = resolver_politica_do_no("task", estado, RastreadorProjetoAncestral())
    assert politica.valor(Gesto.EXCLUIR) == "arbitro"
    assert politica.origem(Gesto.EXCLUIR) == "preset:arbitragem_maxima"


def test_no_sem_projeto_cai_na_global_edge_case() -> None:
    """Caso de borda: nó solto, inexistente ou o próprio Governanca resolvem para a global."""
    estado = _estado(_global(preset="arbitragem_maxima"), _no("solta", TipoNo.NOTE))
    rastreador = RastreadorProjetoAncestral()
    for id_no in ("solta", "inexistente", ID_GOVERNANCA_GLOBAL):
        assert resolver_politica_do_no(id_no, estado, rastreador).estrutura_ilimitada
