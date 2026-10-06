"""Vocabulário da governança: o tipo Governanca é do humano e o papel árbitro nasce enxuto."""

import pytest

from graphow.core.governanca import ID_GOVERNANCA_GLOBAL
from graphow.core.ontologia import ASSINATURA_DECLARADA, VERSAO_ONTOLOGIA, calcular_assinatura_da_ontologia
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.matriz_papeis import TIPOS_EXCLUSIVOS_DO_HUMANO, TODOS_OS_PAPEIS_DE_AGENTE, obter_donos_de_aresta
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.role_gate import RoleGate
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

PAPEIS_DE_AGENTE = [PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.ARBITRO]


def _no(id_no: str, tipo: TipoNo, **propriedades: str) -> ItemPatch:
    """Operação de criação de nó com rótulo igual ao id."""
    valor: dict[str, object] = {"id": id_no, "tipo": tipo.value, "rotulo": id_no}
    if propriedades:
        valor["propriedades"] = propriedades
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _submeter(kernel: WriteKernel, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
    """Submete o lote sob o papel pedido."""
    autor = "david" if papel == PapelAutor.HUMANO else f"{papel.value}-1"
    dados = DadosPropostaPatch(autor=autor, papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _kernel(nivel: str = "estrito", *, com_governanca: bool = True) -> WriteKernel:
    """Kernel com Projeto -> Setor -> Sessao e, por padrão, o Governanca global já criado pelo humano."""
    kernel = montar_kernel_em_memoria()
    governanca = [_no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA)] if com_governanca else []
    recibo = _submeter(
        kernel,
        PapelAutor.HUMANO,
        _no("proj", TipoNo.PROJETO, nivel_autonomia=nivel),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        *governanca,
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def test_versao_e_assinatura_da_ontologia_nominal() -> None:
    """A 1.4.0 mantém o tipo e o papel da 1.3.0, e a assinatura declarada os confere."""
    assert VERSAO_ONTOLOGIA == "1.4.0"
    assert calcular_assinatura_da_ontologia() == ASSINATURA_DECLARADA


def test_vocabulario_novo_nominal() -> None:
    """Governanca é exclusivo do humano e o árbitro é um papel de agente."""
    assert TipoNo.GOVERNANCA.value == "Governanca"
    assert PapelAutor.ARBITRO.value == "arbitro"
    assert TipoNo.GOVERNANCA in TIPOS_EXCLUSIVOS_DO_HUMANO
    assert PapelAutor.ARBITRO in TODOS_OS_PAPEIS_DE_AGENTE
    assert TipoNo.GOVERNANCA not in RoleGate.NOS_CRIACAO_SOB_AUTONOMIA_ILIMITADA


def test_humano_cria_governanca_sem_aresta_de_contencao_nominal() -> None:
    """Governanca é raiz como o Projeto: nasce sem pai e o lote passa."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(kernel, PapelAutor.HUMANO, _no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA))
    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("nivel", ["estrito", "ilimitado"])
@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_cria_governanca_edge_case(papel: PapelAutor, nivel: str) -> None:
    """Nenhum papel de agente cria Governanca, nem sob autonomia ilimitada."""
    kernel = _kernel(nivel, com_governanca=False)
    recibo = _submeter(kernel, papel, _no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA))
    assert not recibo.sucesso
    assert "Governanca" in recibo.mensagem


@pytest.mark.parametrize("nivel", ["estrito", "ilimitado"])
@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_edita_nem_remove_governanca_edge_case(papel: PapelAutor, nivel: str) -> None:
    """Editar rótulo ou propriedade e remover o nó são recusados a todo agente."""
    kernel = _kernel(nivel)
    edicoes = (
        ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/governanca-global/rotulo", value="outro"),
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/governanca-global/propriedades/politica", value="x"),
        ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/governanca-global"),
    )
    for edicao in edicoes:
        assert not _submeter(kernel, papel, edicao).sucesso, edicao.path
    assert ID_GOVERNANCA_GLOBAL in kernel.obter_estado().nos


def test_humano_edita_e_remove_governanca_nominal() -> None:
    """O meta-portão é do humano: ele segue podendo editar e remover."""
    kernel = _kernel()
    editar = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/governanca-global/rotulo", value="outro")
    assert _submeter(kernel, PapelAutor.HUMANO, editar).sucesso
    assert _submeter(kernel, PapelAutor.HUMANO, ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/governanca-global")).sucesso


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, *PAPEIS_DE_AGENTE])
@pytest.mark.parametrize("tipo", list(TipoAresta))
def test_nenhuma_aresta_toca_governanca_edge_case(tipo: TipoAresta, papel: PapelAutor) -> None:
    """Como origem ou destino, qualquer aresta em Governanca é recusada, até ao humano."""
    kernel = _kernel("ilimitado")
    for origem, destino in ((ID_GOVERNANCA_GLOBAL, "sess"), ("proj", ID_GOVERNANCA_GLOBAL), ("sess", ID_GOVERNANCA_GLOBAL)):
        recibo = _submeter(kernel, papel, _aresta(origem, destino, tipo))
        assert not recibo.sucesso, (origem, destino)


def test_aresta_em_governanca_diz_o_motivo_edge_case() -> None:
    """A recusa do SchemaGate nomeia o Governanca em vez de um par genérico."""
    kernel = _kernel()
    recibo = _submeter(kernel, PapelAutor.HUMANO, _aresta("proj", ID_GOVERNANCA_GLOBAL, TipoAresta.CONTEM))
    assert not recibo.sucesso
    assert "Governanca" in recibo.mensagem


def test_arbitro_cria_evidence_decision_e_note_nominal() -> None:
    """O árbitro registra o que sustenta um julgamento."""
    kernel = _kernel()
    for id_no, tipo in (("ev", TipoNo.EVIDENCE), ("dec", TipoNo.DECISION), ("nota", TipoNo.NOTE)):
        recibo = _submeter(kernel, PapelAutor.ARBITRO, _no(id_no, tipo), _aresta("sess", id_no, TipoAresta.PRODUZ))
        assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("tipo", [TipoNo.TASK, TipoNo.CONSTRAINT])
def test_arbitro_nao_cria_task_nem_constraint_em_projeto_estrito_edge_case(tipo: TipoNo) -> None:
    """Task e Constraint seguem fora do vocabulário do árbitro."""
    kernel = _kernel("estrito")
    recibo = _submeter(kernel, PapelAutor.ARBITRO, _no("x", tipo), _aresta("sess", "x", TipoAresta.PRODUZ))
    assert not recibo.sucesso


def test_arbitro_nao_cria_constraint_nem_sob_autonomia_ilimitada_edge_case() -> None:
    """Constraint é exclusiva do humano mesmo num projeto ilimitado."""
    kernel = _kernel("ilimitado")
    recibo = _submeter(
        kernel, PapelAutor.ARBITRO, _no("c", TipoNo.CONSTRAINT), _aresta("sess", "c", TipoAresta.PRODUZ)
    )
    assert not recibo.sucesso


def test_arbitro_ganha_produz_bloqueia_e_substitui_entre_aprendizados_nominal() -> None:
    """O árbitro entra entre os agentes que escrevem produz, abrem bloqueia e substituem Aprendizados."""
    assert PapelAutor.ARBITRO in obter_donos_de_aresta(TipoAresta.PRODUZ).adicao
    assert PapelAutor.ARBITRO in obter_donos_de_aresta(TipoAresta.BLOQUEIA).adicao
    assert PapelAutor.ARBITRO not in obter_donos_de_aresta(TipoAresta.BLOQUEIA).remocao
    par = (TipoNo.APRENDIZADO, TipoNo.APRENDIZADO)
    assert PapelAutor.ARBITRO in obter_donos_de_aresta(TipoAresta.SUBSTITUI, par).adicao
