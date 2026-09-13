"""Gerenciador de ramificações (Forks) sem cópia de prefixo de eventos."""

from dataclasses import dataclass

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.exceptions import ErroEntidadeNaoEncontrada, GraphowError
from graphow.core.models import GrafoEstado
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.projection.reducer import GrafoReducer
from graphow.storage.interfaces import RepositorioEventos
from graphow.storage.linhagem_ramo import DefinicaoRamo, RepositorioRamos


@dataclass(frozen=True)
class PedidoFork:
    """Parâmetros imutáveis de criação de uma ramificação."""

    ramo_origem: str
    id_evento_corte: str
    novo_ramo_id: str
    autor: str = "sistema"


class ForkManager:
    """Permite bifurcar o estado do grafo em qualquer ponto histórico de evento."""

    def __init__(self, repositorio: RepositorioEventos, repositorio_ramos: RepositorioRamos) -> None:
        self._repositorio: RepositorioEventos = repositorio
        self._ramos: RepositorioRamos = repositorio_ramos

    def criar_fork(self, pedido: PedidoFork) -> str:
        """Registra o ponteiro do novo ramo e marca a bifurcação no próprio log dele."""
        evento_corte = self._repositorio.obter_evento_por_id(pedido.id_evento_corte)
        if evento_corte is None:
            raise ErroEntidadeNaoEncontrada(
                f"Evento de corte '{pedido.id_evento_corte}' inexistente",
                {"id": pedido.id_evento_corte},
            )
        self._recusar_ramo_ja_existente(pedido.novo_ramo_id)
        self._ramos.registrar(
            DefinicaoRamo(
                ramo_id=pedido.novo_ramo_id,
                ramo_base=pedido.ramo_origem,
                seq_corte=evento_corte.seq,
                evento_corte_id=evento_corte.id,
            )
        )
        self._registrar_marco_de_criacao(pedido, evento_corte)
        return pedido.novo_ramo_id

    def _recusar_ramo_ja_existente(self, novo_ramo_id: str) -> None:
        """Impede que um fork sobrescreva um ramo que já possui história própria."""
        if novo_ramo_id not in set(self._repositorio.listar_ramos()):
            return
        raise GraphowError(
            f"O ramo '{novo_ramo_id}' ja existe e nao pode ser recriado por fork",
            {"ramo_id": novo_ramo_id},
        )

    def _registrar_marco_de_criacao(self, pedido: PedidoFork, evento_corte: EventoLog) -> None:
        """Grava no novo ramo o evento que documenta de onde ele veio."""
        dados = DadosCriacaoEvento(
            seq=evento_corte.seq + 1,
            autor=pedido.autor,
            papel=PapelAutor.SISTEMA,
            tipo_evento=TipoEvento.RAMO_CRIADO,
            payload={
                "ramo_origem": pedido.ramo_origem,
                "evento_corte_id": evento_corte.id,
                "seq_corte": evento_corte.seq,
            },
            origem=OrigemEvento.HUMANO,
            ramo_id=pedido.novo_ramo_id,
            parent_evento_id=evento_corte.id,
        )
        self._repositorio.append_evento(EventoLog.criar(dados))

    def obter_estado_fork(self, ramo_id: str) -> GrafoEstado:
        """Reconstrói a projeção do ramo bifurcado, herança inclusa."""
        return GrafoReducer.reconstruir(self._repositorio.ler_eventos(ramo_id))
