"""A Evidence de veredito de escopo deriva da raiz que julga, seja ela Decision, Evidence, Question ou Task."""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.matriz_papeis import HUMANO_E_REVISOR, obter_donos_de_aresta
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.schema_gate import SchemaGate
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

RAIZES_NOVAS = {"dec": TipoNo.DECISION, "ev": TipoNo.EVIDENCE, "q": TipoNo.QUESTION}
PROPRIEDADES_DO_VEREDITO = {"acao": "veredito_de_escopo", "parecer_de_escopo": "cabe", "motivo": "dentro do criterio c1"}


def _no(id_no: str, tipo: TipoNo, **propriedades: object) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


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
    """Sessão que produz um Goal, uma Task e as raízes possíveis de uma cadeia de decisão."""
    kernel = montar_kernel_em_memoria()
    produzidos = [_no("goal", TipoNo.GOAL), _no("t1", TipoNo.TASK)]
    produzidos += [_no(id_no, tipo) for id_no, tipo in RAIZES_NOVAS.items()]
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


def _veredito_que_deriva_de(kernel: WriteKernel, papel: PapelAutor, raiz: str) -> ResultadoSubmissao:
    """Nova Evidence de veredito de escopo, produzida pela sessão, derivada da raiz."""
    return _submeter(
        kernel,
        papel,
        _no("ev-veredito", TipoNo.EVIDENCE, **PROPRIEDADES_DO_VEREDITO),
        _aresta("sess", "ev-veredito", TipoAresta.PRODUZ),
        _aresta("ev-veredito", raiz, TipoAresta.DERIVA_DE),
    )


@pytest.mark.parametrize("destino", [TipoNo.DECISION, TipoNo.EVIDENCE, TipoNo.QUESTION])
def test_schema_admite_evidence_derivada_de_toda_raiz_nominal(destino: TipoNo) -> None:
    """O SchemaGate admite Evidence -> Decision, Evidence e Question, além da Task que já admitia."""
    pares = SchemaGate.PARES_ARESTAS_PERMITIDOS[TipoAresta.DERIVA_DE]
    assert (TipoNo.EVIDENCE, destino) in pares
    assert (TipoNo.EVIDENCE, TipoNo.TASK) in pares


@pytest.mark.parametrize("raiz", [*RAIZES_NOVAS, "t1"])
@pytest.mark.parametrize("papel", [PapelAutor.REVISOR, PapelAutor.HUMANO])
def test_revisor_e_humano_gravam_o_veredito_de_qualquer_raiz_nominal(raiz: str, papel: PapelAutor) -> None:
    """O revisor, que julga a revisão de escopo, grava o veredito derivado de Decision, Evidence, Question e Task."""
    recibo = _veredito_que_deriva_de(_kernel(), papel, raiz)
    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize("raiz", RAIZES_NOVAS)
@pytest.mark.parametrize("papel", [PapelAutor.EXECUTOR, PapelAutor.PLANEJADOR, PapelAutor.ARBITRO])
def test_quem_nao_julga_nao_deriva_veredito_da_decisao_edge_case(raiz: str, papel: PapelAutor) -> None:
    """Caso de borda: o executor não tira a raiz da lista de pendências dando-se o veredito de escopo."""
    recibo = _veredito_que_deriva_de(_kernel(), papel, raiz)
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_donos_dos_tres_pares_novos_sao_humano_e_revisor_nominal() -> None:
    """A tabela por par entrega a criação e a retirada ao humano e ao revisor."""
    for destino in RAIZES_NOVAS.values():
        donos = obter_donos_de_aresta(TipoAresta.DERIVA_DE, (TipoNo.EVIDENCE, destino))
        assert donos.adicao == HUMANO_E_REVISOR
        assert donos.remocao == HUMANO_E_REVISOR


def test_deriva_de_da_task_segue_aberto_ao_trabalho_edge_case() -> None:
    """Caso de borda: a regra por par não fecha Evidence -> Task, que o executor usa desde sempre."""
    recibo = _veredito_que_deriva_de(_kernel(), PapelAutor.EXECUTOR, "t1")
    assert recibo.sucesso, recibo.mensagem
