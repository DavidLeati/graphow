"""Testes do acervo: uma nota por aprendizado promovido, regenerável do zero e sem deriva."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.notas import EscritorDeAcervoEmMemoria, GeradorDeAcervo, extrair_notas
from graphow.notas.renderizador import NOME_DO_INDICE, renderizar_indice, renderizar_nota


def _no(id_no: str, tipo: TipoNo, rotulo: str, **propriedades: str) -> ItemPatch:
    """Operação de criação de nó com propriedades opcionais."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo, "propriedades": dict(propriedades)},
    )


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _montar_kernel() -> WriteKernel:
    """Dois aprendizados promovidos (um substitui o outro), um contradito e um sem promoção."""
    kernel = montar_kernel_em_memoria()
    dados = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[
            _no("proj", TipoNo.PROJETO, "Projeto"),
            _no("setor", TipoNo.SETOR, "Setor"),
            _aresta("proj", "setor", TipoAresta.CONTEM),
            _no("sess", TipoNo.SESSAO, "Sessao"),
            _aresta("setor", "sess", TipoAresta.CONTEM),
            _no("dec-1", TipoNo.DECISION, "Transacao unica por lote"),
            _aresta("sess", "dec-1", TipoAresta.PRODUZ),
            _no("ev-1", TipoNo.EVIDENCE, "Sonda de 17 casos"),
            _aresta("sess", "ev-1", TipoAresta.PRODUZ),
            _no("apr-velho", TipoNo.APRENDIZADO, "Rollup incremental por aresta", como_aplicar="Nao faca"),
            _aresta("sess", "apr-velho", TipoAresta.PRODUZ),
            _aresta("apr-velho", "dec-1", TipoAresta.DERIVA_DE),
            _aresta("apr-velho", "proj", TipoAresta.VALE_PARA),
            _no("apr-novo", TipoNo.APRENDIZADO, "Rollup inteiro por commit", como_aplicar="Recalcule tudo", alcance="global"),
            _aresta("sess", "apr-novo", TipoAresta.PRODUZ),
            _aresta("apr-novo", "dec-1", TipoAresta.DERIVA_DE),
            _aresta("apr-novo", "ev-1", TipoAresta.DERIVA_DE),
            _aresta("apr-novo", "apr-velho", TipoAresta.SUBSTITUI),
            _aresta("ev-1", "apr-velho", TipoAresta.CONTRADIZ),
            _no("apr-solto", TipoNo.APRENDIZADO, "Nunca promovido"),
            _aresta("sess", "apr-solto", TipoAresta.PRODUZ),
            _aresta("apr-solto", "dec-1", TipoAresta.DERIVA_DE),
        ],
        justificativa="cenario",
    )
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem
    return kernel


def test_so_o_aprendizado_promovido_vira_nota_nominal() -> None:
    """O acervo é dos aprendizados com alcance; o não promovido fica só no grafo."""
    notas = extrair_notas(_montar_kernel().obter_view())

    assert [nota.id for nota in notas] == ["apr-velho", "apr-novo"]


def test_nota_diz_a_afirmacao_como_se_sabe_e_como_aplicar_nominal() -> None:
    """A regra única do acervo: uma afirmação sem origem não é nota."""
    notas = {nota.id: nota for nota in extrair_notas(_montar_kernel().obter_view())}

    texto = renderizar_nota(notas["apr-novo"])

    assert texto.startswith("# Rollup inteiro por commit")
    assert "**Como se sabe:** [Decision] Transacao unica por lote (`dec-1`, log #" in texto
    assert "[Evidence] Sonda de 17 casos (`ev-1`, log #" in texto
    assert "**Como aplicar:** Recalcule tudo" in texto
    assert "- Alcance: global" in texto
    assert "- Registrado por: david (humano), log #" in texto


def test_links_entre_notas_saem_das_arestas_de_substituicao_e_contradicao_nominal() -> None:
    """A nota vencida aponta para a que a substituiu e cita quem a contradisse."""
    notas = {nota.id: nota for nota in extrair_notas(_montar_kernel().obter_view())}

    texto = renderizar_nota(notas["apr-velho"])

    assert "- Substituído por: [[apr-novo]] (não siga esta nota)" in texto
    assert "- Contradito por: [Evidence] Sonda de 17 casos (`ev-1`, log #" in texto
    assert "- Alcance: proj" in texto


def test_indice_agrupa_por_alcance_e_marca_a_substituida_nominal() -> None:
    """O índice é o mapa do acervo: global primeiro, depois cada contêiner."""
    texto = renderizar_indice(extrair_notas(_montar_kernel().obter_view()))

    assert "2 notas · 1 vigentes · 1 substituídas" in texto
    assert texto.index("## global") < texto.index("## proj")
    assert "- [[apr-novo]] Rollup inteiro por commit" in texto
    assert "- [[apr-velho]] Rollup incremental por aresta (substituída)" in texto


def test_publicar_grava_indice_e_uma_nota_por_aprendizado_e_remove_o_que_sobrou_nominal() -> None:
    """Uma nota escrita à mão no diretório não sobrevive à geração: o grafo é a fonte."""
    escritor = EscritorDeAcervoEmMemoria({"escrita-a-mao.md": "isto nao veio do grafo"})
    notas = extrair_notas(_montar_kernel().obter_view())

    resultado = GeradorDeAcervo(escritor).publicar(notas)

    assert resultado.documentos_escritos == 3
    assert resultado.documentos_removidos == ("escrita-a-mao.md",)
    assert set(escritor.documentos) == {NOME_DO_INDICE, "apr-velho.md", "apr-novo.md"}


def test_conferir_acusa_deriva_e_silencia_quando_esta_em_dia_nominal() -> None:
    """A conferência nomeia o que diverge, falta ou sobra, e nada quando bate."""
    escritor = EscritorDeAcervoEmMemoria()
    notas = extrair_notas(_montar_kernel().obter_view())
    gerador = GeradorDeAcervo(escritor)
    gerador.publicar(notas)
    assert gerador.conferir(notas) == ()

    escritor.documentos["apr-novo.md"] = "editado a mao"
    escritor.documentos["sobra.md"] = "nao veio do grafo"
    escritor.documentos.pop("apr-velho.md")

    assert gerador.conferir(notas) == ("apr-novo.md", "apr-velho.md", "sobra.md")


def test_acervo_regenerado_do_zero_e_identico_edge_case() -> None:
    """Caso de borda: a geração é determinística; duas montagens do mesmo grafo batem byte a byte."""
    primeira = GeradorDeAcervo(EscritorDeAcervoEmMemoria()).montar_documentos(extrair_notas(_montar_kernel().obter_view()))
    segunda = GeradorDeAcervo(EscritorDeAcervoEmMemoria()).montar_documentos(extrair_notas(_montar_kernel().obter_view()))

    assert [(doc.caminho_relativo, doc.conteudo) for doc in primeira] == [
        (doc.caminho_relativo, doc.conteudo) for doc in segunda
    ]


def test_origem_removida_do_grafo_e_dita_removida_edge_case() -> None:
    """Caso de borda: a nota não inventa rótulo para um nó que já não existe."""
    kernel = _montar_kernel()
    remocao = DadosPropostaPatch(
        autor="david",
        papel=PapelAutor.HUMANO,
        operacoes=[ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/ev-1")],
        justificativa="remocao",
    )
    assert kernel.submeter_patch(PropostaPatch.criar(remocao)).sucesso
    view = kernel.obter_view()

    notas = {nota.id: nota for nota in extrair_notas(view)}

    origens = {origem.id: origem for origem in notas["apr-novo"].origens}
    assert "ev-1" not in origens
    assert origens["dec-1"].tipo == "Decision"
