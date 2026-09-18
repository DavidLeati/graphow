"""Testes do controlador de memória: o painel lê aprendizados e sessões, e o humano registra e promove."""

from graphow.context.fechamento import ACAO_DE_CONDENSACAO
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.reactive.montagem import ligar_motor_reativo_padrao
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import (
    RequisicaoEdicaoNo,
    RequisicaoNovoNo,
    RequisicaoPromocaoDeAprendizado,
    RequisicaoRegistroDeAprendizado,
)
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_memoria_controller import (
    CONDENSACAO_FEITA,
    CONDENSACAO_NENHUMA,
    CONDENSACAO_PENDENTE,
    MemoriaWebController,
)


def _montar() -> tuple[WriteKernel, CanvasWebController, MemoriaWebController]:
    """Projeto, Setor e Sessão com uma Decision e uma Evidence produzidas pela sessão."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto 1", id_no="proj-01"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Memoria", id_no="setor-01", contido_em="proj-01"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 1", id_no="sess-01", contido_em="setor-01"),
        RequisicaoNovoNo(tipo="Decision", rotulo="Transacao unica por lote", id_no="dec-1", sessao_id="sess-01"),
        RequisicaoNovoNo(tipo="Evidence", rotulo="Sonda de 17 casos", id_no="ev-1", sessao_id="sess-01"),
    )
    for req in requisicoes:
        assert canvas.criar_no(req).sucesso is True
    return kernel, canvas, MemoriaWebController(kernel)


def _registro(**extras: object) -> RequisicaoRegistroDeAprendizado:
    """Um pedido de registro completo, com o que o teste quiser sobrescrever."""
    base: dict[str, object] = {
        "afirmacao": "Lote com no novo sem contencao e recusado inteiro",
        "id_sessao": "sess-01",
        "origens": ("dec-1", "ev-1"),
        "como_aplicar": "Traga o produz no mesmo lote",
        "id_aprendizado": "apr-1",
    }
    base.update(extras)
    return RequisicaoRegistroDeAprendizado(**base)  # type: ignore[arg-type]


def test_registrar_cria_o_aprendizado_pendurado_na_sessao_e_derivado_das_origens_nominal() -> None:
    """O nó, o `produz` da sessão e um `deriva_de` por origem saem no mesmo lote."""
    kernel, _, memoria = _montar()

    recibo = memoria.registrar_aprendizado(_registro())

    assert recibo.sucesso is True, recibo.mensagem
    view = kernel.obter_view()
    assert view.obter_no("apr-1").tipo == TipoNo.APRENDIZADO
    assert [a.origem_id for a in view.obter_arestas_entrada("apr-1", TipoAresta.PRODUZ)] == ["sess-01"]
    assert sorted(a.destino_id for a in view.obter_arestas_saida("apr-1", TipoAresta.DERIVA_DE)) == ["dec-1", "ev-1"]


def test_registrar_sem_origem_e_recusado_antes_do_kernel_edge_case() -> None:
    """Caso de borda: a interface não manda ao portão um pedido que ele recusaria de qualquer jeito."""
    kernel, _, memoria = _montar()

    recibo = memoria.registrar_aprendizado(_registro(origens=()))

    assert recibo.sucesso is False
    assert "origem" in recibo.mensagem
    assert kernel.obter_view().contem_no("apr-1") is False


def test_promover_global_e_por_conteiner_nominal() -> None:
    """A marca global vira propriedade; o alcance por Setor vira `vale_para`."""
    kernel, _, memoria = _montar()
    memoria.registrar_aprendizado(_registro())

    global_ = memoria.promover_aprendizado(RequisicaoPromocaoDeAprendizado(id_aprendizado="apr-1", eh_global=True))
    setor = memoria.promover_aprendizado(RequisicaoPromocaoDeAprendizado(id_aprendizado="apr-1", id_alvo="setor-01"))

    assert global_.sucesso is True, global_.mensagem
    assert setor.sucesso is True, setor.mensagem
    view = kernel.obter_view()
    assert view.obter_no("apr-1").obter_propriedade("alcance") == "global"
    assert [a.destino_id for a in view.obter_arestas_saida("apr-1", TipoAresta.VALE_PARA)] == ["setor-01"]


def test_promover_sem_alvo_e_recusado_edge_case() -> None:
    """Caso de borda: promover sem dizer para onde não é promover."""
    _, _, memoria = _montar()
    memoria.registrar_aprendizado(_registro())

    recibo = memoria.promover_aprendizado(RequisicaoPromocaoDeAprendizado(id_aprendizado="apr-1"))

    assert recibo.sucesso is False


def test_painel_lista_o_aprendizado_com_origem_alcance_e_sessao_nominal() -> None:
    """O painel vê o aprendizado como o acervo o veria, mais a sessão em que nasceu."""
    _, _, memoria = _montar()
    memoria.registrar_aprendizado(_registro())
    memoria.promover_aprendizado(RequisicaoPromocaoDeAprendizado(id_aprendizado="apr-1", id_alvo="proj-01"))

    resposta = memoria.obter_memoria()

    assert resposta.sucesso is True
    assert [aprendizado.id for aprendizado in resposta.aprendizados] == ["apr-1"]
    aprendizado = resposta.aprendizados[0]
    assert aprendizado.sessao_id == "sess-01"
    assert aprendizado.promovido is True and aprendizado.vigente is True
    assert aprendizado.alcances == ("proj-01",)
    assert [(origem.id, origem.tipo) for origem in aprendizado.origens] == [("dec-1", "Decision"), ("ev-1", "Evidence")]
    assert aprendizado.como_aplicar == "Traga o produz no mesmo lote"


def test_aprendizado_nao_promovido_aparece_sem_alcance_nominal() -> None:
    """O acervo só tem os promovidos; o painel mostra também o que ainda vale só onde nasceu."""
    _, _, memoria = _montar()
    memoria.registrar_aprendizado(_registro())

    aprendizado = memoria.obter_memoria().aprendizados[0]

    assert aprendizado.promovido is False
    assert aprendizado.alcances == ()


def test_painel_descreve_a_sessao_com_fechamento_e_estado_da_condensacao_nominal() -> None:
    """Sessão ativa: nenhuma condensação. Encerrada: pendente. Com a Note: feita."""
    kernel, canvas, memoria = _montar()
    ligar_motor_reativo_padrao(kernel)

    ativa = memoria.obter_memoria().sessoes[0]
    assert ativa.id == "sess-01" and ativa.status == "ativa"
    assert ativa.setor_id == "setor-01"
    assert ativa.condensacao == CONDENSACAO_NENHUMA
    assert any("vigora: dec-1" in linha for linha in ativa.fechamento)

    assert canvas.editar_no(RequisicaoEdicaoNo(id_no="sess-01", novas_propriedades={"status": "concluida"})).sucesso
    encerrada = memoria.obter_memoria().sessoes[0]
    assert encerrada.status == "concluida"
    assert encerrada.condensacao == CONDENSACAO_PENDENTE

    nota = RequisicaoNovoNo(
        tipo="Note",
        rotulo="Condensacao",
        id_no="note-cond",
        sessao_id="sess-01",
        propriedades={"acao": ACAO_DE_CONDENSACAO, "id_alvo": "sess-01", "corpo": "vigora dec-1"},
    )
    assert canvas.criar_no(nota).sucesso
    condensada = memoria.obter_memoria().sessoes[0]
    assert condensada.condensacao == CONDENSACAO_FEITA
    assert condensada.id_condensacao == "note-cond"


def test_sessoes_saem_da_mais_recente_para_a_mais_antiga_nominal() -> None:
    """A sessão de hoje interessa mais que a do mês passado."""
    _, canvas, memoria = _montar()
    assert canvas.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 2", id_no="sess-02", contido_em="setor-01")).sucesso

    assert [sessao.id for sessao in memoria.obter_memoria().sessoes] == ["sess-02", "sess-01"]
