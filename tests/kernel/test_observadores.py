"""Testes unitários para o despacho de observadores pós-commit."""

from collections.abc import Sequence

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.kernel.observadores import DespachanteObservadores, ObservadorCommit


class ObservadorEspiao(ObservadorCommit):
    """Observador de teste que registra tudo o que recebe."""

    def __init__(self, nome: str) -> None:
        self._nome: str = nome
        self.lotes_recebidos: list[tuple[str, ...]] = []

    @property
    def nome(self) -> str:
        """Nome identificador informado na construção."""
        return self._nome

    def notificar(self, eventos: Sequence[EventoLog]) -> None:
        """Guarda os identificadores do lote recebido."""
        self.lotes_recebidos.append(tuple(evento.id for evento in eventos))


def _evento(seq: int) -> EventoLog:
    """Monta um evento mínimo com a sequência informada."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": f"n{seq}"},
        origem=OrigemEvento.HUMANO,
    )
    return EventoLog.criar(dados)


def test_notifica_todos_os_observadores_em_ordem_nominal() -> None:
    """Cada observador registrado recebe o mesmo lote, na ordem de registro."""
    despachante = DespachanteObservadores()
    primeiro = ObservadorEspiao("primeiro")
    segundo = ObservadorEspiao("segundo")
    despachante.registrar(primeiro)
    despachante.registrar(segundo)

    eventos = [_evento(1), _evento(2)]
    despachante.notificar(eventos)

    assert despachante.nomes_registrados == ("primeiro", "segundo")
    assert primeiro.lotes_recebidos == segundo.lotes_recebidos
    assert len(primeiro.lotes_recebidos[0]) == 2


def test_lote_vazio_nao_notifica_ninguem_edge_case() -> None:
    """Caso de borda: um patch sem eventos não acorda observador algum."""
    despachante = DespachanteObservadores()
    espiao = ObservadorEspiao("espiao")
    despachante.registrar(espiao)

    despachante.notificar([])
    assert espiao.lotes_recebidos == []


def test_sem_observadores_a_notificacao_e_inocua_edge_case() -> None:
    """Caso de borda: notificar sem ninguém inscrito não levanta erro."""
    DespachanteObservadores().notificar([_evento(1)])


def test_lista_de_nomes_e_um_instantaneo_imutavel_edge_case() -> None:
    """Caso de borda: a lista publicada não permite alterar o registro interno."""
    despachante = DespachanteObservadores()
    despachante.registrar(ObservadorEspiao("unico"))
    nomes = despachante.nomes_registrados
    assert isinstance(nomes, tuple)
    assert nomes == ("unico",)
