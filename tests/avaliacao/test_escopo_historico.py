"""Regressão do escopo governado sobre logs reais anonimizados: os números da validação da seção 7, fixados.

O corpus (`tests/avaliacao/dados/corpus_escopo.jsonl.gz`) tem três Goals: 12 para 14
Tasks, 5 para 35 e 3 para 100. Cada teste fixa uma medição da regressão; quando
o placar, o classificador ou a fila mudarem de comportamento, o número que mexer
aponta onde. Os ids são os do corpus anonimizado.
"""

import pytest

from graphow.avaliacao.corpus_escopo import carregar_corpus
from graphow.avaliacao.escopo_historia import JANELA_DO_LOTE_SEGUNDOS, historia_do_goal
from graphow.avaliacao.escopo_historico import MedicaoDeEscopo, MedicaoDoGoal, medir_escopo
from graphow.avaliacao.relatorio_escopo import SECAO_7, formatar_relatorio

CONDUZIDO: str = "goal-7414f9"
ONDAS: str = "goal-a54cf5"
CONTINUO: str = "goal-3e94e8"


@pytest.fixture(scope="module")
def medicao() -> MedicaoDeEscopo:
    """A regressão inteira, medida uma vez para o módulo."""
    return medir_escopo()


def _goal(medicao: MedicaoDeEscopo, id_goal: str) -> MedicaoDoGoal:
    """A medição de um Goal do corpus."""
    return next(goal for goal in medicao.goals if goal.id_goal == id_goal)


def test_plano_aproximado_bate_com_a_linha_de_base_nominal(medicao: MedicaoDeEscopo) -> None:
    """O plano é o das Tasks que existiam na primeira ida a `em_andamento`: 12, 5 e 3, como na seção 2."""
    tamanhos = {goal.id_goal: (goal.plano, goal.total) for goal in medicao.goals}
    assert tamanhos == {CONDUZIDO: (12, 14), ONDAS: (5, 35), CONTINUO: (3, 100)}
    assert [goal.id_goal for goal in medicao.goals] == [CONDUZIDO, ONDAS, CONTINUO]


def test_lotes_de_criacao_depois_do_plano_nominal(medicao: MedicaoDeEscopo) -> None:
    """Autor sem pausa maior que a janela é um lote; o mesmo segundo não serve porque o log carimba cada chamada."""
    assert JANELA_DO_LOTE_SEGUNDOS == 120.0
    assert {goal.id_goal: goal.lotes for goal in medicao.goals} == {CONDUZIDO: 2, ONDAS: 16, CONTINUO: 62}


def test_o_goal_conduzido_de_perto_nao_tem_desvio_como_na_secao_7_nominal(medicao: MedicaoDeEscopo) -> None:
    """12 para 14: zero eventos em toda hipótese de raiz, com ou sem o M, e a seção 7 também dá zero."""
    goal = _goal(medicao, CONDUZIDO)
    assert SECAO_7[(goal.plano, goal.total)][1] == 0
    assert goal.desvio.total == goal.desvio_sem_resposta.total == 0
    assert {motivo: desvio.total for motivo, desvio in goal.so_k.items()} == {
        "mais_recente": 0, "mais_antiga": 0, "mais_abrangente": 0, "todas": 0,
    }


def test_eventos_de_desvio_do_desenho_final_nominal(medicao: MedicaoDeEscopo) -> None:
    """K = 3 e M = 5 com a resposta humana depois de cada evento: 0, 2 e 15 eventos, quase todos do M."""
    por_goal = {goal.id_goal: (goal.desvio.total, dict(goal.desvio.por_gatilho())) for goal in medicao.goals}
    assert por_goal == {CONDUZIDO: (0, {}), ONDAS: (2, {"goal": 2, "raiz": 1}), CONTINUO: (15, {"goal": 13, "raiz": 2})}
    assert {goal.id_goal: goal.desvio_sem_resposta.total for goal in medicao.goals} == {
        CONDUZIDO: 0, ONDAS: 12, CONTINUO: 59,
    }


def test_so_o_k_da_secao_7_depende_da_decision_que_vira_a_raiz_nominal(medicao: MedicaoDeEscopo) -> None:
    """O log não diz qual das até 11 Decisions motivou a Task: no modo contínuo o K só varia de 2 a 15 conforme a escolha."""
    por_motivo = {
        motivo: {goal.id_goal: goal.so_k[motivo].total for goal in medicao.goals}
        for motivo in ("mais_recente", "mais_antiga", "mais_abrangente", "todas")
    }
    assert por_motivo["mais_recente"] == {CONDUZIDO: 0, ONDAS: 1, CONTINUO: 2}
    assert por_motivo["mais_antiga"] == {CONDUZIDO: 0, ONDAS: 1, CONTINUO: 13}
    assert por_motivo["mais_abrangente"] == {CONDUZIDO: 0, ONDAS: 1, CONTINUO: 15}
    assert por_motivo["todas"] == {CONDUZIDO: 0, ONDAS: 1, CONTINUO: 5}


def test_nenhuma_hipotese_chega_aos_numeros_da_secao_7_para_os_goals_com_desvio_edge_case(
    medicao: MedicaoDeEscopo,
) -> None:
    """Caso de borda: com resposta simulada, 6 e 23 não saem de nenhuma hipótese; só o 0 da seção 7 se reproduz."""
    for goal in medicao.goals:
        esperado = SECAO_7[(goal.plano, goal.total)][1]
        medidos = {goal.desvio.total, *(desvio.total for desvio in goal.so_k.values())}
        assert (esperado in medidos) is (esperado == 0), goal.id_goal


def test_o_alerta_chega_antes_do_trabalho_que_cobre_nominal(medicao: MedicaoDeEscopo) -> None:
    """Em todo evento ao menos uma Task coberta ainda não tinha começado, mas a margem até a primeira execução é de minutos."""
    ondas, continuo = _goal(medicao, ONDAS).desvio, _goal(medicao, CONTINUO).desvio
    assert (ondas.antes_do_trabalho, ondas.total) == (2, 2)
    assert (continuo.antes_do_trabalho, continuo.total) == (15, 15)
    assert (ondas.cobertas, ondas.nao_comecadas) == (21, 13)
    assert (continuo.cobertas, continuo.nao_comecadas) == (88, 31)
    assert len(ondas.horas_ate_a_primeira_execucao) == 2 and len(continuo.horas_ate_a_primeira_execucao) == 15
    assert max(*ondas.horas_ate_a_primeira_execucao, *continuo.horas_ate_a_primeira_execucao) < 0.2


def test_a_fila_antiga_e_a_nova_servem_o_mesmo_no_historico_nominal(medicao: MedicaoDeEscopo) -> None:
    """Nunca havia mais de uma Task do plano liberada: emergente escolhida com plano liberado é zero e a posição não muda."""
    esperado = {CONDUZIDO: (14, 2, 2, 2, 12), ONDAS: (35, 27, 4, 4, 5), CONTINUO: (97, 90, 0, 0, 3)}
    for goal in medicao.goals:
        fila = goal.fila
        medido = (
            len(fila.momentos), fila.emergentes_escolhidas, fila.com_plano_pendente, fila.pedidas_pelo_plano,
            fila.momentos_com_plano_liberado,
        )
        assert medido == esperado[goal.id_goal], goal.id_goal
        assert fila.com_plano_liberado == 0
        assert fila.posicao_media() == (1.0, 1.0)
        assert fila.posicao_media(so_emergentes=True) is None


def test_toda_emergente_escolhida_com_plano_pendente_era_pedida_pelo_plano_edge_case(
    medicao: MedicaoDeEscopo,
) -> None:
    """Caso de borda: as 6 escolhas de emergente com plano esperando eram dependência do plano (faixa 2), não desvio."""
    for goal in medicao.goals:
        assert goal.fila.pedidas_pelo_plano == goal.fila.com_plano_pendente
    assert sum(goal.fila.com_plano_pendente for goal in medicao.goals) == 6
    assert {goal.id_goal: round(goal.fila.pendentes_por_momento, 2) for goal in medicao.goals} == {
        CONDUZIDO: 1.0, ONDAS: 1.4, CONTINUO: 1.31,
    }


def test_cobertura_de_origem_pelo_classificador_real_nominal(medicao: MedicaoDeEscopo) -> None:
    """O kernel 1.5.0 recusaria 2 de 2, 27 de 30 e 93 de 97 Tasks pós-plano; só subdivisão e correção têm ligação no log antigo."""
    cobertura = {goal.id_goal: goal.cobertura for goal in medicao.goals}
    assert dict(cobertura[CONDUZIDO].por_classe) == {"sem_ligacao": 2}
    assert dict(cobertura[ONDAS].por_classe) == {"b1": 1, "correcao": 2, "sem_ligacao": 27}
    assert dict(cobertura[CONTINUO].por_classe) == {"b1": 2, "correcao": 2, "sem_ligacao": 93}
    assert {id_goal: (c.depois_do_plano, c.aceitas, c.recusadas) for id_goal, c in cobertura.items()} == {
        CONDUZIDO: (2, 0, 2), ONDAS: (30, 3, 27), CONTINUO: (97, 4, 93),
    }
    assert cobertura[CONDUZIDO].recusadas_de_agente == 0 and cobertura[CONDUZIDO].de_agente == 0
    assert cobertura[CONTINUO].recusadas_de_agente == 93


def test_a_medicao_nao_altera_o_corpus_edge_case() -> None:
    """Caso de borda: plano, respostas e `motivada_por` entram numa cópia; o estado do corpus fica como veio."""
    corpus = carregar_corpus()
    antes = corpus.estado.serializar_para_json()
    medir_escopo(corpus)
    depois = corpus.estado.serializar_para_json()

    assert depois == antes
    assert not any(aresta.tipo.value == "motivada_por" for aresta in corpus.estado.arestas.values())
    assert all("planos" not in no.propriedades for no in corpus.estado.nos.values())


def test_o_plano_aproximado_e_o_primeiro_em_andamento_edge_case() -> None:
    """Caso de borda: o plano termina antes do `seq` da primeira Task em andamento e os lotes começam depois dele."""
    corpus = carregar_corpus()
    historia = historia_do_goal(corpus, CONTINUO)

    assert historia.seq_do_plano == 7882
    assert max(task.seq for task in historia.plano) < historia.seq_do_plano
    assert all(task.seq > historia.seq_do_plano for lote in historia.lotes for task in map(historia.task, lote.tasks))
    assert sum(len(lote.tasks) for lote in historia.lotes) == 97


def test_relatorio_tem_as_cinco_tabelas_e_so_ascii_nominal(medicao: MedicaoDeEscopo) -> None:
    """O relatório traz A a E, cabe no console do Windows e não revela o mapa para os Goals reais."""
    linhas = formatar_relatorio(medicao)
    texto = "\n".join(linhas)

    for titulo in ("## A. ", "## B. ", "## C. ", "## D. ", "## E. "):
        assert titulo in texto
    assert all(linha.isascii() for linha in linhas)
    assert "goal-receita" not in texto and "goal-governanca" not in texto and "goal-competicoes" not in texto
    com_rotulo = "\n".join(formatar_relatorio(medicao, {CONTINUO: "modo continuo"}))
    assert f"{CONTINUO} (modo continuo)" in com_rotulo
