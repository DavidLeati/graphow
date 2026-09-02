"""Testes unitários para a projeção que reconcilia o cache com o log."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.projection.projecao_sincronizada import ProjecaoSincronizada
from graphow.storage.in_memory_store import InMemoryEventStore


def _evento_de_no(seq: int, id_no: str, ramo_id: str = "main") -> EventoLog:
    """Monta um evento de criação de nó com a sequência informada."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": id_no, "tipo": "Task", "rotulo": id_no},
        origem=OrigemEvento.HUMANO,
        ramo_id=ramo_id,
    )
    return EventoLog.criar(dados)


def test_primeira_consulta_reconstroi_do_log_nominal() -> None:
    """A projeção inicial vem inteira do repositório."""
    store = InMemoryEventStore()
    store.append_eventos([_evento_de_no(1, "n1"), _evento_de_no(2, "n2")])

    projecao = ProjecaoSincronizada(store).sincronizar("main")
    assert projecao.ultimo_seq_aplicado == 2
    assert projecao.estado.contem_no("n1") is True
    assert projecao.estado.contem_no("n2") is True


def test_eventos_posteriores_sao_incorporados_nominal() -> None:
    """Eventos gravados depois da primeira leitura entram na projeção seguinte."""
    store = InMemoryEventStore()
    sincronizada = ProjecaoSincronizada(store)
    store.append_evento(_evento_de_no(1, "n1"))
    assert sincronizada.obter_estado("main").contem_no("n1") is True

    store.append_evento(_evento_de_no(2, "n2"))
    estado = sincronizada.obter_estado("main")
    assert estado.contem_no("n2") is True
    assert len(estado.nos) == 2


def test_log_inalterado_devolve_a_mesma_projecao_edge_case() -> None:
    """Caso de borda: sem eventos novos, o estado é reaproveitado sem redobra."""
    store = InMemoryEventStore()
    store.append_evento(_evento_de_no(1, "n1"))
    sincronizada = ProjecaoSincronizada(store)

    primeira = sincronizada.sincronizar("main")
    segunda = sincronizada.sincronizar("main")
    assert primeira.estado is segunda.estado


def test_ramo_vazio_projeta_estado_zerado_edge_case() -> None:
    """Caso de borda: ramo sem eventos devolve projeção vazia com marca d'água zero."""
    projecao = ProjecaoSincronizada(InMemoryEventStore()).sincronizar("ramo-inexistente")
    assert projecao.ultimo_seq_aplicado == 0
    assert len(projecao.estado.nos) == 0


def test_log_encolhido_forca_reconstrucao_edge_case() -> None:
    """Caso de borda: se o log recuar (reparo de sequencias), a projeção é refeita do zero."""
    store = InMemoryEventStore()
    store.append_eventos([_evento_de_no(1, "n1"), _evento_de_no(2, "n2")])
    sincronizada = ProjecaoSincronizada(store)
    assert sincronizada.obter_estado("main").versao_log == 2

    store_reparado = InMemoryEventStore()
    store_reparado.append_evento(_evento_de_no(1, "n1"))
    projecao_reparada = ProjecaoSincronizada(store_reparado)
    assert projecao_reparada.obter_estado("main").versao_log == 1


def test_descarte_forca_releitura_completa_edge_case() -> None:
    """Caso de borda: descartar o ramo obriga a próxima consulta a reler o log."""
    store = InMemoryEventStore()
    sincronizada = ProjecaoSincronizada(store)
    store.append_evento(_evento_de_no(1, "n1"))
    primeira = sincronizada.sincronizar("main")

    sincronizada.descartar("main")
    segunda = sincronizada.sincronizar("main")
    assert primeira.estado is not segunda.estado
    assert segunda.estado.contem_no("n1") is True


def test_ramos_distintos_nao_se_contaminam() -> None:
    """Cada ramo mantém a própria projeção e a própria marca d'água."""
    store = InMemoryEventStore()
    store.append_evento(_evento_de_no(1, "n1", "main"))
    store.append_evento(_evento_de_no(1, "n9", "experimento"))
    sincronizada = ProjecaoSincronizada(store)

    assert sincronizada.obter_estado("main").contem_no("n9") is False
    assert sincronizada.obter_estado("experimento").contem_no("n1") is False
