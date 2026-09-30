"""O veredito vigente de uma tarefa: o último julgamento sobre ela ou sobre o que ela entregou."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, TipoAresta
from graphow.projection.graph_view import GrafoView
from graphow.projection.reducer import GrafoReducer
from graphow.projection.revisao import artefatos_da_tarefa, veredito_vigente


def _no(seq: int, id_no: str, tipo: str, **propriedades: str) -> EventoLog:
    """Evento de criação de nó, com propriedades opcionais."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": dict(propriedades)}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _deriva(seq: int, origem: str, destino: str) -> EventoLog:
    """Evento de criação da aresta `deriva_de` entre dois nós."""
    payload = {"id": f"{origem}->{destino}", "origem_id": origem, "destino_id": destino, "tipo": TipoAresta.DERIVA_DE.value}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.ARESTA_CRIADA, payload))


def _veredito(seq: int, id_no: str, veredito: str, alvo: str) -> list[EventoLog]:
    """A Evidence do revisor e a derivação dela, gravadas em sequência."""
    return [_no(seq, id_no, "Evidence", veredito=veredito), _deriva(seq + 1, id_no, alvo)]


def _view(*eventos: EventoLog) -> GrafoView:
    """A projeção dos eventos, com a tarefa e o artefato que ela entregou na frente."""
    base = [_no(1, "t1", "Task"), _no(2, "art-1", "Artifact"), _deriva(3, "art-1", "t1"), _no(4, "evi-teste", "Evidence")]
    return GrafoView(GrafoReducer.reconstruir([*base, _deriva(5, "evi-teste", "t1"), *eventos]))


def test_aprovacao_depois_da_rejeicao_vigora_nominal() -> None:
    """O julgamento mais novo é o que vale, venha ele pela Task ou pelo Artifact."""
    view = _view(*_veredito(10, "evi-rej", "rejeitado", "t1"), *_veredito(20, "evi-ok", "aprovado", "art-1"))

    assert artefatos_da_tarefa(view, "t1") == frozenset({"art-1"})
    assert veredito_vigente(view, "t1") == "aprovado"


def test_rejeicao_depois_da_aprovacao_vigora_edge_case() -> None:
    """Caso de borda: a ordem do log decide, não o identificador nem o valor do veredito."""
    view = _view(*_veredito(10, "evi-z-ok", "aprovado", "art-1"), *_veredito(20, "evi-a-rej", "rejeitado", "t1"))

    assert veredito_vigente(view, "t1") == "rejeitado"


def test_veredito_trocado_no_mesmo_no_vigora_edge_case() -> None:
    """Caso de borda: reescrever o veredito de uma Evidence antiga é um julgamento novo."""
    troca = EventoLog.criar(
        DadosCriacaoEvento(30, "david", PapelAutor.HUMANO, TipoEvento.NO_ATUALIZADO, {"id": "evi-1", "propriedades": {"veredito": "rejeitado"}})
    )
    view = _view(*_veredito(10, "evi-1", "aprovado", "t1"), *_veredito(20, "evi-2", "aprovado", "art-1"), troca)

    assert veredito_vigente(view, "t1") == "rejeitado"


def test_sem_revisao_nao_ha_veredito_edge_case() -> None:
    """Caso de borda: a Evidence do teste do executor não é veredito, e a tarefa segue sem julgamento."""
    assert veredito_vigente(_view(), "t1") == ""
