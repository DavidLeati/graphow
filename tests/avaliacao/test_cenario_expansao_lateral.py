"""O caso 14 para 121 da seção 2, pelos portões reais: o K pega a expansão lateral antes da execução.

Plano humano de 14 Tasks, uma Decision do planejador que gera 9 Tasks emergentes
para 4 alvos fora da fronteira e subdivisões legítimas do plano. Nada aqui é
escrito direto no grafo: o humano aprova o plano, o planejador cria as Tasks
com as ligações, e o kernel confere cada uma.
"""

import pytest

from graphow.avaliacao.cenario_expansao_lateral import (
    ALVOS_FORA_DA_FRONTEIRA,
    ID_QUESTAO,
    ResultadoDaExpansaoLateral,
    medir_expansao_lateral,
)
from graphow.core.falhas import ModoFalhaMAST


@pytest.fixture(scope="module")
def resultado() -> ResultadoDaExpansaoLateral:
    """O cenário montado uma vez para o módulo."""
    return medir_expansao_lateral()


def test_o_cenario_tem_o_tamanho_do_caso_nominal(resultado: ResultadoDaExpansaoLateral) -> None:
    """14 Tasks no plano, 5 subdivisões e 9 emergentes para exatamente 4 alvos fora da fronteira."""
    assert (resultado.tasks_do_plano, resultado.subdivisoes, resultado.emergentes) == (14, 5, 9)
    assert resultado.alvos_da_raiz == tuple(sorted(ALVOS_FORA_DA_FRONTEIRA))


def test_o_k_dispara_na_quarta_emergente_da_raiz_antes_de_qualquer_execucao_nominal(
    resultado: ResultadoDaExpansaoLateral,
) -> None:
    """O contador da raiz anda 1, 2, 3, 4: passa de K = 3 na quarta, e nenhuma Task tinha saído de `pendente`."""
    assert resultado.contador_k_por_emergente == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert resultado.k_dispara_na_emergente == 4
    assert resultado.tasks_iniciadas_no_alerta == 0


def test_o_m_dispara_na_sexta_e_a_raiz_fica_sem_veredito_nominal(resultado: ResultadoDaExpansaoLateral) -> None:
    """M = 5 passa na sexta emergente de agente; a raiz que passou de K não tem veredito de escopo."""
    assert resultado.m_dispara_na_emergente == 6
    assert resultado.raizes_sem_veredito == (ID_QUESTAO,)


def test_a_subdivisao_legitima_nao_conta_para_o_k_edge_case(resultado: ResultadoDaExpansaoLateral) -> None:
    """Caso de borda: as 5 subdivisões, criadas antes e depois do alerta, não mexem nos contadores da raiz."""
    assert resultado.contador_k_por_emergente[-1] == resultado.emergentes
    assert resultado.contador_m_por_emergente[-1] == resultado.emergentes


def test_a_fila_serve_o_plano_antes_das_emergentes_nominal(resultado: ResultadoDaExpansaoLateral) -> None:
    """Na ordem antiga as 9 emergentes saem antes do plano (ids menores); na nova, o plano e as subdivisões vão primeiro."""
    assert resultado.posicao_do_plano() == (10, 1)
    assert resultado.emergentes_a_frente_do_plano() == (9, 0)
    assert resultado.posicao_da_primeira_emergente() == (1, 20)
    assert resultado.fila_nova[:14] == tuple(f"plano-{n:02d}" for n in range(1, 15))
    assert all(id_task.startswith("expansao-") for id_task in resultado.fila_nova[19:])


def test_a_task_do_planejador_sem_ligacao_e_recusada_nominal(resultado: ResultadoDaExpansaoLateral) -> None:
    """Sob o plano aprovado, o Goal como pai não basta: o kernel recusa com o modo nomeado."""
    assert resultado.sem_ligacao_recusada == ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE.value


def test_o_teto_recusa_a_sexta_e_o_desvio_respondido_reabre_nominal(resultado: ResultadoDaExpansaoLateral) -> None:
    """Com `teto_expansao` 5: cinco emergentes passam, a sexta cai, e a resposta do humano devolve o orçamento."""
    teto = resultado.teto
    assert (teto.teto, teto.aceitas_antes_da_recusa) == (5, 5)
    assert (teto.recusada, teto.modo_de_falha) == ("expansao-06", ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO.value)
    assert teto.aceita_depois_da_resposta is True


def test_as_nove_emergentes_num_lote_so_caem_inteiras_sob_o_teto_edge_case(resultado: ResultadoDaExpansaoLateral) -> None:
    """Caso de borda: o lote é atômico, então estourar o teto na sexta não deixa nenhuma das nove no grafo."""
    assert resultado.teto.lote_inteiro_recusado is True
