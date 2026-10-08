"""As quatro arestas do escopo governado (ontologia 1.5.0): pares, donos e o que a Task travada exige."""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.invariant_gate import ARESTAS_QUE_REDEFINEM_A_TAREFA
from graphow.kernel.matriz_papeis import HUMANO_E_PLANEJADOR, SO_HUMANO, obter_donos_de_aresta
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.schema_gate import SchemaGate
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

ARESTAS_DO_ESCOPO = [TipoAresta.MOTIVADA_POR, TipoAresta.ACOMPANHA, TipoAresta.INTEGRA, TipoAresta.DESFAZ]
AGENTES_SEM_PLANEJADOR = [PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.ARBITRO]

PARES_ESPERADOS = {
    TipoAresta.MOTIVADA_POR: {
        (TipoNo.TASK, TipoNo.DECISION),
        (TipoNo.TASK, TipoNo.EVIDENCE),
        (TipoNo.TASK, TipoNo.TASK),
        (TipoNo.TASK, TipoNo.QUESTION),
        (TipoNo.DECISION, TipoNo.DECISION),
        (TipoNo.DECISION, TipoNo.EVIDENCE),
        (TipoNo.DECISION, TipoNo.TASK),
        (TipoNo.DECISION, TipoNo.QUESTION),
    },
    TipoAresta.ACOMPANHA: {(TipoNo.TASK, TipoNo.EVIDENCE)},
    TipoAresta.INTEGRA: {(TipoNo.TASK, TipoNo.TASK)},
    TipoAresta.DESFAZ: {(TipoNo.TASK, TipoNo.DECISION)},
}

# Um par válido de cada tipo, com os ids do cenário.
LIGACAO_VALIDA = {
    TipoAresta.MOTIVADA_POR: ("t1", "dec"),
    TipoAresta.ACOMPANHA: ("t1", "ev"),
    TipoAresta.INTEGRA: ("t1", "t2"),
    TipoAresta.DESFAZ: ("t1", "dec"),
}


def _no(id_no: str, tipo: TipoNo) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": id_no})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
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


def _kernel() -> WriteKernel:
    """Projeto, Setor e Sessão que produz um Goal, duas Tasks, uma Decision, uma Evidence e uma Question."""
    kernel = montar_kernel_em_memoria()
    produzidos = [
        _no("goal", TipoNo.GOAL),
        _no("t1", TipoNo.TASK),
        _no("t2", TipoNo.TASK),
        _no("dec", TipoNo.DECISION),
        _no("ev", TipoNo.EVIDENCE),
        _no("q", TipoNo.QUESTION),
    ]
    recibo = _submeter(
        kernel,
        PapelAutor.HUMANO,
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        *produzidos,
        *(_aresta("sess", item.value["id"], TipoAresta.PRODUZ) for item in produzidos),
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
def test_pares_das_arestas_do_escopo_sao_os_declarados_nominal(tipo: TipoAresta) -> None:
    """O SchemaGate admite exatamente os pares do contrato, e nenhum a mais."""
    assert set(SchemaGate.PARES_ARESTAS_PERMITIDOS[tipo]) == PARES_ESPERADOS[tipo]


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
def test_donos_das_arestas_do_escopo_nominal(tipo: TipoAresta) -> None:
    """Humano e planejador criam; só o humano retira o vínculo."""
    donos = obter_donos_de_aresta(tipo)
    assert donos.adicao == HUMANO_E_PLANEJADOR
    assert donos.remocao == SO_HUMANO


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
def test_arestas_do_escopo_redefinem_a_tarefa_nominal(tipo: TipoAresta) -> None:
    """Numa Task travada, só o dono do lock liga ou desliga o vínculo de escopo."""
    assert tipo in ARESTAS_QUE_REDEFINEM_A_TAREFA


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, PapelAutor.PLANEJADOR])
def test_humano_e_planejador_criam_a_aresta_nominal(tipo: TipoAresta, papel: PapelAutor) -> None:
    """O par válido passa pelos quatro portões para quem é dono da criação."""
    origem, destino = LIGACAO_VALIDA[tipo]
    recibo = _submeter(_kernel(), papel, _aresta(origem, destino, tipo))
    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
@pytest.mark.parametrize("papel", AGENTES_SEM_PLANEJADOR)
def test_executor_revisor_e_arbitro_nao_criam_a_aresta_edge_case(tipo: TipoAresta, papel: PapelAutor) -> None:
    """Caso de borda: quem executa não liga a própria Task a um motivo para fugir do plano."""
    origem, destino = LIGACAO_VALIDA[tipo]
    recibo = _submeter(_kernel(), papel, _aresta(origem, destino, tipo))
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
def test_so_o_humano_remove_a_aresta_edge_case(tipo: TipoAresta) -> None:
    """Caso de borda: o planejador cria e não retira; o humano retira."""
    origem, destino = LIGACAO_VALIDA[tipo]
    kernel = _kernel()
    assert _submeter(kernel, PapelAutor.PLANEJADOR, _aresta(origem, destino, tipo)).sucesso
    remocao = ItemPatch(op=OperacaoPatch.REMOVE, path=f"/arestas/{tipo.value}-{origem}-{destino}")

    assert not _submeter(kernel, PapelAutor.PLANEJADOR, remocao).sucesso
    assert _submeter(kernel, PapelAutor.HUMANO, remocao).sucesso


@pytest.mark.parametrize("tipo", ARESTAS_DO_ESCOPO)
def test_par_fora_da_tabela_e_recusado_ate_ao_humano_edge_case(tipo: TipoAresta) -> None:
    """Caso de borda: Evidence não motiva nem acompanha nada, e a Question não é Task."""
    recibo = _submeter(_kernel(), PapelAutor.HUMANO, _aresta("ev", "t1", tipo))
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.PAR_DE_ARESTA_INVALIDO.value
