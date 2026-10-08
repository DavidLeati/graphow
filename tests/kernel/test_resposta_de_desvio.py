"""`Goal.respostas_de_desvio` é do gesto `responder_desvio`, e cada resposta tem forma fixa e autoria verdadeira."""

from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor
from graphow.kernel.write_kernel import WriteKernel
from tests.kernel.cenario_escopo import (
    AGENTES,
    definir_lista,
    entrada_da_resposta,
    lista_do_goal,
    montar_kernel_com_goal,
    submeter,
)

MAXIMA: str = "governanca_maxima"
ARBITRAGEM: str = "arbitragem_maxima"
PERSONALIZADA: str = "personalizada"
COM_O_ARBITRO: dict[str, str] = {"responder_desvio": "arbitro"}
CAMPO: str = "respostas_de_desvio"


def _responder(kernel: WriteKernel, quem: PapelAutor, **sobrescritas: Any) -> Any:
    """O papel acrescenta uma resposta de desvio, com campos trocados quando o teste os falsifica."""
    anteriores = lista_do_goal(kernel, CAMPO)
    entrada = entrada_da_resposta(kernel, quem, **sobrescritas)
    return submeter(kernel, quem, definir_lista(CAMPO, [*anteriores, entrada]))


@pytest.mark.parametrize("preset", [MAXIMA, ARBITRAGEM])
@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, *AGENTES, PapelAutor.ARBITRO])
def test_nos_presets_fixos_so_o_humano_responde_nominal(preset: str, papel: PapelAutor) -> None:
    """O gesto é do humano nos dois presets fixos: a arbitragem máxima não o entrega ao árbitro."""
    kernel = montar_kernel_com_goal(preset)
    recibo = _responder(kernel, papel)
    assert recibo.sucesso is (papel == PapelAutor.HUMANO), recibo.mensagem
    if papel != PapelAutor.HUMANO:
        assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
        assert "responder_desvio" in recibo.mensagem


def test_so_a_personalizada_entrega_o_gesto_ao_arbitro_nominal() -> None:
    """Com `responder_desvio: arbitro` na personalizada o árbitro responde, e a resposta leva o papel dele."""
    kernel = montar_kernel_com_goal(PERSONALIZADA, COM_O_ARBITRO)
    assert _responder(kernel, PapelAutor.ARBITRO, resposta="conter").sucesso
    resposta = lista_do_goal(kernel, CAMPO)[0]
    assert (resposta["papel"], resposta["respondido_por"]) == ("arbitro", "arbitro-1#bbbb")


@pytest.mark.parametrize("papel", AGENTES)
def test_planejador_executor_e_revisor_nunca_respondem_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: nem a personalizada com o árbitro abre o gesto aos outros agentes."""
    kernel = montar_kernel_com_goal(PERSONALIZADA, COM_O_ARBITRO)
    recibo = _responder(kernel, papel)
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_resposta_com_raiz_existente_ou_nula_passa_nominal() -> None:
    """A raiz é o id de uma decisão do grafo, ou nula quando a resposta é ao Goal."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _responder(kernel, PapelAutor.HUMANO, raiz="dec-1").sucesso
    assert _responder(kernel, PapelAutor.HUMANO, raiz=None).sucesso
    assert [r["raiz"] for r in lista_do_goal(kernel, CAMPO)] == ["dec-1", None]


@pytest.mark.parametrize(
    ("sobrescrita", "trecho"),
    [
        ({"seq": 1}, "seq"),
        ({"respondido_por": "outra-pessoa"}, "autoria"),
        ({"papel": "arbitro"}, "autoria"),
        ({"raiz": "nao-existe"}, "raiz"),
        ({"raiz": 7}, "raiz"),
        ({"resposta": ""}, "texto"),
        ({"resposta": "   "}, "texto"),
        ({"resposta": 3}, "texto"),
        ({"extra": 1}, "entrada"),
    ],
)
def test_forma_da_resposta_e_conferida_ate_para_o_humano_edge_case(sobrescrita: dict[str, Any], trecho: str) -> None:
    """Caso de borda: seq velho, autor falso, raiz inexistente e texto vazio são recusados, o humano inclusive."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = _responder(kernel, PapelAutor.HUMANO, **sobrescrita)
    assert not recibo.sucesso
    assert trecho in recibo.mensagem
    assert lista_do_goal(kernel, CAMPO) == []


def test_resposta_sem_a_chave_raiz_vale_como_nula_edge_case() -> None:
    """Caso de borda: a chave `raiz` é opcional na entrada; ausente é o mesmo que nula."""
    kernel = montar_kernel_com_goal(MAXIMA)
    entrada = entrada_da_resposta(kernel, PapelAutor.HUMANO)
    del entrada["raiz"]
    assert submeter(kernel, PapelAutor.HUMANO, definir_lista(CAMPO, [entrada])).sucesso


def test_reescrever_a_resposta_antiga_e_recusado_edge_case() -> None:
    """Caso de borda: a resposta que zerou o contador não se reescreve nem se apaga."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _responder(kernel, PapelAutor.HUMANO).sucesso
    antiga = lista_do_goal(kernel, CAMPO)[0]
    nova = entrada_da_resposta(kernel, PapelAutor.HUMANO)
    recibo = submeter(kernel, PapelAutor.HUMANO, definir_lista(CAMPO, [{**antiga, "resposta": "outra"}, nova]))
    assert not recibo.sucesso
    assert "antiga" in recibo.mensagem
    assert not submeter(kernel, PapelAutor.HUMANO, definir_lista(CAMPO, [])).sucesso
    assert lista_do_goal(kernel, CAMPO) == [antiga]


def test_duas_respostas_num_lote_sao_recusadas_edge_case() -> None:
    """Caso de borda: uma resposta por lote, cada uma com o seq do próprio momento."""
    kernel = montar_kernel_com_goal(MAXIMA)
    duas = [entrada_da_resposta(kernel, PapelAutor.HUMANO), entrada_da_resposta(kernel, PapelAutor.HUMANO)]
    recibo = submeter(kernel, PapelAutor.HUMANO, definir_lista(CAMPO, duas))
    assert not recibo.sucesso
    assert "uma por lote" in recibo.mensagem
