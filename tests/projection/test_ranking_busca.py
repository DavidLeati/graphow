"""Testes do ranking e do corte da busca textual."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import PapelAutor, StatusTask, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import (
    LIMITE_MAXIMO_DE_RESULTADOS,
    CASOU_NAS_PROPRIEDADES,
    CASOU_NO_ROTULO,
    CriterioBusca,
)
from graphow.projection.reducer import GrafoReducer


def _no(seq: int, id_no: str, tipo: str, rotulo: str, **propriedades: str) -> EventoLog:
    """Evento de criação de nó, com propriedades opcionais."""
    payload = {"id": id_no, "tipo": tipo, "rotulo": rotulo, "propriedades": dict(propriedades)}
    return EventoLog.criar(DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, payload))


def _montar_view(eventos: list[EventoLog]) -> GrafoView:
    """Monta a view a partir dos eventos informados."""
    return GrafoView(GrafoReducer.reconstruir(eventos))


def test_casamento_no_rotulo_vence_casamento_na_propriedade() -> None:
    """O rótulo é o que a pessoa escreveu para ser encontrado."""
    view = _montar_view([
        _no(1, "a", "Task", "Nada a ver", descricao="fala sobre cache"),
        _no(2, "b", "Task", "Camada de cache"),
    ])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache"))

    assert [item.no.id for item in resultado.itens] == ["b", "a"]
    assert resultado.itens[0].onde_casou == CASOU_NO_ROTULO
    assert resultado.itens[1].onde_casou == CASOU_NAS_PROPRIEDADES


def test_palavra_inteira_vence_prefixo_que_vence_substring() -> None:
    """Quanto mais exato o encontro, mais alto o resultado aparece."""
    view = _montar_view([
        _no(1, "substring", "Task", "Descache total"),
        _no(2, "prefixo", "Task", "Cacheamento agressivo"),
        _no(3, "inteira", "Task", "O cache do disco"),
    ])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache"))

    assert [item.no.id for item in resultado.itens] == ["inteira", "prefixo", "substring"]


def test_tarefa_aberta_aparece_antes_da_concluida() -> None:
    """Empatado o casamento, o que ainda pede trabalho vem primeiro."""
    view = _montar_view([
        _no(1, "feita", "Task", "Cache", status=StatusTask.CONCLUIDO.value),
        _no(2, "aberta", "Task", "Cache", status=StatusTask.PENDENTE.value),
    ])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache"))

    assert [item.no.id for item in resultado.itens] == ["aberta", "feita"]


def test_corte_preserva_o_total_e_anuncia_a_truncagem() -> None:
    """Sem o total, o agente não sabe que perdeu resultado."""
    view = _montar_view([_no(i, f"n{i}", "Task", f"cache {i}") for i in range(1, 9)])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache", limite=3))

    assert len(resultado.itens) == 3
    assert resultado.total_encontrado == 8
    assert resultado.truncado is True


def test_resultado_completo_nao_se_declara_truncado() -> None:
    """Quando tudo coube, `truncado` precisa dizer que nada faltou."""
    view = _montar_view([_no(1, "n1", "Task", "cache")])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache", limite=5))

    assert resultado.truncado is False
    assert resultado.em_dicionario()["exibidos"] == 1


def test_limite_e_saneado_entre_um_e_o_teto() -> None:
    """Limite absurdo não derruba a busca nem libera resposta ilimitada."""
    assert CriterioBusca(termo="x", limite=0).limite_efetivo == 1
    assert CriterioBusca(termo="x", limite=-9).limite_efetivo == 1
    assert CriterioBusca(termo="x", limite=10_000).limite_efetivo == LIMITE_MAXIMO_DE_RESULTADOS


def test_filtro_por_tipo_restringe_os_candidatos() -> None:
    """O filtro de tipo age antes do ranking, não depois do corte."""
    view = _montar_view([
        _no(1, "t", "Task", "cache"),
        _no(2, "d", "Decision", "cache"),
    ])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache", tipos=(TipoNo.DECISION,)))

    assert [item.no.id for item in resultado.itens] == ["d"]
    assert resultado.total_encontrado == 1


def test_termo_sem_correspondencia_devolve_pagina_vazia() -> None:
    """Nenhum resultado é uma resposta legítima, não um erro."""
    view = _montar_view([_no(1, "n1", "Task", "outra coisa")])

    resultado = view.buscar_ranqueado(CriterioBusca(termo="cache"))

    assert resultado.total_encontrado == 0
    assert resultado.itens == ()
    assert resultado.truncado is False


def test_ordem_e_estavel_entre_execucoes() -> None:
    """A mesma busca precisa devolver a mesma ordem sempre."""
    eventos = [_no(i, f"n{i}", "Task", "cache") for i in range(1, 6)]
    primeira = _montar_view(eventos).buscar_ranqueado(CriterioBusca(termo="cache", limite=5))
    segunda = _montar_view(eventos).buscar_ranqueado(CriterioBusca(termo="cache", limite=5))

    assert [i.no.id for i in primeira.itens] == [i.no.id for i in segunda.itens]
