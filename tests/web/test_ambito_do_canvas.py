"""Testes do âmbito no canvas: os projetos de trabalho numa raiz, as sessões do hook na outra."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.harness.ambiente_padrao import AmbientePadrao, GarantidorDeAmbientePadrao
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.web.colapso_visual import OpcoesDeRecorteVisual
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController

IDS_DO_PROJETO: frozenset[str] = frozenset({"proj", "setor-a", "sess-a", "t-a"})
IDS_DO_HOOK: frozenset[str] = frozenset(
    {"proj-meu-repo", "setor-meu-repo-memoria", "sess-hook", "run-sess-hook", "note-avulsa", "quest-avulsa"}
)


def _aresta(tipo: TipoAresta, origem: str, destino: str) -> ItemPatch:
    """Operação de criação de uma aresta tipada."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _registro_do_agente(id_no: str, tipo: TipoNo, rotulo: str) -> tuple[ItemPatch, ItemPatch]:
    """O que o agente grava na própria sessão do hook: o nó e a aresta `produz` que o pendura nela."""
    no = ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo})
    return no, _aresta(TipoAresta.PRODUZ, "sess-hook", id_no)


def _submeter(kernel: WriteKernel, papel: PapelAutor, operacoes: tuple[ItemPatch, ...]) -> bool:
    """Submete o lote sob o papel dado e devolve se o portão aceitou."""
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def _montar_os_dois_ambitos() -> tuple[WriteKernel, CanvasWebController]:
    """Um Projeto de trabalho feito na tela e a sessão que o hook abriu, com a nota avulsa do agente."""
    kernel = montar_kernel_em_memoria()
    ctrl = CanvasWebController(kernel)
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Setor a", id_no="setor-a", contido_em="proj"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao a", id_no="sess-a", contido_em="setor-a"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Tarefa a", id_no="t-a", sessao_id="sess-a"))
    id_setor = GarantidorDeAmbientePadrao(kernel).garantir(AmbientePadrao(nome_do_projeto="meu-repo"))
    ServicoHarness(kernel).registrar(PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor=id_setor))
    avulsos = (
        *_registro_do_agente("note-avulsa", TipoNo.NOTE, "Nota avulsa do agente"),
        *_registro_do_agente("quest-avulsa", TipoNo.QUESTION, "Pergunta avulsa do agente"),
    )
    assert _submeter(kernel, PapelAutor.EXECUTOR, avulsos)
    return kernel, ctrl


def test_raiz_dos_projetos_deixa_de_fora_o_ambiente_do_hook_nominal() -> None:
    """'Todos os projetos' traz o trabalho estruturado, sem sessões nem Runs do hook."""
    _, ctrl = _montar_os_dois_ambitos()

    assert {no.id for no in ctrl.obter_canvas(ambito="projetos").nos} == IDS_DO_PROJETO


def test_raiz_das_sessoes_do_hook_traz_so_o_ambiente_do_hook_nominal() -> None:
    """A outra raiz traz o ambiente do repositório, as sessões, os Runs e o que o agente anotou nelas."""
    _, ctrl = _montar_os_dois_ambitos()

    assert {no.id for no in ctrl.obter_canvas(ambito="hook").nos} == IDS_DO_HOOK


def test_nota_e_pergunta_avulsas_do_agente_seguem_na_sessao_do_hook_nominal() -> None:
    """O agente continua anotando na própria sessão, e o que ele anota não aparece nos projetos."""
    _, ctrl = _montar_os_dois_ambitos()
    canvas = ctrl.obter_canvas()

    ambitos = {no.id: no.ambito for no in canvas.nos if no.id in {"note-avulsa", "quest-avulsa"}}
    assert ambitos == {"note-avulsa": "hook", "quest-avulsa": "hook"}
    assert {no.sessao_id for no in canvas.nos if no.id in ambitos} == {"sess-hook"}


def test_sem_ambito_a_camada_de_navegacao_traz_as_duas_raizes_marcadas_nominal() -> None:
    """O explorador lê a camada inteira e separa as raízes pelo âmbito de cada uma."""
    _, ctrl = _montar_os_dois_ambitos()
    canvas = ctrl.obter_canvas(opcoes=OpcoesDeRecorteVisual(colapsar_em="projeto"))

    assert {no.id: no.ambito for no in canvas.nos} == {"proj": "projetos", "proj-meu-repo": "hook"}


def test_total_por_ambito_conta_o_grafo_inteiro_em_qualquer_recorte_edge_case() -> None:
    """Caso de borda: colapsada e filtrada, a resposta ainda diz quanto cada raiz guarda."""
    _, ctrl = _montar_os_dois_ambitos()
    canvas = ctrl.obter_canvas(ambito="projetos", opcoes=OpcoesDeRecorteVisual(colapsar_em="projeto"))

    assert canvas.total_por_ambito == {"projetos": len(IDS_DO_PROJETO), "hook": len(IDS_DO_HOOK)}


def test_sessao_do_hook_levada_a_um_projeto_passa_a_morar_nele_edge_case() -> None:
    """Caso de borda: quem move a sessão do hook para um Setor de trabalho a leva, com o que ela produziu."""
    kernel, ctrl = _montar_os_dois_ambitos()
    mover = (
        ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/contem-setor-meu-repo-memoria-sess-hook"),
        _aresta(TipoAresta.CONTEM, "setor-a", "sess-hook"),
    )
    assert _submeter(kernel, PapelAutor.HUMANO, mover)

    ids = {no.id for no in ctrl.obter_canvas(ambito="projetos").nos}

    assert {"sess-hook", "run-sess-hook", "note-avulsa"} <= ids
    assert "proj-meu-repo" not in ids


def test_ambito_desconhecido_nao_filtra_nada_edge_case() -> None:
    """Caso de borda: um âmbito que ninguém declarou devolve o grafo inteiro, como sem filtro."""
    _, ctrl = _montar_os_dois_ambitos()

    assert {no.id for no in ctrl.obter_canvas(ambito="qualquer").nos} == IDS_DO_PROJETO | IDS_DO_HOOK
