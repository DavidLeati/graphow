"""Testes unitários para ForkManager: ramificação por ponteiro, sem cópia de prefixo."""

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.exceptions import ErroEntidadeNaoEncontrada, GraphowError
from graphow.core.types import PapelAutor, TipoNo
from graphow.lineage.fork_manager import ForkManager, PedidoFork
from graphow.storage.composicao import ConjuntoRepositorios, montar_repositorios_em_memoria


def _gravar_no(repositorios: ConjuntoRepositorios, seq: int, id_no: str, tipo: TipoNo) -> EventoLog:
    """Persiste um evento de criação de nó no ramo principal."""
    evento = EventoLog.criar(
        DadosCriacaoEvento(seq, "david", PapelAutor.HUMANO, TipoEvento.NO_CRIADO, {"id": id_no, "tipo": tipo.value})
    )
    repositorios.eventos.append_evento(evento)
    return evento


def _montar_cenario() -> tuple[ConjuntoRepositorios, ForkManager, EventoLog]:
    """Monta um ramo principal com três nós e devolve o evento do meio."""
    repositorios = montar_repositorios_em_memoria()
    _gravar_no(repositorios, 1, "n1", TipoNo.GOAL)
    evento_do_meio = _gravar_no(repositorios, 2, "n2", TipoNo.TASK)
    _gravar_no(repositorios, 3, "n3", TipoNo.TASK)
    return repositorios, ForkManager(repositorios.eventos, repositorios.ramos), evento_do_meio


def test_fork_manager_criacao_ramo_nominal() -> None:
    """A bifurcação enxerga o prefixo herdado e ignora o que veio depois do corte."""
    repositorios, manager, evento_do_meio = _montar_cenario()
    novo_ramo = manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))
    assert novo_ramo == "experimento-b"

    estado_fork = manager.obter_estado_fork("experimento-b")
    assert estado_fork.contem_no("n1") is True
    assert estado_fork.contem_no("n2") is True
    assert estado_fork.contem_no("n3") is False


def test_fork_nao_copia_o_prefixo_de_eventos_nominal() -> None:
    """O ramo derivado guarda apenas o próprio marco de criação."""
    repositorios, manager, evento_do_meio = _montar_cenario()
    manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))

    definicao = repositorios.ramos.obter_definicao("experimento-b")
    assert definicao is not None
    assert definicao.ramo_base == "main"
    assert definicao.seq_corte == 2

    eventos_visiveis = repositorios.eventos.ler_eventos("experimento-b")
    assert [evento.tipo_evento for evento in eventos_visiveis[-1:]] == [TipoEvento.RAMO_CRIADO]
    assert len(eventos_visiveis) == 3


def test_sequencias_do_ramo_derivado_nao_reiniciam_edge_case() -> None:
    """Caso de borda: o ramo continua a numeração, em vez de recomeçar em 1."""
    repositorios, manager, evento_do_meio = _montar_cenario()
    manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))

    sequencias = [evento.seq for evento in repositorios.eventos.ler_eventos("experimento-b")]
    assert sequencias == [1, 2, 3]
    assert len(sequencias) == len(set(sequencias))


def test_fork_manager_evento_inexistente_edge_case() -> None:
    """Caso de borda: bifurcar sobre evento inexistente lança erro de entidade."""
    repositorios = montar_repositorios_em_memoria()
    manager = ForkManager(repositorios.eventos, repositorios.ramos)
    with pytest.raises(ErroEntidadeNaoEncontrada):
        manager.criar_fork(PedidoFork("main", "evento-inexistente", "ramo-invalido"))


def test_fork_sobre_ramo_ja_existente_e_recusado_edge_case() -> None:
    """Caso de borda: recriar um ramo existente é recusado, não duplicado.

    Era exatamente isso que corrompia o banco: o segundo fork reiniciava o seq.
    """
    repositorios, manager, evento_do_meio = _montar_cenario()
    manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))
    with pytest.raises(GraphowError):
        manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))


def test_fork_de_fork_resolve_a_cadeia_completa_edge_case() -> None:
    """Caso de borda: bifurcar um ramo derivado herda também o prefixo do avô."""
    repositorios, manager, evento_do_meio = _montar_cenario()
    manager.criar_fork(PedidoFork("main", evento_do_meio.id, "filho"))
    eventos_do_filho = repositorios.eventos.ler_eventos("filho")

    manager.criar_fork(PedidoFork("filho", eventos_do_filho[-1].id, "neto"))
    estado_neto = manager.obter_estado_fork("neto")
    assert estado_neto.contem_no("n1") is True
    assert estado_neto.contem_no("n2") is True
    assert estado_neto.contem_no("n3") is False


def test_escrita_no_ramo_derivado_nao_afeta_a_origem() -> None:
    """Eventos próprios do fork ficam invisíveis para o ramo de origem."""
    repositorios, manager, evento_do_meio = _montar_cenario()
    manager.criar_fork(PedidoFork("main", evento_do_meio.id, "experimento-b"))

    seq_livre = repositorios.eventos.obter_ultimo_seq("experimento-b") + 1
    repositorios.eventos.append_evento(
        EventoLog.criar(
            DadosCriacaoEvento(
                seq_livre,
                "david",
                PapelAutor.HUMANO,
                TipoEvento.NO_CRIADO,
                {"id": "n-exclusivo", "tipo": TipoNo.NOTE.value},
                ramo_id="experimento-b",
            )
        )
    )
    assert manager.obter_estado_fork("experimento-b").contem_no("n-exclusivo") is True
    assert manager.obter_estado_fork("main").contem_no("n-exclusivo") is False
