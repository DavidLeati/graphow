"""O Artifact criado pelo canvas: a âncora (commit, ou sha256 com caminho) e o `deriva_de` no mesmo lote do nó."""

from graphow.core.falhas import ModoFalhaMAST
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.conversao_requisicoes import converter_novo_no
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController

SESSAO: str = "sess-01"
SHA256: str = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def _controller() -> CanvasWebController:
    """Projeto, Setor e Sessão, com a Task de código `t-codigo` e a de ação externa `t-envio`."""
    ctrl = CanvasWebController(WriteKernel(InMemoryEventStore()))
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto 1", id_no="proj-01"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor 1", id_no="setor-01", contido_em="proj-01"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 1", id_no=SESSAO, contido_em="setor-01"),
        RequisicaoNovoNo(tipo="Task", rotulo="Somar", id_no="t-codigo", sessao_id=SESSAO, propriedades={"status": "pendente"}),
        RequisicaoNovoNo(tipo="Task", rotulo="Enviar o relatorio", id_no="t-envio", sessao_id=SESSAO,
                         propriedades={"status": "pendente", "entrega": "acao_externa"}),
    )
    for req in requisicoes:
        recibo = ctrl.criar_no(req)
        assert recibo.sucesso is True, recibo.mensagem
    return ctrl


def _artifact(id_no: str, *deriva_de: str, **propriedades: object) -> RequisicaoNovoNo:
    """O pedido do diálogo "Novo nó" para um Artifact da Sessão."""
    return RequisicaoNovoNo(tipo="Artifact", rotulo=id_no, id_no=id_no, sessao_id=SESSAO, propriedades=propriedades,
                            deriva_de=deriva_de)


def test_artifact_da_acao_externa_nasce_com_o_deriva_de_no_mesmo_lote_nominal() -> None:
    """C6: sem âncora, com `deriva_de` só à Task de ação externa, o Artifact passa e a aresta nasce com ele."""
    ctrl = _controller()

    recibo = ctrl.criar_no(_artifact("art-envio", "t-envio", resumo="e-mail enviado a diretoria"))

    assert recibo.sucesso is True, recibo.mensagem
    arestas = {(a.origem_id, a.destino_id, a.tipo) for a in ctrl.obter_canvas().arestas}
    assert ("art-envio", "t-envio", "deriva_de") in arestas
    assert (SESSAO, "art-envio", "produz") in arestas


def test_artifact_fora_de_git_leva_sha256_e_caminho_nominal() -> None:
    """C6: o documento fora de git se registra pelo canvas com o `sha256` do conteúdo e o `caminho`."""
    ctrl = _controller()

    recibo = ctrl.criar_no(_artifact("art-doc", "t-codigo", sha256=SHA256, caminho="relatorios/setembro.md", resumo="relatorio"))

    assert recibo.sucesso is True, recibo.mensagem
    assert ("art-doc", "t-codigo", "deriva_de") in {(a.origem_id, a.destino_id, a.tipo) for a in ctrl.obter_canvas().arestas}


def test_artifact_sem_ancora_fora_da_acao_externa_e_recusado_inteiro_edge_case() -> None:
    """Caso de borda: sem âncora e com `deriva_de` também à Task de código, o lote cai inteiro, nó e arestas."""
    ctrl = _controller()

    misto = ctrl.criar_no(_artifact("art-misto", "t-envio", "t-codigo", resumo="soma.py"))
    sem_derivacao = ctrl.criar_no(_artifact("art-solto", resumo="soma.py"))

    assert misto.sucesso is False and misto.modo_de_falha == ModoFalhaMAST.ARTIFACT_SEM_ANCORA.value
    assert sem_derivacao.sucesso is False and sem_derivacao.modo_de_falha == ModoFalhaMAST.ARTIFACT_SEM_ANCORA.value
    canvas = ctrl.obter_canvas()
    assert all(no.id not in {"art-misto", "art-solto"} for no in canvas.nos)
    assert all(a.origem_id != "art-misto" for a in canvas.arestas)


def test_corpo_do_pedido_leva_os_ids_de_deriva_de_sem_vazio_nem_repeticao_edge_case() -> None:
    """Caso de borda: o `deriva_de` do corpo vira a tupla de ids, na ordem, sem vazios nem repetidos; o que não é lista, nada."""
    assert converter_novo_no({"tipo": "Artifact", "deriva_de": ["t-1", " ", "t-1", "t-2"]}).deriva_de == ("t-1", "t-2")
    assert converter_novo_no({"tipo": "Artifact", "deriva_de": "t-1"}).deriva_de == ()
    assert converter_novo_no({"tipo": "Task"}).deriva_de == ()
