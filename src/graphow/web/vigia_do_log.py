"""Vigia que leva ao canal SSE os eventos escritos por outros processos.

O gancho pós-commit do kernel só enxerga o que este processo escreveu. O servidor
MCP roda em outro processo sobre o mesmo arquivo SQLite: o que o agente aceitava
chegava ao banco e nunca ao navegador, que só via a novidade com F5. O canal de
tempo real existia e estava correto — faltava alguém contando ao processo web que
o log tinha andado sem ele.

SQLite não notifica escritas entre processos, então a única leitura honesta é a
marca d'água: perguntar a maior sequência do ramo e dobrar apenas o delta.
"""

from collections.abc import Sequence
import sqlite3
import sys
import threading

from graphow.core.events import EventoLog
from graphow.storage.interfaces import RepositorioEventos
from graphow.storage.linhagem_ramo import RepositorioRamos, ResolvedorLinhagem
from graphow.web.sse_controller import SSEWebController

INTERVALO_PADRAO_DE_VARREDURA: float = 0.5
TEMPO_LIMITE_DE_PARADA: float = 2.0
NOME_DA_THREAD: str = "graphow-vigia-do-log"
PREFIXO_DO_AVISO: str = "AVISO [vigia-do-log]:"


class VigiaDoLogExterno:
    """Publica no canal de tempo real os eventos que entraram no log sem passar por aqui."""

    def __init__(
        self,
        repositorio: RepositorioEventos,
        controlador: SSEWebController,
        ramos: RepositorioRamos | None = None,
        *,
        intervalo_segundos: float = INTERVALO_PADRAO_DE_VARREDURA,
    ) -> None:
        self._repositorio: RepositorioEventos = repositorio
        self._controlador: SSEWebController = controlador
        self._resolvedor: ResolvedorLinhagem | None = (
            ResolvedorLinhagem(ramos) if ramos is not None else None
        )
        self._intervalo_segundos: float = intervalo_segundos
        self._marcas: dict[str, int] = {}
        self._parada: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def esta_ativo(self) -> bool:
        """Informa se a varredura de segundo plano está em curso."""
        return self._thread is not None and self._thread.is_alive()

    def iniciar(self) -> None:
        """Adota o log atual como já visto e passa a varrer o delta em segundo plano."""
        if self._thread is not None:
            return
        self.adotar_posicao_atual()
        self._parada.clear()
        self._thread = threading.Thread(target=self._laco, name=NOME_DA_THREAD, daemon=True)
        self._thread.start()

    def parar(self, timeout_segundos: float = TEMPO_LIMITE_DE_PARADA) -> None:
        """Sinaliza a parada e espera a thread de varredura encerrar."""
        self._parada.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=timeout_segundos)

    def adotar_posicao_atual(self) -> None:
        """Marca tudo que já existe como visto, para não republicar o passado.

        Sem isto, o primeiro navegador a conectar receberia o log inteiro como se
        fosse novidade.
        """
        for ramo_id in self._repositorio.listar_ramos():
            self._marcas[ramo_id] = self._repositorio.obter_ultimo_seq(ramo_id)

    def varrer(self) -> int:
        """Publica tudo que surgiu desde a última passada e devolve quantos eventos foram."""
        return sum(self._publicar_novidades_do_ramo(ramo_id) for ramo_id in self._repositorio.listar_ramos())

    def _laco(self) -> None:
        """Repete a varredura no intervalo configurado até chegar o sinal de parada."""
        while not self._parada.wait(self._intervalo_segundos):
            self._varrer_tolerando_falha_de_leitura()

    def _varrer_tolerando_falha_de_leitura(self) -> None:
        """Uma leitura que falha não pode derrubar a thread e calar o canvas para sempre.

        O caso previsto é o banco ocupado por outro processo além do `busy_timeout`.
        A varredura seguinte reencontra o mesmo delta: a marca d'água só avança
        depois que os eventos são despachados.
        """
        try:
            self.varrer()
        except (sqlite3.Error, OSError) as erro:
            sys.stderr.write(f"{PREFIXO_DO_AVISO} falha ao ler o log: {erro}\n")

    def _publicar_novidades_do_ramo(self, ramo_id: str) -> int:
        """Despacha os eventos do ramo posteriores à marca d'água guardada."""
        marca = self._marcas.get(ramo_id, self._seq_de_partida(ramo_id))
        seq_no_log = self._repositorio.obter_ultimo_seq(ramo_id)
        if seq_no_log <= marca:
            self._marcas[ramo_id] = min(marca, seq_no_log)
            return 0
        novos = self._repositorio.ler_eventos_desde_seq(ramo_id, marca)
        total = self._despachar(novos)
        self._marcas[ramo_id] = seq_no_log
        return total

    def _despachar(self, eventos: Sequence[EventoLog]) -> int:
        """Entrega o lote ao canal SSE, que descarta sozinho o que já publicou."""
        for evento in eventos:
            self._controlador.despachar_evento(evento)
        return len(eventos)

    def _seq_de_partida(self, ramo_id: str) -> int:
        """Ponto inicial de um ramo visto pela primeira vez: a sequência de corte herdada.

        Um fork guarda só os eventos próprios; o prefixo continua sendo lido do pai.
        Partir do zero republicaria esse prefixo inteiro como se fosse novidade.
        Sem o repositório de ramos não há como distinguir o herdado do próprio, e
        aí a escolha conservadora é adotar o ramo como já visto.
        """
        if self._resolvedor is None:
            return self._repositorio.obter_ultimo_seq(ramo_id)
        return self._resolvedor.obter_seq_corte(ramo_id)
