"""Testes unitários para o WriteKernel e fluxo transacional."""

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import (
    DadosPropostaPatch,
    ItemPatch,
    OperacaoPatch,
    PropostaPatch,
    ResultadoValidacao,
)
from graphow.kernel.schema_gate import SchemaGate
from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore


def _operacoes_de_hierarquia() -> list[ItemPatch]:
    """Projeto, Setor e Sessao encadeados por `contem`, onde o trabalho se pendura."""
    return [
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/proj-1", value={"id": "proj-1", "tipo": TipoNo.PROJETO.value, "rotulo": "Projeto 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/setor-1", value={"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "Setor 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/c-setor-1", value={
            "id": "c-setor-1", "origem_id": "proj-1", "destino_id": "setor-1", "tipo": TipoAresta.CONTEM.value
        }),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/sess-1", value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao 1"}),
        ItemPatch(op=OperacaoPatch.ADD, path="/arestas/c-sess-1", value={
            "id": "c-sess-1", "origem_id": "setor-1", "destino_id": "sess-1", "tipo": TipoAresta.CONTEM.value
        }),
    ]


def test_write_kernel_submissao_nominal() -> None:
    """Testa submissão transacional nominal com criação de nó e aresta."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            *_operacoes_de_hierarquia(),
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/task-1", value={"id": "task-1", "tipo": TipoNo.TASK.value, "rotulo": "Task 1"}),
            ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value={
                "id": "e1", "origem_id": "sess-1", "destino_id": "task-1", "tipo": TipoAresta.PRODUZ.value
            }),
        ],
        justificativa="Inicialização do fluxo",
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is True
    # Projeto, Setor e as duas `contem` somam quatro eventos aos três originais.
    assert recibo.versao_log == 7
    assert len(recibo.eventos_gerados) == 7

    view = kernel.obter_view("main")
    assert view.total_nos == 4
    assert view.total_arestas == 3


def test_write_kernel_rejeicao_atomica_sem_efeitos_colaterais_edge_case() -> None:
    """Caso de borda: rejeição no portão não persiste nenhum evento e mantém estado intacto."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    # Submissão inválida por violação de papel
    dados_invalidos = DadosPropostaPatch(
        autor="executor-1",
        papel=PapelAutor.EXECUTOR,
        operacoes=[
            ItemPatch(op=OperacaoPatch.ADD, path="/nos/c1", value={"id": "c1", "tipo": TipoNo.CONSTRAINT.value}),
        ],
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados_invalidos))

    assert recibo.sucesso is False
    assert store.obter_ultimo_seq("main") == 0
    assert kernel.obter_view("main").total_nos == 0


def test_write_kernel_gestao_de_locks_edge_case() -> None:
    """Caso de borda: aquisição, bloqueio e liberação de lock exclusivo de Task."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)

    # Cria task
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=[
                    *_operacoes_de_hierarquia(),
                    ItemPatch(op=OperacaoPatch.ADD, path="/nos/t1", value={"id": "t1", "tipo": TipoNo.TASK.value}),
                    ItemPatch(op=OperacaoPatch.ADD, path="/arestas/p-t1", value={
                        "id": "p-t1", "origem_id": "sess-1", "destino_id": "t1", "tipo": TipoAresta.PRODUZ.value
                    }),
                ],
            )
        )
    )

    # Agente A adquire lock
    assert kernel.adquirir_lock_task("t1", "agente-a") is True
    # Agente B tenta adquirir lock sobre mesma task
    assert kernel.adquirir_lock_task("t1", "agente-b") is False

    # Agente B tenta submeter patch e é barrado
    recibo_b = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="agente-b",
                papel=PapelAutor.EXECUTOR,
                operacoes=[
                    ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/t1/propriedades/status", value=StatusTask.EM_ANDAMENTO.value),
                ],
            )
        )
    )
    assert recibo_b.sucesso is False
    assert "bloqueado para escrita" in recibo_b.mensagem

    # Agente A libera lock e agente B consegue adquirir
    assert kernel.liberar_lock_task("t1", "agente-a") is True
    assert kernel.adquirir_lock_task("t1", "agente-b") is True


class _SchemaGatePermissivo(SchemaGate):
    """Aprova tudo: faz o papel de um portão que deixou passar uma forma que a projeção não dobra."""

    def validar(self, proposta: PropostaPatch, estado: GrafoEstado) -> ResultadoValidacao:
        """Aprova o lote sem olhar."""
        return ResultadoValidacao.sucesso()


def test_lote_que_nao_se_aplica_e_recusado_sem_tocar_o_log_edge_case() -> None:
    """Caso de borda: a projeção vinha depois do `append_eventos` e o lote ruim ficava gravado.

    Com um portão que aprova tudo, a aresta de tipo inexistente chega ao
    acumulador, que estoura. O kernel projeta antes de gravar: o lote volta
    recusado, o log não anda e o ramo continua legível.
    """
    store = InMemoryEventStore()
    kernel = WriteKernel(store, DependenciasKernel(schema_gate=_SchemaGatePermissivo()))
    valor = {"id": "e1", "origem_id": "a", "destino_id": "b", "tipo": "tipo_fantasma"}
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[ItemPatch(op=OperacaoPatch.ADD, path="/arestas/e1", value=valor)],
    )

    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.ESTRUTURA_INCOMPLETA.value
    assert recibo.diagnostico is not None and recibo.diagnostico.portao == "WriteKernel"
    assert store.obter_ultimo_seq("main") == 0
    assert kernel.obter_view("main").total_arestas == 0
