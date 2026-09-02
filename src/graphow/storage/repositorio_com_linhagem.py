"""Repositório de eventos que compõe a leitura de um ramo com a herança do pai.

Um ramo derivado guarda apenas os próprios eventos; o prefixo continua a ser lido
do ramo de origem, até a sequência de corte. É o que torna o fork barato e o que
elimina a renumeração que corrompia o log. Ver auditoria F-06.
"""

from collections.abc import Sequence

from graphow.core.events import EventoLog
from graphow.storage.interfaces import RepositorioEventos
from graphow.storage.linhagem_ramo import RepositorioRamos, ResolvedorLinhagem


class RepositorioEventosComLinhagem(RepositorioEventos):
    """Decorador que resolve a herança entre ramos em toda leitura do log."""

    def __init__(self, repositorio_base: RepositorioEventos, repositorio_ramos: RepositorioRamos) -> None:
        self._base: RepositorioEventos = repositorio_base
        self._ramos: RepositorioRamos = repositorio_ramos
        self._resolvedor: ResolvedorLinhagem = ResolvedorLinhagem(repositorio_ramos)

    def append_evento(self, evento: EventoLog) -> None:
        """Grava o evento como próprio do ramo informado."""
        self._base.append_evento(evento)

    def append_eventos(self, eventos: Sequence[EventoLog]) -> None:
        """Grava o lote como eventos próprios do ramo informado."""
        self._base.append_eventos(eventos)

    def ler_eventos(self, ramo_id: str = "main") -> list[EventoLog]:
        """Lê o prefixo herdado seguido dos eventos próprios, em ordem de sequência."""
        return self._compor(ramo_id, seq_minimo=0, seq_maximo=None)

    def ler_eventos_ate_seq(self, ramo_id: str, seq_limite: int) -> list[EventoLog]:
        """Lê a composição do ramo até a sequência limite inclusive."""
        return self._compor(ramo_id, seq_minimo=0, seq_maximo=seq_limite)

    def ler_eventos_desde_seq(self, ramo_id: str, seq_exclusivo: int) -> list[EventoLog]:
        """Lê a composição do ramo a partir da sequência informada, exclusive."""
        return self._compor(ramo_id, seq_minimo=seq_exclusivo, seq_maximo=None)

    def _compor(self, ramo_id: str, seq_minimo: int, seq_maximo: int | None) -> list[EventoLog]:
        """Junta o prefixo herdado com os eventos próprios e ordena por sequência."""
        seq_corte = self._resolvedor.obter_seq_corte(ramo_id)
        herdados = self._ler_prefixo_herdado(ramo_id, seq_corte)
        proprios = self._base.ler_eventos(ramo_id)
        na_janela = [
            evento
            for evento in herdados + proprios
            if evento.seq > seq_minimo and (seq_maximo is None or evento.seq <= seq_maximo)
        ]
        return sorted(na_janela, key=lambda evento: evento.seq)

    def _ler_prefixo_herdado(self, ramo_id: str, seq_corte: int) -> list[EventoLog]:
        """Lê do ramo de origem tudo o que este ramo herda, já recursivamente composto."""
        definicao = self._ramos.obter_definicao(ramo_id)
        if definicao is None or seq_corte <= 0:
            return []
        return self.ler_eventos_ate_seq(definicao.ramo_base, seq_corte)

    def obter_ultimo_seq(self, ramo_id: str = "main") -> int:
        """Maior sequência visível no ramo, contando o que ele herdou."""
        return max(self._base.obter_ultimo_seq(ramo_id), self._resolvedor.obter_seq_corte(ramo_id))

    def listar_ramos(self) -> list[str]:
        """Lista os ramos com eventos próprios somados aos ramos apenas declarados."""
        com_eventos = set(self._base.listar_ramos())
        declarados = set(self._ramos.listar_ramos_derivados())
        return sorted(com_eventos | declarados)

    def obter_evento_por_id(self, id_evento: str) -> EventoLog | None:
        """Busca um evento pelo identificador no repositório subjacente."""
        return self._base.obter_evento_por_id(id_evento)
