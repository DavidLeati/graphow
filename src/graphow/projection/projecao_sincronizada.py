"""Projeção que reconsulta o log antes de responder, em vez de confiar num cache eterno.

Um cache que nunca reconsulta faz os quatro portões validarem contra um passado:
dois processos sobre o mesmo banco divergem para sempre. Ver auditoria F-04.
"""

from dataclasses import dataclass
import threading

from graphow.core.models import GrafoEstado
from graphow.projection.reducer import GrafoReducer
from graphow.storage.interfaces import RepositorioEventos


@dataclass(frozen=True)
class ProjecaoDoRamo:
    """Estado projetado de um ramo junto da marca d'água já aplicada."""

    estado: GrafoEstado
    ultimo_seq_aplicado: int


class ProjecaoSincronizada:
    """Mantém projeções por ramo alinhadas ao log, aplicando apenas o delta pendente."""

    def __init__(self, repositorio: RepositorioEventos) -> None:
        self._repositorio: RepositorioEventos = repositorio
        self._projecoes: dict[str, ProjecaoDoRamo] = {}
        self._lock: threading.RLock = threading.RLock()

    def obter_estado(self, ramo_id: str) -> GrafoEstado:
        """Consulta o estado do ramo já reconciliado com tudo que há no log."""
        return self.sincronizar(ramo_id).estado

    def sincronizar(self, ramo_id: str) -> ProjecaoDoRamo:
        """Aplica os eventos surgidos desde a última leitura e devolve a projeção."""
        with self._lock:
            projecao_atual = self._projecoes.get(ramo_id)
            if projecao_atual is None:
                return self._reconstruir_do_zero(ramo_id)
            return self._aplicar_delta_pendente(ramo_id, projecao_atual)

    def _reconstruir_do_zero(self, ramo_id: str) -> ProjecaoDoRamo:
        """Reconstrói o ramo inteiro a partir do log, na primeira consulta."""
        eventos = self._repositorio.ler_eventos(ramo_id)
        estado = GrafoReducer.reconstruir(eventos)
        seq_aplicado = eventos[-1].seq if eventos else 0
        return self._registrar(ramo_id, ProjecaoDoRamo(estado=estado, ultimo_seq_aplicado=seq_aplicado))

    def _aplicar_delta_pendente(self, ramo_id: str, projecao: ProjecaoDoRamo) -> ProjecaoDoRamo:
        """Consulta a marca d'água do log e dobra apenas os eventos novos."""
        seq_no_log = self._repositorio.obter_ultimo_seq(ramo_id)
        if seq_no_log == projecao.ultimo_seq_aplicado:
            return projecao
        if seq_no_log < projecao.ultimo_seq_aplicado:
            return self._reconstruir_do_zero(ramo_id)

        eventos_novos = self._repositorio.ler_eventos_desde_seq(ramo_id, projecao.ultimo_seq_aplicado)
        estado = GrafoReducer.aplicar_eventos(projecao.estado, eventos_novos)
        return self._registrar(ramo_id, ProjecaoDoRamo(estado=estado, ultimo_seq_aplicado=seq_no_log))

    def registrar_estado_recem_commitado(self, ramo_id: str, projecao: ProjecaoDoRamo) -> None:
        """Adota a projeção calculada pelo próprio kernel logo após o commit."""
        with self._lock:
            self._registrar(ramo_id, projecao)

    def _registrar(self, ramo_id: str, projecao: ProjecaoDoRamo) -> ProjecaoDoRamo:
        """Guarda a projeção como a versão corrente do ramo."""
        self._projecoes[ramo_id] = projecao
        return projecao

    def descartar(self, ramo_id: str) -> None:
        """Esquece a projeção do ramo, forçando reconstrução na próxima consulta."""
        with self._lock:
            self._projecoes.pop(ramo_id, None)
