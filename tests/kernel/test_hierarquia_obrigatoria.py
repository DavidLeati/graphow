"""Testes da invariante que recusa nó nascido fora da hierarquia de contenção."""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel


def _no(id_no: str, tipo: TipoNo) -> ItemPatch:
    """Operação de criação de nó com rótulo igual ao id."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": id_no})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _submeter(kernel: WriteKernel, *operacoes: ItemPatch, papel: PapelAutor = PapelAutor.HUMANO) -> ResultadoSubmissao:
    """Submete o lote sob o papel pedido."""
    dados = DadosPropostaPatch(autor="david", papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _kernel_com_sessao() -> WriteKernel:
    """Kernel com a cadeia Projeto -> Setor -> Sessao já montada."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def test_projeto_nasce_sem_pai_nominal() -> None:
    """Projeto é a raiz legítima: não pede aresta alguma."""
    kernel = montar_kernel_em_memoria()
    assert _submeter(kernel, _no("proj", TipoNo.PROJETO)).sucesso


def test_no_de_trabalho_pendurado_no_mesmo_lote_nominal() -> None:
    """A aresta 'produz' no mesmo lote basta para o nó nascer."""
    kernel = _kernel_com_sessao()
    recibo = _submeter(kernel, _no("art", TipoNo.ARTIFACT), _aresta("sess", "art", TipoAresta.PRODUZ))
    assert recibo.sucesso, recibo.mensagem


def test_task_decomposta_de_goal_esta_na_hierarquia_nominal() -> None:
    """'decompoe' também é contenção: a subtarefa pende do objetivo."""
    kernel = _kernel_com_sessao()
    assert _submeter(kernel, _no("goal", TipoNo.GOAL), _aresta("sess", "goal", TipoAresta.PRODUZ)).sucesso
    recibo = _submeter(kernel, _no("task", TipoNo.TASK), _aresta("goal", "task", TipoAresta.DECOMPOE))
    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, PapelAutor.EXECUTOR])
def test_no_solto_e_recusado_para_qualquer_papel_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: nem o humano cria nó órfão, e nada do lote é gravado."""
    kernel = _kernel_com_sessao()
    versao = kernel.obter_estado().versao_log
    recibo = _submeter(kernel, _no("art", TipoNo.ARTIFACT), papel=papel)
    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.NO_FORA_DA_HIERARQUIA.value
    assert "'produz' vinda de uma Sessao" in recibo.mensagem
    assert kernel.obter_estado().versao_log == versao


def test_aresta_que_nao_e_de_contencao_nao_basta_edge_case() -> None:
    """Caso de borda: 'deriva_de' liga o nó a outro, mas não o põe na hierarquia."""
    kernel = _kernel_com_sessao()
    assert _submeter(kernel, _no("task", TipoNo.TASK), _aresta("sess", "task", TipoAresta.PRODUZ)).sucesso
    recibo = _submeter(kernel, _no("art", TipoNo.ARTIFACT), _aresta("art", "task", TipoAresta.DERIVA_DE))
    assert recibo.modo_de_falha == ModoFalhaMAST.NO_FORA_DA_HIERARQUIA.value


def test_um_orfao_no_lote_recusa_o_lote_inteiro_edge_case() -> None:
    """Caso de borda: o nó pendurado não salva o vizinho solto do mesmo lote."""
    kernel = _kernel_com_sessao()
    recibo = _submeter(
        kernel,
        _no("ok", TipoNo.NOTE),
        _aresta("sess", "ok", TipoAresta.PRODUZ),
        _no("solto", TipoNo.NOTE),
    )
    assert recibo.modo_de_falha == ModoFalhaMAST.NO_FORA_DA_HIERARQUIA.value
    assert kernel.obter_estado().contem_no("ok") is False


def test_setor_sem_projeto_indica_a_aresta_esperada_edge_case() -> None:
    """Caso de borda: a recusa diz qual aresta falta para cada contêiner."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(kernel, _no("setor", TipoNo.SETOR))
    assert recibo.modo_de_falha == ModoFalhaMAST.NO_FORA_DA_HIERARQUIA.value
    assert "'contem' vinda de um Projeto" in recibo.mensagem


def test_edicao_de_no_existente_nao_e_afetada_nominal() -> None:
    """Só a criação é checada: editar um nó já existente segue livre."""
    kernel = _kernel_com_sessao()
    edicao = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/sess/propriedades/status", value="ativa")
    assert _submeter(kernel, edicao).sucesso
