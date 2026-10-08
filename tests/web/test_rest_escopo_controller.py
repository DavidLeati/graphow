"""Testes do controlador do placar de escopo: o placar do Goal, o plano aprovado e os limiares com a origem."""

from http import HTTPStatus

from graphow.web.rest_escopo_controller import EscopoWebController
from tests.web.cenario_escopo import EMERGENTES, montar_kernel


def test_placar_do_goal_com_plano_e_desvio_acima_de_k_nominal() -> None:
    """O corpo traz o placar, o plano aprovado, o gatilho K disparado em d1 e os limiares com a origem."""
    resposta = EscopoWebController(montar_kernel()).ler("goal-e")
    corpo = resposta.corpo

    assert resposta.status == HTTPStatus.OK and corpo["sucesso"] is True
    assert corpo["plano_aprovado"] is True and corpo["id_goal"] == "goal-e"
    assert corpo["referencia"]["papel"] == "humano"
    assert corpo["contagem_por_classe"]["b3"] == EMERGENTES
    assert corpo["raiz_que_mais_gerou"] == "d1" and corpo["sem_veredito"] == ["d1"]
    assert [(g["tipo"], g["raiz"]) for g in corpo["gatilhos_disparados"]] == [("raiz", "d1")]
    assert corpo["limiares"]["por_raiz"] == 3 and corpo["limiares"]["por_goal"] == 5
    assert corpo["limiares"]["origem_por_raiz"] and corpo["limiares"]["origem_por_goal"]
    assert corpo["linhas"][0].startswith("Escopo: plano_v1 (humano, seq ")
    assert any(linha.startswith("Gatilho K: d1") for linha in corpo["linhas_de_desvio"])


def test_goal_sem_plano_aprovado_diz_que_nao_ha_plano_edge_case() -> None:
    """Caso de borda: sem plano aprovado `plano_aprovado` é falso e nenhuma Task é do plano."""
    corpo = EscopoWebController(montar_kernel(com_plano=False, emergentes=0)).ler("goal-e").corpo

    assert corpo["plano_aprovado"] is False and corpo["referencia"] is None
    assert corpo["plano"]["total"] == 0 and corpo["gatilhos_disparados"] == []


def test_goal_sem_desvio_nao_dispara_gatilho_edge_case() -> None:
    """Caso de borda: com plano e sem emergente o placar é calmo."""
    corpo = EscopoWebController(montar_kernel(emergentes=0)).ler("goal-e").corpo

    assert corpo["plano_aprovado"] is True and corpo["gatilhos_disparados"] == [] and corpo["raiz_que_mais_gerou"] is None


def test_pedido_sem_goal_ou_para_no_que_nao_e_goal_e_recusado_edge_case() -> None:
    """Caso de borda: sem id vem 400; id inexistente ou de outro tipo vem 404, sem tocar o grafo."""
    escopo = EscopoWebController(montar_kernel())

    assert escopo.ler("").status == HTTPStatus.BAD_REQUEST
    assert escopo.ler("nao-existe").status == HTTPStatus.NOT_FOUND
    recusa = escopo.ler("t-plano")
    assert recusa.status == HTTPStatus.NOT_FOUND and recusa.corpo["sucesso"] is False
