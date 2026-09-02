"""Testes unitários para o adaptador entre o kernel e o motor reativo."""

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.montagem import montar_comportamentos_padrao, montar_motor_reativo_padrao
from graphow.reactive.observador_reativo import ObservadorReativo
from graphow.storage.in_memory_store import InMemoryEventStore


def _kernel_com_reatividade() -> WriteKernel:
    """Monta um kernel com o motor reativo registrado como observador."""
    kernel = WriteKernel(InMemoryEventStore())
    kernel.registrar_observador(ObservadorReativo(montar_motor_reativo_padrao(kernel)))
    return kernel


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch]) -> None:
    """Submete operações sob a identidade humana."""
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=tuple(operacoes), justificativa="teste"
    )
    kernel.submeter_patch(PropostaPatch.criar(dados))


def _criar_task(kernel: WriteKernel, id_task: str) -> None:
    """Cria uma Sessao e a Task pendente que ela produz.

    A nota reativa nasce presa à sessão e ao alvo: sem a sessão no grafo ela
    seria órfã, e uma nota órfã não aparece na vista de ninguém. Ver A-10.
    """
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/sess-1",
                value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao"},
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/nos/{id_task}",
                value={
                    "id": id_task,
                    "tipo": TipoNo.TASK.value,
                    "rotulo": "Tarefa",
                    "propriedades": {"status": StatusTask.PENDENTE.value},
                },
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path=f"/arestas/prod-{id_task}",
                value={
                    "id": f"prod-{id_task}",
                    "origem_id": "sess-1",
                    "destino_id": id_task,
                    "tipo": TipoAresta.PRODUZ.value,
                },
            ),
        ],
    )


def test_comportamento_dispara_sem_chamada_manual_nominal() -> None:
    """A reação acontece pelo gancho do kernel, sem ninguém acionar o motor."""
    kernel = _kernel_com_reatividade()
    _criar_task(kernel, "task-1")
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path="/nos/task-1/propriedades/status",
                value=StatusTask.PRONTO_PARA_REVISAO.value,
            )
        ],
    )

    notas = kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    assert len(notas) == 1
    assert "Revis" in notas[0].rotulo


def test_comportamentos_padrao_estao_todos_registrados_nominal() -> None:
    """A montagem padrão ativa os comportamentos nativos declarados."""
    motor = montar_motor_reativo_padrao(WriteKernel(InMemoryEventStore()))
    assert len(motor.comportamentos_registrados) == len(montar_comportamentos_padrao())
    assert "RevisorNotificado" in motor.comportamentos_registrados


def test_reentrancia_nao_duplica_reacoes_edge_case() -> None:
    """Caso de borda: a reação submete um patch e não pode reagir a si mesma em duplicidade."""
    kernel = _kernel_com_reatividade()
    _criar_task(kernel, "task-1")
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path="/nos/task-1/propriedades/status",
                value=StatusTask.PRONTO_PARA_REVISAO.value,
            )
        ],
    )
    assert len(kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)) == 1


def test_evento_irrelevante_nao_gera_reacao_edge_case() -> None:
    """Caso de borda: um evento que nenhum comportamento observa não muda o grafo."""
    kernel = _kernel_com_reatividade()
    _criar_task(kernel, "task-1")
    assert kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE) == []


def test_observador_ignora_lote_vazio_edge_case() -> None:
    """Caso de borda: notificar com lote vazio não aciona o motor."""
    kernel = WriteKernel(InMemoryEventStore())
    observador = ObservadorReativo(montar_motor_reativo_padrao(kernel))
    observador.notificar([])
    assert kernel.obter_view().total_nos == 0


def test_nome_do_observador_identifica_o_motor() -> None:
    """O nome publicado permite auditar quem está inscrito no kernel."""
    kernel = WriteKernel(InMemoryEventStore())
    assert ObservadorReativo(montar_motor_reativo_padrao(kernel)).nome == "MotorReativo"


def _evento_qualquer() -> EventoLog:
    """Monta um evento avulso para verificações diretas do adaptador."""
    dados = DadosCriacaoEvento(
        seq=1,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": "n1", "tipo": TipoNo.NOTE.value, "rotulo": "Nota"},
        origem=OrigemEvento.HUMANO,
    )
    return EventoLog.criar(dados)


def test_notificacao_direta_nao_levanta_erro() -> None:
    """O adaptador aceita eventos que não correspondem a nenhum comportamento."""
    kernel = WriteKernel(InMemoryEventStore())
    ObservadorReativo(montar_motor_reativo_padrao(kernel)).notificar([_evento_qualquer()])
