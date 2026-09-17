"""Memória diz de onde veio: o Aprendizado nos três portões.

Um Aprendizado sem `deriva_de` no mesmo lote é recusado como o nó sem aresta de
contenção. O alcance dele é a promoção, e promoção é do humano: nem a
propriedade `alcance` nem a aresta `vale_para` saem da mão de um agente.
"""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import NivelAutonomiaProjeto, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

PAPEIS_DE_AGENTE: tuple[PapelAutor, ...] = (PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR)
# Registra quem detém `deriva_de`: a origem obrigatória é aresta de proveniência.
PAPEIS_QUE_REGISTRAM: tuple[PapelAutor, ...] = (PapelAutor.EXECUTOR, PapelAutor.REVISOR)


def _no(id_no: str, tipo: TipoNo, **propriedades: str) -> ItemPatch:
    """Operação de criação de nó com rótulo igual ao id."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": dict(propriedades)},
    )


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO) -> ResultadoSubmissao:
    """Submete o lote sob o papel informado."""
    dados = DadosPropostaPatch(autor="autor-teste", papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _kernel_com_sessao(autonomia: str = NivelAutonomiaProjeto.ESTRITO.value) -> WriteKernel:
    """Projeto, setor e sessão, com uma decisão e uma evidência já produzidas."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        [
            _no("proj", TipoNo.PROJETO, nivel_autonomia=autonomia),
            _no("setor", TipoNo.SETOR),
            _aresta("proj", "setor", TipoAresta.CONTEM),
            _no("sess", TipoNo.SESSAO),
            _aresta("setor", "sess", TipoAresta.CONTEM),
            _no("dec-1", TipoNo.DECISION),
            _aresta("sess", "dec-1", TipoAresta.PRODUZ),
            _no("ev-1", TipoNo.EVIDENCE),
            _aresta("sess", "ev-1", TipoAresta.PRODUZ),
        ],
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _registrar(kernel: WriteKernel, papel: PapelAutor = PapelAutor.HUMANO, **propriedades: str) -> ResultadoSubmissao:
    """Cria o aprendizado 'apr' pendurado na sessão e derivado da decisão."""
    return _submeter(
        kernel,
        [
            _no("apr", TipoNo.APRENDIZADO, como_aplicar="siga a decisao", **propriedades),
            _aresta("sess", "apr", TipoAresta.PRODUZ),
            _aresta("apr", "dec-1", TipoAresta.DERIVA_DE),
        ],
        papel,
    )


@pytest.mark.parametrize("papel", [PapelAutor.HUMANO, PapelAutor.EXECUTOR])
def test_aprendizado_sem_origem_e_recusado_para_qualquer_papel_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: nem o humano registra memória sem dizer de onde veio."""
    kernel = _kernel_com_sessao()
    versao = kernel.obter_estado().versao_log

    recibo = _submeter(kernel, [_no("apr", TipoNo.APRENDIZADO), _aresta("sess", "apr", TipoAresta.PRODUZ)], papel)

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.APRENDIZADO_SEM_ORIGEM.value
    assert "deriva_de" in recibo.mensagem
    assert kernel.obter_estado().versao_log == versao


@pytest.mark.parametrize("papel", PAPEIS_QUE_REGISTRAM)
def test_quem_detem_deriva_de_registra_aprendizado_com_origem_nominal(papel: PapelAutor) -> None:
    """Executor e revisor registram; o portão só exige a origem."""
    kernel = _kernel_com_sessao()

    recibo = _registrar(kernel, papel)

    assert recibo.sucesso, recibo.mensagem
    assert kernel.obter_view().obter_no("apr").tipo == TipoNo.APRENDIZADO


def test_planejador_nao_registra_aprendizado_edge_case() -> None:
    """Caso de borda: quem só planeja não detém a camada de proveniência do trabalho."""
    kernel = _kernel_com_sessao()

    recibo = _registrar(kernel, PapelAutor.PLANEJADOR)

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_deriva_de_de_outro_no_no_lote_nao_conta_como_origem_edge_case() -> None:
    """Caso de borda: a origem tem de partir do próprio Aprendizado."""
    kernel = _kernel_com_sessao()

    recibo = _submeter(
        kernel,
        [
            _no("apr", TipoNo.APRENDIZADO),
            _aresta("sess", "apr", TipoAresta.PRODUZ),
            _no("nota", TipoNo.NOTE),
            _aresta("sess", "nota", TipoAresta.PRODUZ),
            _aresta("nota", "dec-1", TipoAresta.DERIVA_DE),
        ],
    )

    assert recibo.modo_de_falha == ModoFalhaMAST.APRENDIZADO_SEM_ORIGEM.value


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_declara_alcance_ao_registrar_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: escrever `alcance` na criação seria promover o próprio aprendizado."""
    kernel = _kernel_com_sessao()

    recibo = _registrar(kernel, papel, alcance="global")

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value
    assert "promover_aprendizado" in recibo.mensagem


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_escreve_alcance_depois_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: a propriedade isolada também é reservada ao humano."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso

    recibo = _submeter(
        kernel,
        [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/apr/propriedades/alcance", value="global")],
        papel,
    )

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


def test_humano_promove_por_propriedade_e_por_aresta_nominal() -> None:
    """A promoção tem duas formas: a marca global e o alcance por contêiner."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso

    global_ = _submeter(kernel, [ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/apr/propriedades/alcance", value="global")])
    por_aresta = _submeter(kernel, [_aresta("apr", "setor", TipoAresta.VALE_PARA)])

    assert global_.sucesso and por_aresta.sucesso
    view = kernel.obter_view()
    assert view.obter_no("apr").obter_propriedade("alcance") == "global"
    assert view.obter_arestas_saida("apr", TipoAresta.VALE_PARA)[0].destino_id == "setor"


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_cria_vale_para_nem_sob_autonomia_ilimitada_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: a autonomia amplia a estrutura, nunca a promoção de memória."""
    kernel = _kernel_com_sessao(NivelAutonomiaProjeto.ILIMITADO.value)
    assert _registrar(kernel).sucesso

    recibo = _submeter(kernel, [_aresta("apr", "proj", TipoAresta.VALE_PARA)], papel)

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value


@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE)
def test_agente_nao_remove_aprendizado_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: memória é substituída ou contradita, nunca apagada por agente."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso

    recibo = _submeter(kernel, [ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/apr")], papel)

    assert recibo.sucesso is False
    assert kernel.obter_view().contem_no("apr") is True


def test_humano_remove_aprendizado_nominal() -> None:
    """A porta segue aberta para quem tem a chave."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso

    assert _submeter(kernel, [ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/apr")]).sucesso is True


def test_substitui_entre_aprendizados_e_contradiz_de_evidencia_passam_no_schema_nominal() -> None:
    """Esquecer é marcar: os dois pares que a vista lê existem na ontologia."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso
    novo = _submeter(
        kernel,
        [
            _no("apr-2", TipoNo.APRENDIZADO),
            _aresta("sess", "apr-2", TipoAresta.PRODUZ),
            _aresta("apr-2", "ev-1", TipoAresta.DERIVA_DE),
            _aresta("apr-2", "apr", TipoAresta.SUBSTITUI),
        ],
    )
    contradicao = _submeter(kernel, [_aresta("ev-1", "apr-2", TipoAresta.CONTRADIZ)])

    assert novo.sucesso, novo.mensagem
    assert contradicao.sucesso, contradicao.mensagem


def test_vale_para_um_no_de_trabalho_e_recusado_pelo_schema_edge_case() -> None:
    """Caso de borda: o alcance é por contêiner; uma Task não é alcance."""
    kernel = _kernel_com_sessao()
    assert _registrar(kernel).sucesso

    recibo = _submeter(kernel, [_aresta("apr", "dec-1", TipoAresta.VALE_PARA)])

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == ModoFalhaMAST.PAR_DE_ARESTA_INVALIDO.value
