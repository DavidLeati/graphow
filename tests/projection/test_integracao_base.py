"""O ramo base e os caminhos de colisão de um Goal, herdados do Setor e do Projeto."""

from typing import Any

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, TipoAresta
from graphow.projection.graph_view import GrafoView
from graphow.projection.integracao_base import IntegracaoDoGoal, cadeia_de_heranca, resolver_integracao
from graphow.projection.reducer import GrafoReducer

MIGRATIONS: list[str] = ["**/migrations/*.py"]


def _no(seq: int, id_no: str, tipo: str, propriedades: dict[str, Any]) -> EventoLog:
    """Evento de criação de nó com as propriedades dadas."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": propriedades}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _aresta(seq: int, origem: str, destino: str, tipo: TipoAresta) -> EventoLog:
    """Evento de criação de aresta entre dois nós."""
    payload = {"id": f"{origem}->{destino}", "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, payload))


def _view(projeto: dict[str, Any], setor: dict[str, Any], goal: dict[str, Any]) -> GrafoView:
    """Projeto contém Setor, que contém a Sessao que produziu o Goal, cada um com as propriedades dadas."""
    eventos = [
        _no(1, "proj", "Projeto", projeto),
        _no(2, "setor", "Setor", setor),
        _no(3, "sess", "Sessao", {}),
        _no(4, "goal", "Goal", goal),
        _aresta(5, "proj", "setor", TipoAresta.CONTEM),
        _aresta(6, "setor", "sess", TipoAresta.CONTEM),
        _aresta(7, "sess", "goal", TipoAresta.PRODUZ),
    ]
    return GrafoView(GrafoReducer.reconstruir(eventos))


def test_goal_herda_do_projeto_o_que_nao_traz_nominal() -> None:
    """Sem nada no Goal nem no Setor, vale o que o Projeto gravou, com a origem dita."""
    view = _view({"ramo_base": "origin/stage", "caminhos_de_colisao": MIGRATIONS}, {}, {})

    integracao = resolver_integracao(view, "goal")

    assert integracao == IntegracaoDoGoal("origin/stage", "proj", ("**/migrations/*.py",), "proj")


def test_setor_vence_o_projeto_e_goal_vence_o_setor_nominal() -> None:
    """O mais próximo do Goal vence, e cada propriedade se resolve por conta própria."""
    view = _view(
        {"ramo_base": "origin/main", "caminhos_de_colisao": MIGRATIONS},
        {"ramo_base": "origin/stage"},
        {"ramo_base": "release"},
    )

    integracao = resolver_integracao(view, "goal")

    assert (integracao.ramo_base, integracao.origem_do_ramo) == ("release", "goal")
    assert (integracao.caminhos_de_colisao, integracao.origem_dos_caminhos) == (("**/migrations/*.py",), "proj")


def test_setor_sem_ramo_passa_ao_projeto_edge_case() -> None:
    """Caso de borda: valor em branco no Setor é ausência, e a herança segue para o Projeto."""
    view = _view({"ramo_base": "stage"}, {"ramo_base": "  ", "caminhos_de_colisao": ["**/*.sql"]}, {})

    integracao = resolver_integracao(view, "goal")

    assert (integracao.ramo_base, integracao.origem_do_ramo) == ("stage", "proj")
    assert (integracao.caminhos_de_colisao, integracao.origem_dos_caminhos) == (("**/*.sql",), "setor")


def test_glob_solto_vira_lista_de_um_edge_case() -> None:
    """Caso de borda: o humano grava um glob só, como texto, e ele vale como lista."""
    view = _view({}, {}, {"ramo_base": "stage", "caminhos_de_colisao": "**/migrations/*.py"})

    assert resolver_integracao(view, "goal").caminhos_de_colisao == ("**/migrations/*.py",)


def test_ninguem_gravou_nada_edge_case() -> None:
    """Caso de borda: sem nenhuma das duas na herança, a integração volta vazia."""
    assert resolver_integracao(_view({}, {}, {}), "goal") == IntegracaoDoGoal()


def test_goal_inexistente_nao_tem_cadeia_edge_case() -> None:
    """Caso de borda: id que não existe devolve cadeia vazia, não exceção."""
    view = _view({"ramo_base": "stage"}, {}, {})

    assert cadeia_de_heranca(view, "goal-que-nao-existe") == ()
    assert resolver_integracao(view, "goal-que-nao-existe") == IntegracaoDoGoal()


def test_cadeia_sobe_da_sessao_ao_projeto_nominal() -> None:
    """A cadeia é o Goal, o Setor da sessão que o produziu e o Projeto do Setor, nessa ordem."""
    view = _view({}, {}, {})

    assert [no.id for no in cadeia_de_heranca(view, "goal")] == ["goal", "setor", "proj"]
