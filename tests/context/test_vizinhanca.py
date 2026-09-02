"""Testes da seção de vizinhos: relevância na ordem e corte por tipo."""

from graphow.context.corte import LIMITES_DE_VIZINHOS_POR_TIPO, montar_escada_de_corte
from graphow.context.secoes import PrioridadeRetencao
from graphow.context.vizinhanca import montar_secao_de_vizinhos, ordenar_por_relevancia
from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, StatusTask, TipoNo


def _tarefa(id_no: str, status: str) -> NoGrafo:
    """Task de teste com o status informado."""
    return NoGrafo(id=id_no, tipo=TipoNo.TASK, rotulo=id_no, propriedades={"status": status})


def test_ordem_coloca_bloqueado_antes_de_concluido_nominal() -> None:
    """A ordem é de urgência: o que trava alguém aparece primeiro."""
    nos = [
        _tarefa("a-concluida", StatusTask.CONCLUIDO.value),
        _tarefa("b-pendente", StatusTask.PENDENTE.value),
        _tarefa("c-bloqueada", StatusTask.BLOQUEADO.value),
        _tarefa("d-andamento", StatusTask.EM_ANDAMENTO.value),
    ]

    ordenados = ordenar_por_relevancia(nos)

    assert [no.id for no in ordenados] == [
        "c-bloqueada",
        "d-andamento",
        "b-pendente",
        "a-concluida",
    ]


def test_questao_aberta_tem_a_mesma_urgencia_de_um_bloqueio_edge_case() -> None:
    """Caso de borda: dúvida aberta é o que trava o trabalho, e vem à frente."""
    questao = NoGrafo(
        id="q1",
        tipo=TipoNo.QUESTION,
        rotulo="Duvida",
        propriedades={"status": StatusQuestion.ABERTA.value},
    )
    ordenados = ordenar_por_relevancia([_tarefa("t1", StatusTask.PENDENTE.value), questao])

    assert [no.id for no in ordenados] == ["q1", "t1"]


def test_linha_de_vizinho_carrega_o_status_nominal() -> None:
    """O agente escolhia às cegas: a linha agora diz em que pé está cada vizinho."""
    secao = montar_secao_de_vizinhos([_tarefa("t1", StatusTask.BLOQUEADO.value)])

    assert "[bloqueado]" in secao.linhas[0]
    assert secao.prioridade_retencao == PrioridadeRetencao.NAVEGACAO


def test_secao_reduzida_mantem_um_por_tipo_e_anuncia_o_resto_nominal() -> None:
    """O corte é por dentro: sobra um exemplar e a contagem do que ficou fora."""
    secao = montar_secao_de_vizinhos([_tarefa(f"t{i}", StatusTask.PENDENTE.value) for i in range(10)])

    reduzida = secao.reduzida(1)

    assert len(reduzida.ids_incluidos) == 1
    assert "e mais 9 do tipo Task" in reduzida.linhas[-1]


def test_secao_sem_grupos_nao_encolhe_edge_case() -> None:
    """Caso de borda: seção sem grupos declarados devolve a si mesma."""
    secao = montar_secao_de_vizinhos([])

    assert secao.pode_encolher is False
    assert secao.reduzida(1) is secao


def test_escada_encolhe_vizinhos_antes_de_sacrificar_restricoes_nominal() -> None:
    """A ordem de renúncia está declarada em um lugar só, e é esta."""
    escada = montar_escada_de_corte()
    limites = [plano.limite_de_vizinhos for plano in escada]
    indice_do_ultimo_limite = max(i for i, limite in enumerate(limites) if limite is not None)
    indice_do_sacrificio = min(
        i
        for i, plano in enumerate(escada)
        if PrioridadeRetencao.RESTRICOES in plano.prioridades_descartadas
    )

    assert list(LIMITES_DE_VIZINHOS_POR_TIPO) == [
        limite for limite in limites if limite is not None
    ]
    assert indice_do_ultimo_limite < indice_do_sacrificio


def test_escada_comeca_sem_corte_algum_edge_case() -> None:
    """Caso de borda: o primeiro degrau entrega a vista inteira."""
    primeiro = montar_escada_de_corte()[0]

    assert primeiro.houve_corte is False
    assert primeiro.prioridades_descartadas == frozenset()
