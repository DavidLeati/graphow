"""Motor reativo que processa eventos e orquestra comportamentos desacoplados."""

from collections.abc import Sequence
from dataclasses import dataclass

from graphow.core.events import EventoLog
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.projection.graph_view import GrafoView
from graphow.reactive.diagnostico import ReacaoRecusada, RegistroDeReacoes, RegistroEmMemoria
from graphow.reactive.interfaces import ComportamentoReativo

LIMITE_DE_CASCATA_PADRAO: int = 3


@dataclass(frozen=True)
class ContextoReacao:
    """Estado imutável de uma rodada de avaliação de comportamentos reativos."""

    evento: EventoLog
    view: GrafoView
    profundidade: int


class MotorReativo:
    """Despachante reativo que escuta mutações de log e invoca comportamentos."""

    def __init__(
        self,
        kernel: WriteKernel,
        limite_cascata: int = LIMITE_DE_CASCATA_PADRAO,
        registro: RegistroDeReacoes | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._limite_cascata: int = limite_cascata
        self._registro: RegistroDeReacoes = registro or RegistroEmMemoria()
        self._comportamentos: dict[str, ComportamentoReativo] = {}

    def registrar_comportamento(self, comportamento: ComportamentoReativo) -> None:
        """Registra um novo comportamento reativo no motor."""
        self._comportamentos[comportamento.nome] = comportamento

    @property
    def comportamentos_registrados(self) -> tuple[str, ...]:
        """Nomes dos comportamentos ativos, em ordem estável de registro."""
        return tuple(self._comportamentos)

    @property
    def recusas_registradas(self) -> tuple[ReacaoRecusada, ...]:
        """Reações que o kernel recusou desde a construção do motor."""
        return self._registro.listar()

    def processar_evento(self, evento: EventoLog, profundidade: int = 0) -> list[str]:
        """Dispara avaliação para todos os comportamentos registrados sobre o evento."""
        if profundidade >= self._limite_cascata:
            return []
        contexto = ContextoReacao(
            evento=evento,
            view=self._kernel.obter_view(evento.ramo_id),
            profundidade=profundidade,
        )
        gerados: list[str] = []
        for comportamento in self._comportamentos.values():
            gerados.extend(self._reagir(comportamento, contexto))
        return gerados

    def _reagir(self, comportamento: ComportamentoReativo, contexto: ContextoReacao) -> tuple[str, ...]:
        """Avalia um comportamento e persiste a proposta resultante, se houver."""
        proposta = comportamento.avaliar(contexto.evento, contexto.view)
        if proposta is None:
            return ()
        recibo = self._kernel.submeter_patch(proposta)
        if not recibo.sucesso:
            self._anotar_recusa(comportamento.nome, contexto.evento.id, recibo)
            return ()
        return recibo.eventos_gerados + self._propagar_em_cascata(recibo.eventos_gerados, contexto)

    def _anotar_recusa(self, comportamento: str, id_evento: str, recibo: ResultadoSubmissao) -> None:
        """Guarda a recusa do kernel, para que a reação morta apareça em algum lugar."""
        self._registro.registrar(
            ReacaoRecusada(
                comportamento=comportamento,
                id_evento_gatilho=id_evento,
                mensagem=recibo.mensagem,
                modo_de_falha=recibo.modo_de_falha,
            )
        )

    def _propagar_em_cascata(
        self,
        ids_eventos: Sequence[str],
        contexto: ContextoReacao,
    ) -> tuple[str, ...]:
        """Reprocessa os eventos recém-gerados, respeitando o limite de profundidade."""
        derivados: list[str] = []
        for id_evento in ids_eventos:
            derivados.extend(self._reprocessar_evento_derivado(id_evento, contexto))
        return tuple(derivados)

    def _reprocessar_evento_derivado(self, id_evento: str, contexto: ContextoReacao) -> list[str]:
        """Busca o evento gerado e o submete a uma nova rodada de reações."""
        evento_derivado = self._kernel.obter_evento(id_evento)
        if evento_derivado is None:
            return []
        return self.processar_evento(evento_derivado, contexto.profundidade + 1)
