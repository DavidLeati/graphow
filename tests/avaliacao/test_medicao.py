"""Testes do harness de avaliação: a métrica número um passa a ter número."""

from graphow.avaliacao import executar_avaliacao, montar_cenario_gravado
from graphow.avaliacao.medicao import MedicaoDaTarefa, MedidorDeTarefas
from graphow.avaliacao.relatorio import RelatorioDeAvaliacao
from graphow.avaliacao.tarefas_gravadas import ID_SESSAO, TAREFAS_GRAVADAS
from graphow.core.types import TipoNo


def test_corpus_tem_dez_tarefas_gravadas_nominal() -> None:
    """O plano pede dez tarefas reais gravadas; menos que isso não é corpus."""
    assert len(TAREFAS_GRAVADAS) == 10
    assert len({tarefa.id for tarefa in TAREFAS_GRAVADAS}) == 10


def test_cenario_e_reconstruido_de_forma_identica_nominal() -> None:
    """Medição que muda entre execuções não serve de linha de base."""
    primeiro = montar_cenario_gravado().obter_estado().serializar_para_json()
    segundo = montar_cenario_gravado().obter_estado().serializar_para_json()

    assert primeiro == segundo


def test_cenario_contem_a_sessao_e_todas_as_tarefas_nominal() -> None:
    """O corpus precisa existir no grafo, não só na estrutura de dados."""
    view = montar_cenario_gravado().obter_view()

    assert view.contem_no(ID_SESSAO) is True
    assert len(view.listar_nos_por_tipo(TipoNo.TASK)) == len(TAREFAS_GRAVADAS)


def test_medicao_cobre_todas_as_tarefas_nominal() -> None:
    """Cada tarefa gravada recebe uma medição própria."""
    medicoes = MedidorDeTarefas(montar_cenario_gravado()).medir_todas()

    assert len(medicoes) == len(TAREFAS_GRAVADAS)
    assert {m.id_tarefa for m in medicoes} == {t.id for t in TAREFAS_GRAVADAS}


def test_recorte_custa_menos_que_o_despejo_da_sessao_nominal() -> None:
    """É esta comparação que o ADR afirmava sem medir."""
    relatorio = executar_avaliacao()

    assert relatorio.tokens_por_tarefa_bem_sucedida < relatorio.tokens_por_tarefa_sem_grafo
    assert 0.0 < relatorio.reducao_media < 1.0


def test_metrica_conta_apenas_tarefas_concluidas_edge_case() -> None:
    """Caso de borda: a métrica é 'por tarefa bem-sucedida', não por tentativa."""
    relatorio = executar_avaliacao()

    assert len(relatorio.bem_sucedidas) < len(relatorio.medicoes)
    assert all(medicao.concluida for medicao in relatorio.bem_sucedidas)


def test_intervencao_humana_e_contada_na_tarefa_escalada_nominal() -> None:
    """A dúvida respondida pelo humano é a intervenção que o plano quer contar."""
    medicoes = {m.id_tarefa: m for m in MedidorDeTarefas(montar_cenario_gravado()).medir_todas()}

    assert medicoes["t09-escalacao"].intervencoes_humanas == 1
    assert medicoes["t01-parser"].intervencoes_humanas == 0


def test_relatorio_declara_os_proprios_limites_nominal() -> None:
    """O número viaja junto do que ele não prova. Ver A-15."""
    linhas = executar_avaliacao().formatar()
    texto = "\n".join(linhas)

    assert "Limites desta medicao" in texto
    assert "agente real" in texto
    assert "classe-de-caractere-v1" in texto


def test_reducao_de_medicao_sem_base_e_zero_edge_case() -> None:
    """Caso de borda: sem custo de referência, não se inventa economia."""
    medicao = MedicaoDaTarefa(
        id_tarefa="x", tokens_com_grafo=10, tokens_sem_grafo=0, intervencoes_humanas=0, concluida=True
    )

    assert medicao.reducao == 0.0


def test_relatorio_vazio_nao_divide_por_zero_edge_case() -> None:
    """Caso de borda: um corpus vazio devolve zero, não uma exceção."""
    relatorio = RelatorioDeAvaliacao.a_partir_de(())

    assert relatorio.tokens_por_tarefa_bem_sucedida == 0.0
    assert relatorio.intervencoes_por_tarefa == 0.0
