"""Invariante da ponte: só o humano encerra uma escalação, por qualquer caminho.

A garantia valia para o nome da ferramenta `responder_questao` e não para o
kernel: um executor trocava o status da Question por `propor_patch`, ou apagava
a Question, ou removia a aresta `bloqueia`, e a Task destravava. Este arquivo
percorre os três caminhos para cada papel de agente. Ver achados A-01 a A-03.
"""

from collections.abc import Sequence

import pytest

from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.matriz_papeis import DONOS_POR_TIPO_DE_ARESTA, obter_donos_de_aresta
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

PAPEIS_DE_AGENTE: tuple[PapelAutor, ...] = (
    PapelAutor.PLANEJADOR,
    PapelAutor.EXECUTOR,
    PapelAutor.REVISOR,
)

CAMINHOS_DE_FUGA: tuple[ItemPatch, ...] = (
    ItemPatch(
        op=OperacaoPatch.REPLACE,
        path="/nos/quest-1/propriedades/status",
        value=StatusQuestion.RESPONDIDA.value,
    ),
    ItemPatch(
        op=OperacaoPatch.REPLACE,
        path="/nos/quest-1/propriedades/status",
        value=StatusQuestion.DESCARTADA.value,
    ),
    ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/quest-1"),
    ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/bloq-1"),
)


def _submeter(
    kernel: WriteKernel,
    operacoes: Sequence[ItemPatch],
    papel: PapelAutor = PapelAutor.HUMANO,
) -> ResultadoSubmissao:
    """Submete um lote de operações sob o papel informado."""
    dados = DadosPropostaPatch(
        autor="autor-de-teste",
        papel=papel,
        operacoes=tuple(operacoes),
        justificativa="tentativa de encerrar a escalacao",
    )
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _montar_tarefa_bloqueada() -> WriteKernel:
    """Cria uma Task travada por uma Question aberta, tudo escrito pelo humano."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/task-1",
                value={
                    "id": "task-1",
                    "tipo": TipoNo.TASK.value,
                    "rotulo": "Tarefa travada",
                    "propriedades": {"status": StatusTask.PENDENTE.value},
                },
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/quest-1",
                value={
                    "id": "quest-1",
                    "tipo": TipoNo.QUESTION.value,
                    "rotulo": "Qual politica de eviccao?",
                    "propriedades": {"status": StatusQuestion.ABERTA.value},
                },
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/arestas/bloq-1",
                value={
                    "id": "bloq-1",
                    "origem_id": "quest-1",
                    "destino_id": "task-1",
                    "tipo": TipoAresta.BLOQUEIA.value,
                },
            ),
        ],
    )
    return kernel


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
@pytest.mark.parametrize("operacao", CAMINHOS_DE_FUGA)
def test_nenhum_agente_encerra_a_duvida_que_o_bloqueia(
    papel: PapelAutor,
    operacao: ItemPatch,
) -> None:
    """Invariante da escalação: nenhum caminho de fuga destrava a Task."""
    kernel = _montar_tarefa_bloqueada()

    recibo = _submeter(kernel, [operacao], papel)

    assert recibo.sucesso is False, operacao.path
    assert kernel.obter_view().esta_bloqueada("task-1") is True


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
@pytest.mark.parametrize("operacao", CAMINHOS_DE_FUGA)
def test_conclusao_em_dois_passos_tambem_falha(papel: PapelAutor, operacao: ItemPatch) -> None:
    """O caminho de dois passos — destravar e depois concluir — não existe mais."""
    kernel = _montar_tarefa_bloqueada()

    _submeter(kernel, [operacao], papel)
    fechamento = _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path="/nos/task-1/propriedades/status",
                value=StatusTask.CONCLUIDO.value,
            )
        ],
        papel,
    )

    assert fechamento.sucesso is False
    assert kernel.obter_view().obter_no("task-1").obter_propriedade("status") != "concluido"


def test_humano_encerra_a_duvida_e_a_tarefa_destrava_nominal() -> None:
    """A porta não foi apenas fechada: ela continua aberta para quem tem a chave."""
    kernel = _montar_tarefa_bloqueada()

    recibo = _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path="/nos/quest-1/propriedades/status",
                value=StatusQuestion.RESPONDIDA.value,
            )
        ],
    )

    assert recibo.sucesso is True
    assert kernel.obter_view().esta_bloqueada("task-1") is False


def test_todo_tipo_de_aresta_tem_dono_declarado() -> None:
    """Nenhum tipo de aresta pode existir sem um papel responsável por criá-la."""
    sem_dono = [tipo.value for tipo in TipoAresta if tipo not in DONOS_POR_TIPO_DE_ARESTA]
    assert not sem_dono, f"Tipos de aresta sem dono na matriz: {sem_dono}"


def test_todo_dono_declarado_inclui_o_humano_edge_case() -> None:
    """Caso de borda: uma aresta que o humano não pudesse criar seria ingovernável."""
    sem_humano = [
        tipo.value
        for tipo in TipoAresta
        if not obter_donos_de_aresta(tipo).autoriza(PapelAutor.HUMANO, eh_remocao=False)
    ]
    assert not sem_humano, sem_humano


def test_executor_nao_reescopa_a_propria_tarefa_edge_case() -> None:
    """Caso de borda: `escopa` é a aresta que amarra a restrição ao trabalho."""
    kernel = _montar_tarefa_bloqueada()
    _submeter(
        kernel,
        [
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/nos/const-1",
                value={"id": "const-1", "tipo": TipoNo.CONSTRAINT.value, "rotulo": "Zero deps"},
            ),
            ItemPatch(
                op=OperacaoPatch.ADD,
                path="/arestas/esc-1",
                value={
                    "id": "esc-1",
                    "origem_id": "const-1",
                    "destino_id": "task-1",
                    "tipo": TipoAresta.ESCOPA.value,
                },
            ),
        ],
    )

    remocao = _submeter(
        kernel,
        [ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/esc-1")],
        PapelAutor.EXECUTOR,
    )

    assert remocao.sucesso is False
    assert kernel.obter_view().contem_aresta("esc-1") is True
