"""`Goal.planos` é do gesto `aprovar_plano`, e cada entrada tem forma fixa: só cresce, uma por lote, com autoria verdadeira."""

from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.write_kernel import WriteKernel
from tests.kernel.cenario_escopo import (
    AGENTES,
    definir_lista,
    entrada_do_plano,
    lista_do_goal,
    montar_kernel_com_goal,
    submeter,
)
from tests.kernel.cenario_governanca import criar_aresta, criar_no

MAXIMA: str = "governanca_maxima"
ARBITRAGEM: str = "arbitragem_maxima"


def _aprovar(kernel: WriteKernel, quem: PapelAutor, **sobrescritas: Any) -> Any:
    """O papel acrescenta a próxima versão do plano, com campos trocados quando o teste os falsifica."""
    anteriores = lista_do_goal(kernel, "planos")
    entrada = entrada_do_plano(kernel, quem, **sobrescritas)
    return submeter(kernel, quem, definir_lista("planos", [*anteriores, entrada]))


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, *AGENTES, PapelAutor.ARBITRO])
def test_governanca_maxima_so_o_humano_aprova_o_plano_nominal(papel: PapelAutor) -> None:
    """Na governança máxima o gesto é do humano: nenhum papel de agente, árbitro inclusive, escreve o plano."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = _aprovar(kernel, papel)
    assert recibo.sucesso is (papel == PapelAutor.HUMANO), recibo.mensagem
    if papel != PapelAutor.HUMANO:
        assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
        assert "aprovar_plano" in recibo.mensagem
        assert lista_do_goal(kernel, "planos") == []


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, PapelAutor.ARBITRO])
def test_arbitragem_maxima_entrega_o_gesto_ao_arbitro_nominal(papel: PapelAutor) -> None:
    """Na arbitragem máxima o árbitro aprova o plano, e o registro leva o papel dele."""
    kernel = montar_kernel_com_goal(ARBITRAGEM)
    assert _aprovar(kernel, papel).sucesso
    assert lista_do_goal(kernel, "planos")[0]["papel"] == papel.value


@pytest.mark.parametrize("papel", AGENTES)
def test_planejador_executor_e_revisor_nunca_aprovam_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: nem a arbitragem máxima abre o gesto a quem não é humano nem árbitro."""
    kernel = montar_kernel_com_goal(ARBITRAGEM)
    recibo = _aprovar(kernel, papel)
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_o_goal_criado_com_planos_passa_pelo_mesmo_gesto_edge_case() -> None:
    """Caso de borda: criar o Goal já com a lista não contorna o gesto do papel."""
    kernel = montar_kernel_com_goal(MAXIMA)
    nascer = (
        criar_no("g2", TipoNo.GOAL, planos=[entrada_do_plano(kernel, PapelAutor.PLANEJADOR)]),
        criar_aresta("prod-g2", "sess", "g2", TipoAresta.PRODUZ),
    )
    recibo = submeter(kernel, PapelAutor.PLANEJADOR, *nascer)
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_versoes_sucessivas_cada_uma_com_o_proprio_seq_nominal() -> None:
    """A versão 1 do humano e a 2 do árbitro convivem; cada uma guarda o seq em que foi aprovada."""
    kernel = montar_kernel_com_goal(ARBITRAGEM)
    assert _aprovar(kernel, PapelAutor.HUMANO).sucesso
    assert _aprovar(kernel, PapelAutor.ARBITRO).sucesso
    planos = lista_do_goal(kernel, "planos")
    assert [(p["versao"], p["papel"]) for p in planos] == [(1, "humano"), (2, "arbitro")]
    assert planos[0]["seq"] < planos[1]["seq"]
    assert planos[0]["aprovado_por"] == "david"


@pytest.mark.parametrize(
    ("sobrescrita", "trecho"),
    [
        ({"versao": 2}, "versao 1"),
        ({"versao": 0}, "versao 1"),
        ({"versao": True}, "versao"),
        ({"seq": 1}, "seq"),
        ({"seq": "agora"}, "seq"),
        ({"aprovado_por": "outra-pessoa"}, "autoria"),
        ({"papel": "arbitro"}, "autoria"),
        ({"extra": 1}, "entrada"),
    ],
)
def test_forma_da_entrada_nova_e_conferida_ate_para_o_humano_edge_case(sobrescrita: dict[str, Any], trecho: str) -> None:
    """Caso de borda: versão errada, seq errado, autor falso e chave a mais são recusados, o humano inclusive."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = _aprovar(kernel, PapelAutor.HUMANO, **sobrescrita)
    assert not recibo.sucesso
    assert trecho in recibo.mensagem
    assert lista_do_goal(kernel, "planos") == []


def test_autor_falso_e_violacao_de_papel_nao_so_de_estrutura_edge_case() -> None:
    """Caso de borda: assinar com o nome de outro é falha de permissão, e a mensagem diz quem propôs."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = _aprovar(kernel, PapelAutor.HUMANO, aprovado_por="outra-pessoa")
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
    assert "david" in recibo.mensagem


def test_reescrever_a_entrada_antiga_e_recusado_edge_case() -> None:
    """Caso de borda: a lista só cresce; trocar o seq de uma versão que já existe é apagar o registro."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _aprovar(kernel, PapelAutor.HUMANO).sucesso
    antiga = lista_do_goal(kernel, "planos")[0]
    reescrita = [{**antiga, "seq": antiga["seq"] + 1}, entrada_do_plano(kernel, PapelAutor.HUMANO, versao=2)]
    recibo = submeter(kernel, PapelAutor.HUMANO, definir_lista("planos", reescrita))
    assert not recibo.sucesso
    assert "antiga" in recibo.mensagem
    assert lista_do_goal(kernel, "planos") == [antiga]


def test_encurtar_ou_remover_a_lista_e_recusado_edge_case() -> None:
    """Caso de borda: esvaziar a lista ou remover a propriedade perderia o plano aprovado."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _aprovar(kernel, PapelAutor.HUMANO).sucesso
    assert not submeter(kernel, PapelAutor.HUMANO, definir_lista("planos", [])).sucesso
    remover = ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/goal/propriedades/planos")
    assert not submeter(kernel, PapelAutor.HUMANO, remover).sucesso
    assert len(lista_do_goal(kernel, "planos")) == 1


def test_duas_entradas_num_lote_sao_recusadas_edge_case() -> None:
    """Caso de borda: uma aprovação por lote, para cada versão ter o seq do próprio momento."""
    kernel = montar_kernel_com_goal(MAXIMA)
    primeira = entrada_do_plano(kernel, PapelAutor.HUMANO)
    segunda = entrada_do_plano(kernel, PapelAutor.HUMANO, versao=2)
    recibo = submeter(kernel, PapelAutor.HUMANO, definir_lista("planos", [primeira, segunda]))
    assert not recibo.sucesso
    assert "uma por lote" in recibo.mensagem


def test_reescrever_a_lista_com_o_mesmo_valor_nao_e_aprovacao_nem_erro_edge_case() -> None:
    """Caso de borda: escrever a lista idêntica não muda nada e passa, para o humano."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _aprovar(kernel, PapelAutor.HUMANO).sucesso
    igual = lista_do_goal(kernel, "planos")
    assert submeter(kernel, PapelAutor.HUMANO, definir_lista("planos", igual)).sucesso
