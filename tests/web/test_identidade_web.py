"""Testes da identidade web: a autoria vem da sessão, não do corpo da requisição."""

from graphow.core.types import PapelAutor
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.identidade_web import (
    IdentidadeSessaoWeb,
    detectar_identidade_declarada,
    montar_recusa_de_identidade,
)
from graphow.web.rest_canvas_controller import CanvasWebController


def test_escrita_do_canvas_usa_o_autor_da_sessao_nominal() -> None:
    """O log de autoria deixava de ser confiável com a interface aberta."""
    kernel = montar_kernel_em_memoria()
    controlador = CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david"))

    controlador.criar_no(RequisicaoNovoNo(tipo="Note", rotulo="Anotacao", id_no="n1"))

    evento = kernel.repositorio.ler_eventos("main")[-1]
    assert evento.autor == "david"
    assert evento.papel == PapelAutor.HUMANO


def test_no_criado_pela_interface_carrega_proveniencia_humana_nominal() -> None:
    """A proveniência do nó precisa refletir quem de fato escreveu."""
    kernel = montar_kernel_em_memoria()
    CanvasWebController(kernel, IdentidadeSessaoWeb(autor="david")).criar_no(
        RequisicaoNovoNo(tipo="Note", rotulo="Anotacao", id_no="n1")
    )

    proveniencia = kernel.obter_view().obter_no("n1").proveniencia
    assert proveniencia.autor == "david"
    assert proveniencia.eh_de_agente is False


def test_dto_de_requisicao_nao_carrega_identidade_edge_case() -> None:
    """Caso de borda: o campo não existe, então não há como declará-lo."""
    req = RequisicaoNovoNo(tipo="Task", rotulo="Tarefa")

    assert not hasattr(req, "autor")
    assert not hasattr(req, "papel")


def test_corpo_que_declara_identidade_e_detectado_nominal() -> None:
    """POST e PUT liam `papel` do corpo com padrão humano; agora isso é recusa."""
    assert detectar_identidade_declarada({"papel": "humano", "rotulo": "x"}) == ("papel",)
    assert detectar_identidade_declarada({"autor": "outro", "papel": "executor"}) == (
        "autor",
        "papel",
    )
    assert detectar_identidade_declarada({"rotulo": "x"}) == ()


def test_recusa_diz_qual_e_a_identidade_real_da_sessao_nominal() -> None:
    """Recusar em vez de ignorar torna a garantia observável, como no MCP."""
    recusa = montar_recusa_de_identidade(("papel",), IdentidadeSessaoWeb(autor="david"))

    assert recusa["sucesso"] is False
    assert "david" in recusa["mensagem"]
    assert "humano" in recusa["mensagem"]


def test_identidade_local_cai_no_autor_generico_sem_usuario_edge_case() -> None:
    """Caso de borda: sem usuário resolvível, a escrita segue identificável."""
    identidade = IdentidadeSessaoWeb.do_usuario_local()

    assert identidade.autor
    assert identidade.papel == PapelAutor.HUMANO
