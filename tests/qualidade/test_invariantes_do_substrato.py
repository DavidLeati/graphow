"""Invariantes do substrato, verificadas sobre sequências arbitrárias de patches.

Estes testes existem porque os limites de forma (400 linhas, 30 por função, 3
argumentos) não capturam nenhuma das falhas que a auditoria encontrou. O que
importa é o que precisa ser verdade depois de qualquer sequência de escritas.
"""

from collections.abc import Sequence
import random

import pytest

from graphow.core.exceptions import ErroConflitoDeSequencia
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.reducer import GrafoReducer

SEMENTES_EXAMINADAS: tuple[int, ...] = (1, 7, 13, 42, 99)
OPERACOES_POR_SEMENTE: int = 40

PAPEIS_DE_AGENTE: tuple[PapelAutor, ...] = (
    PapelAutor.PLANEJADOR,
    PapelAutor.EXECUTOR,
    PapelAutor.REVISOR,
)


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO):
    """Submete um lote de operações sob o papel informado."""
    dados = DadosPropostaPatch(
        autor="autor-de-teste",
        papel=papel,
        operacoes=tuple(operacoes),
        justificativa="sequencia arbitraria",
    )
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _operacao_de_no(id_no: str, tipo: TipoNo, propriedades: dict[str, str] | None = None) -> ItemPatch:
    """Operação de criação de nó com as propriedades informadas."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}},
    )


def _operacao_de_aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta tipada."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _executar_sequencia_arbitraria(kernel: WriteKernel, semente: int) -> None:
    """Aplica uma sequência pseudoaleatória, porém determinística, de mutações."""
    sorteador = random.Random(semente)
    for indice in range(OPERACOES_POR_SEMENTE):
        _aplicar_mutacao_sorteada(kernel, sorteador, indice)


def _aplicar_mutacao_sorteada(kernel: WriteKernel, sorteador: random.Random, indice: int) -> None:
    """Aplica uma mutação escolhida entre criar nó, ligar arestas ou remover."""
    escolha = sorteador.randint(0, 3)
    if escolha == 0:
        _submeter(kernel, [_operacao_de_no(f"task-{indice}", TipoNo.TASK, {"status": "pendente"})])
        return
    if escolha == 1:
        _submeter(kernel, [_operacao_de_no(f"note-{indice}", TipoNo.NOTE)])
        return
    if escolha == 2:
        _ligar_tarefas_existentes(kernel, sorteador, indice)
        return
    _remover_no_existente(kernel, sorteador)


def _ligar_tarefas_existentes(kernel: WriteKernel, sorteador: random.Random, indice: int) -> None:
    """Cria uma dependência entre duas tarefas já presentes, se houver duas."""
    tarefas = [no.id for no in kernel.obter_view().listar_nos_por_tipo(TipoNo.TASK)]
    if len(tarefas) < 2:
        return
    origem, destino = sorteador.sample(tarefas, 2)
    _submeter(kernel, [_operacao_de_aresta(f"dep-{indice}", origem, destino, TipoAresta.DEPENDE_DE)])


def _remover_no_existente(kernel: WriteKernel, sorteador: random.Random) -> None:
    """Remove um nó qualquer da projeção corrente, se houver algum."""
    existentes = [no.id for no in kernel.obter_view().listar_todos_os_nos()]
    if not existentes:
        return
    _submeter(kernel, [ItemPatch(op=OperacaoPatch.REMOVE, path=f"/nos/{sorteador.choice(existentes)}")])


@pytest.mark.parametrize("semente", SEMENTES_EXAMINADAS)
def test_replay_do_log_reproduz_a_projecao_corrente(semente: int) -> None:
    """Invariante central: o grafo é sempre uma dobra determinística do log."""
    kernel = montar_kernel_em_memoria()
    _executar_sequencia_arbitraria(kernel, semente)

    reconstruido: GrafoEstado = GrafoReducer.reconstruir(kernel.repositorio.ler_eventos("main"))
    assert reconstruido.serializar_para_json() == kernel.obter_estado("main").serializar_para_json()


@pytest.mark.parametrize("semente", SEMENTES_EXAMINADAS)
def test_sequencias_do_log_sao_contiguas_e_unicas(semente: int) -> None:
    """Invariante de ordenação: sem lacunas nem repetições, o replay é uma ordem total."""
    kernel = montar_kernel_em_memoria()
    _executar_sequencia_arbitraria(kernel, semente)

    sequencias = [evento.seq for evento in kernel.repositorio.ler_eventos("main")]
    assert sequencias == sorted(sequencias)
    assert sequencias == list(range(1, len(sequencias) + 1))


@pytest.mark.parametrize("semente", SEMENTES_EXAMINADAS)
def test_nenhuma_aresta_sobrevive_sem_suas_pontas(semente: int) -> None:
    """Invariante relacional: remover um nó não pode deixar aresta pendurada."""
    kernel = montar_kernel_em_memoria()
    _executar_sequencia_arbitraria(kernel, semente)

    estado = kernel.obter_estado("main")
    for aresta in estado.arestas.values():
        assert aresta.origem_id in estado.nos, aresta.id
        assert aresta.destino_id in estado.nos, aresta.id


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_nenhum_agente_fecha_tarefa_com_duvida_aberta(papel: PapelAutor) -> None:
    """Invariante de governança: vale para todo papel não humano, em qualquer ordem."""
    kernel = montar_kernel_em_memoria()
    _submeter(kernel, [_operacao_de_no("task-1", TipoNo.TASK, {"status": StatusTask.PENDENTE.value})])
    _submeter(
        kernel,
        [
            _operacao_de_no("quest-1", TipoNo.QUESTION, {"status": StatusQuestion.ABERTA.value}),
            _operacao_de_aresta("bloq-1", "quest-1", "task-1", TipoAresta.BLOQUEIA),
        ],
    )

    recibo = _submeter(
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
    assert recibo.sucesso is False
    assert kernel.obter_view().obter_no("task-1").obter_propriedade("status") != "concluido"


def test_lote_recusado_nao_deixa_efeito_parcial() -> None:
    """Invariante transacional: uma operação inválida no meio anula o lote inteiro."""
    kernel = montar_kernel_em_memoria()
    total_antes = len(kernel.repositorio.ler_eventos("main"))

    recibo = _submeter(
        kernel,
        [
            _operacao_de_no("valido-1", TipoNo.NOTE),
            _operacao_de_no("invalido", TipoNo.CONSTRAINT),
            _operacao_de_no("valido-2", TipoNo.NOTE),
        ],
        PapelAutor.EXECUTOR,
    )

    assert recibo.sucesso is False
    assert len(kernel.repositorio.ler_eventos("main")) == total_antes
    assert kernel.obter_view().contem_no("valido-1") is False


def test_colisao_de_sequencia_nunca_grava_metade_do_lote() -> None:
    """Invariante de durabilidade: o repositório recusa o lote inteiro na colisão."""
    kernel = montar_kernel_em_memoria()
    _submeter(kernel, [_operacao_de_no("n1", TipoNo.NOTE)])
    eventos_existentes = kernel.repositorio.ler_eventos("main")

    with pytest.raises(ErroConflitoDeSequencia):
        kernel.repositorio.append_eventos(eventos_existentes)

    assert len(kernel.repositorio.ler_eventos("main")) == len(eventos_existentes)


def test_ciclo_de_dependencia_nunca_entra_no_grafo() -> None:
    """Invariante estrutural: depende_de permanece acíclico sob qualquer ordem."""
    kernel = montar_kernel_em_memoria()
    for indice in range(4):
        _submeter(kernel, [_operacao_de_no(f"t{indice}", TipoNo.TASK)])
    for indice in range(3):
        _submeter(kernel, [_operacao_de_aresta(f"d{indice}", f"t{indice}", f"t{indice + 1}", TipoAresta.DEPENDE_DE)])

    fechamento_do_ciclo = _submeter(
        kernel, [_operacao_de_aresta("ciclo", "t3", "t0", TipoAresta.DEPENDE_DE)]
    )
    assert fechamento_do_ciclo.sucesso is False
    assert fechamento_do_ciclo.modo_de_falha == "ciclo_dependencia"
