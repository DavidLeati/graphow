"""Testes do âmbito: o que nasceu do hook fica fora dos projetos de trabalho."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.ambito import (
    Ambito,
    ambientes_do_hook,
    ambito_do_no,
    contar_por_ambito,
    eh_ambiente_do_hook,
    ler_ambito,
    nasceu_do_hook,
)


def _no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch:
    """Operação de criação de nó."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo})


def _contem(origem: str, destino: str) -> ItemPatch:
    """Operação de criação da aresta de contenção."""
    id_aresta = f"contem-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": TipoAresta.CONTEM.value},
    )


# A filiação de cada nó ao Projeto, como o mapeador de escopo a dobra das arestas `contem`.
MAPA_PROJETOS: dict[str, str] = {
    "proj-trabalho": "proj-trabalho",
    "setor-eng": "proj-trabalho",
    "proj-repo": "proj-repo",
    "setor-repo-memoria": "proj-repo",
}


def _submeter(kernel: WriteKernel, papel: PapelAutor, operacoes: list[ItemPatch]) -> None:
    """Grava o lote sob o papel dado, exigindo que o portão o aceite."""
    autor = "harness" if papel == PapelAutor.SISTEMA else "david"
    dados = DadosPropostaPatch(autor=autor, papel=papel, operacoes=operacoes, justificativa="teste")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def _grafo_com_os_dois_ambitos() -> WriteKernel:
    """Um Projeto de trabalho do humano e o ambiente que o hook criou para o repositório."""
    kernel = montar_kernel_em_memoria()
    _submeter(kernel, PapelAutor.HUMANO, [_no("proj-trabalho", TipoNo.PROJETO, "Trabalho"), _no("setor-eng", TipoNo.SETOR, "Engenharia"), _contem("proj-trabalho", "setor-eng")])
    _submeter(kernel, PapelAutor.SISTEMA, [_no("proj-repo", TipoNo.PROJETO, "repo"), _no("setor-repo-memoria", TipoNo.SETOR, "Memoria"), _contem("proj-repo", "setor-repo-memoria")])
    return kernel


def test_o_projeto_que_o_hook_criou_e_ambiente_e_o_do_humano_e_trabalho_nominal() -> None:
    """A proveniência separa os dois: só o harness escreve como `sistema`."""
    view = _grafo_com_os_dois_ambitos().obter_view()

    assert eh_ambiente_do_hook(view.obter_no("proj-repo")) is True
    assert eh_ambiente_do_hook(view.obter_no("proj-trabalho")) is False
    assert ambientes_do_hook(view) == frozenset({"proj-repo"})


def test_setor_do_hook_nasceu_do_hook_mas_nao_e_ambiente_edge_case() -> None:
    """Caso de borda: o ambiente é o Projeto; o Setor `Memoria` nasceu do hook sem ser raiz."""
    setor = _grafo_com_os_dois_ambitos().obter_view().obter_no("setor-repo-memoria")

    assert nasceu_do_hook(setor) is True
    assert eh_ambiente_do_hook(setor) is False


def test_cada_no_herda_o_ambito_do_projeto_que_o_contem_nominal() -> None:
    """O Setor do humano mora nos projetos, o Setor do hook nas sessões do hook."""
    ambientes = ambientes_do_hook(_grafo_com_os_dois_ambitos().obter_view())

    assert ambito_do_no("setor-eng", MAPA_PROJETOS, ambientes) == Ambito.PROJETOS
    assert ambito_do_no("setor-repo-memoria", MAPA_PROJETOS, ambientes) == Ambito.HOOK


def test_no_fora_de_qualquer_projeto_fica_entre_os_projetos_edge_case() -> None:
    """Caso de borda: sem Projeto acima, o nó continua onde a pasta 'Fora da hierarquia' o mostra."""
    assert ambito_do_no("solto", {}, frozenset({"proj-repo"})) == Ambito.PROJETOS


def test_contagem_por_ambito_cobre_o_grafo_inteiro_nominal() -> None:
    """Cada nó conta uma vez, no âmbito em que mora."""
    view = _grafo_com_os_dois_ambitos().obter_view()

    assert contar_por_ambito(view, MAPA_PROJETOS) == {"projetos": 2, "hook": 2}


def test_ler_ambito_aceita_so_os_nomes_conhecidos_edge_case() -> None:
    """Caso de borda: um âmbito desconhecido ou vazio não filtra nada."""
    assert ler_ambito(" Hook ") == Ambito.HOOK
    assert ler_ambito("projetos") == Ambito.PROJETOS
    assert ler_ambito("sessoes") is None
    assert ler_ambito(None) is None
