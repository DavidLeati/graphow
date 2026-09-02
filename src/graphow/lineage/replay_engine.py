"""Motor de Replay determinístico e cálculo de Diff entre ramificações."""

from dataclasses import dataclass
import threading
from typing import Any

from graphow.core.models import GrafoEstado
from graphow.projection.reducer import GrafoReducer
from graphow.storage.interfaces import RepositorioEventos


@dataclass(frozen=True)
class InstantaneoRamo:
    """Estado já reconstruído de um ramo até determinada sequência."""

    ramo_id: str
    seq: int
    estado: GrafoEstado


@dataclass(frozen=True)
class DiferencaEstrutural:
    """Comparação imutável entre dois estados projetados."""

    nos_adicionados: tuple[str, ...]
    nos_removidos: tuple[str, ...]
    nos_comuns: tuple[str, ...]
    arestas_adicionadas: tuple[str, ...]
    arestas_removidas: tuple[str, ...]

    def como_dicionario(self) -> dict[str, list[str]]:
        """Representação serializável para as camadas REST e de linha de comando."""
        return {
            "nos_adicionados": list(self.nos_adicionados),
            "nos_removidos": list(self.nos_removidos),
            "nos_comuns": list(self.nos_comuns),
            "arestas_adicionadas": list(self.arestas_adicionadas),
            "arestas_removidas": list(self.arestas_removidas),
        }


class ReplayEngine:
    """Motor para reconstrução pontual e comparação de linhagem de grafos.

    Guarda o último instantâneo por ramo: arrastar o controle de tempo para frente
    dobra apenas o delta, em vez de reler o log inteiro a cada tique. Ver F-09.
    """

    def __init__(self, repositorio: RepositorioEventos) -> None:
        self._repositorio: RepositorioEventos = repositorio
        self._instantaneos: dict[str, InstantaneoRamo] = {}
        self._lock: threading.RLock = threading.RLock()

    def reproduzir_ate_seq(self, ramo_id: str, seq_limite: int) -> GrafoEstado:
        """Recria o estado exato do grafo na sequência especificada."""
        with self._lock:
            instantaneo = self._obter_instantaneo_utilizavel(ramo_id, seq_limite)
            estado = self._avancar_ate(instantaneo, seq_limite)
            self._instantaneos[ramo_id] = InstantaneoRamo(ramo_id=ramo_id, seq=seq_limite, estado=estado)
            return estado

    def _obter_instantaneo_utilizavel(self, ramo_id: str, seq_limite: int) -> InstantaneoRamo:
        """Reaproveita o instantâneo anterior quando ele antecede a sequência pedida."""
        anterior = self._instantaneos.get(ramo_id)
        if anterior is not None and anterior.seq <= seq_limite:
            return anterior
        return InstantaneoRamo(ramo_id=ramo_id, seq=0, estado=GrafoEstado())

    def _avancar_ate(self, instantaneo: InstantaneoRamo, seq_limite: int) -> GrafoEstado:
        """Dobra sobre o instantâneo apenas os eventos que faltam para chegar ao alvo."""
        if instantaneo.seq == seq_limite:
            return instantaneo.estado
        eventos = self._ler_janela(instantaneo.ramo_id, instantaneo.seq, seq_limite)
        return GrafoReducer.aplicar_eventos(instantaneo.estado, eventos)

    def _ler_janela(self, ramo_id: str, seq_inicial: int, seq_limite: int) -> list[Any]:
        """Lê os eventos entre a marca do instantâneo e a sequência solicitada."""
        candidatos = self._repositorio.ler_eventos_desde_seq(ramo_id, seq_inicial)
        return [evento for evento in candidatos if evento.seq <= seq_limite]

    def reproduzir_ate_timestamp(self, ramo_id: str, timestamp_utc: str) -> GrafoEstado:
        """Recria o estado exato do grafo até o momento temporal informado."""
        eventos = [
            evento
            for evento in self._repositorio.ler_eventos(ramo_id)
            if evento.timestamp_utc <= timestamp_utc
        ]
        return GrafoReducer.reconstruir(eventos)

    def calcular_diff(self, estado_a: GrafoEstado, estado_b: GrafoEstado) -> dict[str, list[str]]:
        """Calcula diferenças estruturais entre dois estados (ex: comparação de forks)."""
        return self.comparar(estado_a, estado_b).como_dicionario()

    def comparar(self, estado_a: GrafoEstado, estado_b: GrafoEstado) -> DiferencaEstrutural:
        """Compara dois estados projetados devolvendo o resultado tipado."""
        nos_a, nos_b = set(estado_a.nos), set(estado_b.nos)
        arestas_a, arestas_b = set(estado_a.arestas), set(estado_b.arestas)
        return DiferencaEstrutural(
            nos_adicionados=tuple(sorted(nos_b - nos_a)),
            nos_removidos=tuple(sorted(nos_a - nos_b)),
            nos_comuns=tuple(sorted(nos_a & nos_b)),
            arestas_adicionadas=tuple(sorted(arestas_b - arestas_a)),
            arestas_removidas=tuple(sorted(arestas_a - arestas_b)),
        )
