"""Kernel de Escrita e Validação Transacional em 4 Portões (PatchBoard)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
import threading

from graphow.core.events import EventoLog
from graphow.core.exceptions import ErroConflitoDeSequencia
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.invariant_gate import InvariantGate
from graphow.kernel.observadores import DespachanteObservadores, ObservadorCommit
from graphow.kernel.patch_models import PropostaPatch, ResultadoValidacao
from graphow.kernel.role_gate import RoleGate
from graphow.kernel.schema_gate import SchemaGate
from graphow.kernel.telemetria import FatoDeEscrita, montar_span_de_execucao, montar_span_de_patch
from graphow.observability.mast_evaluator import DiagnosticoFalha, MASTEvaluator
from graphow.observability.tracer import Tracer, TracerNulo
from graphow.projection.graph_view import GrafoView
from graphow.projection.projecao_sincronizada import ProjecaoDoRamo, ProjecaoSincronizada
from graphow.projection.reducer import GrafoReducer
from graphow.storage.interfaces import RepositorioEventos, RepositorioLocks
from graphow.storage.linhagem_ramo import RepositorioRamos, RepositorioRamosEmMemoria
from graphow.storage.lock_store import LockStoreEmMemoria

# Um conflito significa que outro escritor ocupou a posição entre a validação e o
# commit. A resposta correta é revalidar contra o log já atualizado, não sobrescrever.
TENTATIVAS_MAXIMAS_DE_COMMIT: int = 4


@dataclass(frozen=True)
class ResultadoSubmissao:
    """Recibo imutável do resultado da submissão de um patch ao kernel."""

    sucesso: bool
    mensagem: str
    versao_log: int
    eventos_gerados: tuple[str, ...] = field(default_factory=tuple)
    diagnostico: DiagnosticoFalha | None = None

    @property
    def modo_de_falha(self) -> str | None:
        """Modo MAST da rejeicao, para o agente corrigir a proposta sem adivinhar."""
        return self.diagnostico.modo.value if self.diagnostico else None


@dataclass(frozen=True)
class DependenciasKernel:
    """Colaboradores injetáveis do kernel de escrita."""

    schema_gate: SchemaGate | None = None
    role_gate: RoleGate | None = None
    invariant_gate: InvariantGate | None = None
    repositorio_locks: RepositorioLocks | None = None
    repositorio_ramos: RepositorioRamos | None = None
    tracer: Tracer | None = None


class WriteKernel:
    """Orquestrador central de mutações por JSON Patch sobre o estado compartilhado."""

    def __init__(
        self,
        repositorio: RepositorioEventos,
        dependencias: DependenciasKernel | None = None,
    ) -> None:
        recursos = dependencias or DependenciasKernel()
        self._repositorio: RepositorioEventos = repositorio
        self._schema_gate: SchemaGate = recursos.schema_gate or SchemaGate()
        self._role_gate: RoleGate = recursos.role_gate or RoleGate()
        self._invariant_gate: InvariantGate = recursos.invariant_gate or InvariantGate()
        self._locks: RepositorioLocks = recursos.repositorio_locks or LockStoreEmMemoria()
        self._ramos: RepositorioRamos = recursos.repositorio_ramos or RepositorioRamosEmMemoria()
        self._tracer: Tracer = recursos.tracer or TracerNulo()
        self._projecoes: ProjecaoSincronizada = ProjecaoSincronizada(repositorio)
        self._conversor: ConversorPatchParaEventos = ConversorPatchParaEventos()
        self._observadores: DespachanteObservadores = DespachanteObservadores()
        self._lock_sincronizacao: threading.RLock = threading.RLock()

    def registrar_observador(self, observador: ObservadorCommit) -> None:
        """Inscreve um observador para receber os eventos aceitos pelos portões."""
        self._observadores.registrar(observador)

    @property
    def observadores_registrados(self) -> tuple[str, ...]:
        """Nomes dos observadores ativos, em ordem de registro."""
        return self._observadores.nomes_registrados

    def submeter_patch(self, proposta: PropostaPatch) -> ResultadoSubmissao:
        """Executa os 4 portões contra o log atual e persiste o lote atomicamente."""
        resultado = self._submeter_com_repeticao(proposta)
        self._tracer.registrar_span(montar_span_de_patch(proposta, _descrever(resultado)))
        return resultado

    def _submeter_com_repeticao(self, proposta: PropostaPatch) -> ResultadoSubmissao:
        """Revalida contra o log atualizado enquanto outro escritor ocupar a posição."""
        with self._lock_sincronizacao:
            for _ in range(TENTATIVAS_MAXIMAS_DE_COMMIT):
                resultado = self._tentar_submeter(proposta)
                if resultado is not None:
                    return resultado
            return ResultadoSubmissao(
                sucesso=False,
                mensagem="Conflito de escrita persistente: outro escritor avancou o log a cada tentativa",
                versao_log=self._repositorio.obter_ultimo_seq(proposta.ramo_id),
            )

    def _tentar_submeter(self, proposta: PropostaPatch) -> ResultadoSubmissao | None:
        """Uma rodada de validação e commit. Devolve None quando vale a pena repetir."""
        projecao = self._projecoes.sincronizar(proposta.ramo_id)
        validacao = self._executar_portoes(proposta, projecao.estado)
        if not validacao.aprovado:
            return _recibo_de_recusa(validacao, projecao.estado.versao_log)
        try:
            return self._aplicar_e_commitar(proposta, projecao)
        except ErroConflitoDeSequencia:
            self._projecoes.descartar(proposta.ramo_id)
            return None

    def _executar_portoes(self, proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
        """Aplica sequencialmente SchemaGate -> RoleGate -> InvariantGate."""
        resultado_schema = self._schema_gate.validar(proposta, estado)
        if not resultado_schema.aprovado:
            return resultado_schema
        resultado_role = self._role_gate.validar(proposta, estado)
        if not resultado_role.aprovado:
            return resultado_role
        return self._invariant_gate.validar(proposta, estado, self._locks.listar_locks())

    def _aplicar_e_commitar(
        self,
        proposta: PropostaPatch,
        projecao: ProjecaoDoRamo,
    ) -> ResultadoSubmissao:
        """Converte e projeta o lote antes de gravá-lo: só chega ao log o que se aplica ao grafo.

        A projeção vinha depois do `append_eventos`. Um lote que os portões
        aprovavam e o acumulador não sabia aplicar ficava gravado, e toda
        leitura seguinte do ramo estourava no mesmo evento.
        """
        try:
            eventos = self._conversor.converter(proposta, projecao.ultimo_seq_aplicado)
            estado_novo = GrafoReducer.aplicar_eventos(projecao.estado, eventos)
        except (KeyError, TypeError, ValueError) as erro:
            return _recusar_lote_que_nao_se_aplica(erro, projecao.estado.versao_log)
        if not eventos:
            return ResultadoSubmissao(
                sucesso=True,
                mensagem="Nenhuma operacao gerou evento",
                versao_log=projecao.estado.versao_log,
            )
        self._gravar_e_adotar(proposta.ramo_id, eventos, estado_novo)
        return ResultadoSubmissao(
            sucesso=True,
            mensagem="Patch validado e persistido com sucesso",
            versao_log=eventos[-1].seq,
            eventos_gerados=tuple(evento.id for evento in eventos),
        )

    def _gravar_e_adotar(
        self,
        ramo_id: str,
        eventos: Sequence[EventoLog],
        estado_novo: GrafoEstado,
    ) -> None:
        """Persiste eventos já projetados, adota o estado que eles produzem e avisa os observadores."""
        self._repositorio.append_eventos(eventos)
        self._projecoes.registrar_estado_recem_commitado(
            ramo_id, ProjecaoDoRamo(estado=estado_novo, ultimo_seq_aplicado=eventos[-1].seq)
        )
        self._observadores.notificar(eventos)

    def registrar_execucao(self, pedido: PedidoDeExecucao) -> ResultadoSubmissao:
        """Grava um fato de ciclo de vida de execução no log e notifica os observadores.

        Os quatro portões validam mutações propostas sobre nós e arestas. Um
        evento de execução não propõe mutação: ele registra que uma sessão de
        agente foi pedida, começou ou terminou. Ver `kernel/execucao.py`.
        """
        if not pedido.eh_de_ciclo_de_execucao:
            self._tracer.registrar_span(montar_span_de_execucao(pedido, False))
            return ResultadoSubmissao(
                sucesso=False,
                mensagem=f"Tipo de evento fora do ciclo de execucao: {pedido.tipo_evento.value}",
                versao_log=self._repositorio.obter_ultimo_seq(pedido.ramo_id),
            )
        with self._lock_sincronizacao:
            resultado = self._persistir_execucao(pedido)
        self._tracer.registrar_span(montar_span_de_execucao(pedido, resultado.sucesso))
        return resultado

    def _persistir_execucao(self, pedido: PedidoDeExecucao) -> ResultadoSubmissao:
        """Numera e projeta o evento de execução antes de persisti-lo, como faz com o lote."""
        projecao = self._projecoes.sincronizar(pedido.ramo_id)
        evento = pedido.montar_evento(projecao.ultimo_seq_aplicado + 1)
        estado_novo = GrafoReducer.aplicar_eventos(projecao.estado, (evento,))
        self._gravar_e_adotar(pedido.ramo_id, (evento,), estado_novo)
        return ResultadoSubmissao(
            sucesso=True,
            mensagem=f"Execucao registrada: {pedido.tipo_evento.value}",
            versao_log=evento.seq,
            eventos_gerados=(evento.id,),
        )

    def obter_estado(self, ramo_id: str = "main") -> GrafoEstado:
        """Consulta a projeção do ramo já reconciliada com o log persistido."""
        return self._projecoes.obter_estado(ramo_id)

    def obter_view(self, ramo_id: str = "main") -> GrafoView:
        """Fornece visão imutável CQRS do grafo, com o índice de rollup do ramo."""
        projecao = self._projecoes.sincronizar(ramo_id)
        return GrafoView(projecao.estado, projecao.indice)

    @property
    def repositorio(self) -> RepositorioEventos:
        """Repositório de eventos injetado, para colaboradores que leem o log cru."""
        return self._repositorio

    @property
    def repositorio_ramos(self) -> RepositorioRamos:
        """Repositório de linhagem de ramos injetado no kernel."""
        return self._ramos

    def obter_evento(self, id_evento: str) -> EventoLog | None:
        """Consulta um evento persistido pelo identificador, sem expor o repositório."""
        return self._repositorio.obter_evento_por_id(id_evento)

    def listar_ramos(self) -> tuple[str, ...]:
        """Enumera os ramos existentes no repositório de eventos."""
        return tuple(self._repositorio.listar_ramos())

    def obter_dono_do_lock(self, id_task: str) -> str | None:
        """Consulta quem detém a escrita exclusiva sobre a tarefa."""
        return self._locks.obter_dono(id_task)

    def listar_locks_ativos(self) -> dict[str, str]:
        """Instantâneo dos locks vigentes, para consultas que filtram por posse."""
        return dict(self._locks.listar_locks())

    def adquirir_lock_task(self, id_task: str, autor: str) -> bool:
        """Adquire lock exclusivo de escrita sobre uma Task para o autor."""
        return self._locks.tentar_adquirir(id_task, autor)

    def liberar_lock_task(self, id_task: str, autor: str) -> bool:
        """Libera o lock exclusivo caso pertença ao autor solicitante."""
        return self._locks.liberar(id_task, autor)


def _recibo_de_recusa(validacao: ResultadoValidacao, versao_log: int) -> ResultadoSubmissao:
    """Recibo de um lote recusado, com o diagnóstico MAST do modo que a recusa declarou."""
    return ResultadoSubmissao(
        sucesso=False,
        mensagem=validacao.mensagem_erro or "Patch rejeitado",
        versao_log=versao_log,
        diagnostico=MASTEvaluator.classificar_resultado(validacao),
    )


def _recusar_lote_que_nao_se_aplica(erro: KeyError | TypeError | ValueError, versao_log: int) -> ResultadoSubmissao:
    """Recusa, sem gravar nada, o lote que o conversor ou o acumulador não conseguem aplicar.

    É a rede atrás dos portões: se um deles deixar passar uma forma que a
    projeção não sabe dobrar, o lote volta recusado em vez de ficar no log.
    """
    validacao = ResultadoValidacao.falha(
        f"O lote nao se aplica ao grafo ({type(erro).__name__}: {erro}). Nada foi gravado",
        "WriteKernel",
        {"erro": type(erro).__name__},
        modo=ModoFalhaMAST.ESTRUTURA_INCOMPLETA,
    )
    return _recibo_de_recusa(validacao, versao_log)


def _descrever(resultado: ResultadoSubmissao) -> FatoDeEscrita:
    """Traduz o recibo do kernel nos campos crus que o span carrega."""
    return FatoDeEscrita(
        sucesso=resultado.sucesso,
        portao=resultado.diagnostico.portao if resultado.diagnostico else None,
        modo_de_falha=resultado.modo_de_falha,
        eventos_gerados=len(resultado.eventos_gerados),
    )
