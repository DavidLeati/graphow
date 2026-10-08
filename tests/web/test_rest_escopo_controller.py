"""Testes do controlador do placar de escopo: o placar do Goal, o plano aprovado e os limiares com a origem."""

from http import HTTPStatus

from graphow.core.types import PapelAutor
from graphow.web.dto import RequisicaoRespostaDeDesvio
from graphow.web.identidade_web import IdentidadeSessaoWeb
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


def test_aprovar_plano_congela_as_tasks_como_versao_do_humano_nominal() -> None:
    """O gesto grava a versão 1 com o papel humano da identidade web e devolve o placar de depois."""
    kernel = montar_kernel(com_plano=False, emergentes=0)
    escopo = EscopoWebController(kernel, IdentidadeSessaoWeb(autor="ana", papel=PapelAutor.HUMANO))

    resposta = escopo.aprovar_plano("goal-e")

    assert resposta.status == HTTPStatus.OK and resposta.corpo["sucesso"] is True
    assert resposta.corpo["plano_aprovado"] is True
    assert resposta.corpo["referencia"]["papel"] == "humano"
    planos = kernel.obter_view().obter_no("goal-e").obter_propriedade("planos")
    assert [(p["versao"], p["aprovado_por"], p["papel"]) for p in planos] == [(1, "ana", "humano")]
    assert resposta.corpo["recibo"]["versao"] == 1


def test_aprovar_de_novo_acrescenta_a_versao_seguinte_edge_case() -> None:
    """Caso de borda: cada aprovação é uma versão a mais, e a lista só cresce."""
    kernel = montar_kernel(com_plano=False, emergentes=0)
    escopo = EscopoWebController(kernel)

    escopo.aprovar_plano("goal-e")
    escopo.aprovar_plano("goal-e")

    planos = kernel.obter_view().obter_no("goal-e").obter_propriedade("planos")
    assert [p["versao"] for p in planos] == [1, 2]


def test_responder_desvio_zera_o_contador_da_raiz_nominal() -> None:
    """A resposta do humano à raiz que passou de K tira o gatilho e o veredito pendente dela."""
    escopo = EscopoWebController(montar_kernel())

    resposta = escopo.responder_desvio(RequisicaoRespostaDeDesvio("goal-e", "  Segue: o hub fica.  ", "d1"))

    corpo = resposta.corpo
    assert resposta.status == HTTPStatus.OK and corpo["sucesso"] is True
    assert corpo["gatilhos_disparados"] == []
    assert next(raiz for raiz in corpo["raizes"] if raiz["raiz"] == "d1")["contador_k"] == 0
    assert corpo["recibo"]["versao_log"] > 0


def test_responder_desvio_sem_texto_ou_com_raiz_inexistente_e_recusado_edge_case() -> None:
    """Caso de borda: resposta vazia é 400 sem tocar o kernel; raiz que não é nó vem recusada pelo kernel (422)."""
    escopo = EscopoWebController(montar_kernel())

    vazia = escopo.responder_desvio(RequisicaoRespostaDeDesvio("goal-e", "   ", "d1"))
    sem_raiz = escopo.responder_desvio(RequisicaoRespostaDeDesvio("goal-e", "ok", "fantasma"))

    assert vazia.status == HTTPStatus.BAD_REQUEST
    assert sem_raiz.status == HTTPStatus.UNPROCESSABLE_ENTITY and sem_raiz.corpo["sucesso"] is False
    assert "fantasma" in sem_raiz.corpo["mensagem"]


def test_gestos_em_alvo_que_nao_e_goal_voltam_400_e_404_edge_case() -> None:
    """Caso de borda: sem Goal é 400, Goal inexistente ou de outro tipo é 404, para os dois gestos."""
    escopo = EscopoWebController(montar_kernel())

    assert escopo.aprovar_plano("").status == HTTPStatus.BAD_REQUEST
    assert escopo.aprovar_plano("t-plano").status == HTTPStatus.NOT_FOUND
    assert escopo.responder_desvio(RequisicaoRespostaDeDesvio("nao-existe", "ok")).status == HTTPStatus.NOT_FOUND


def test_a_leitura_diz_o_que_o_proximo_aprovar_congela_nominal() -> None:
    """Antes e depois de aprovar, a leitura traz a versão seguinte e a conta das Tasks de agora."""
    escopo = EscopoWebController(montar_kernel())

    antes = escopo.ler("goal-e").corpo["para_aprovar"]
    escopo.aprovar_plano("goal-e")
    depois = escopo.ler("goal-e").corpo["para_aprovar"]

    assert antes == {"versao": 2, "tasks": 1 + EMERGENTES}
    assert depois == {"versao": 3, "tasks": 1 + EMERGENTES}
