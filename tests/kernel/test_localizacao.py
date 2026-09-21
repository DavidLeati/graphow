"""A Evidence de leitura de código nasce com o ponteiro inteiro: arquivo, linhas e trecho.

O explorador aponta trechos e o planejador registra o que leu neles. Sem o
ponteiro, uma interpretação errada ganharia autoridade de fato registrado.
"""

import pytest

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.localizacao import FaixaDeLinhas, diagnosticar_localizacao, interpretar_faixa
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

TRECHO_DE_TRES_LINHAS: str = 'def taxa_para_fator(taxa: float, dias: int) -> float:\n    """Desconto."""\n    return (1 + taxa) ** (-dias / 252)'
PONTEIRO: dict[str, object] = {"arquivo": "src/precos/fator.py", "linhas": "40-42", "trecho": TRECHO_DE_TRES_LINHAS}


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object] | None = None) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _propriedade(id_no: str, chave: str, valor: object, op: OperacaoPatch = OperacaoPatch.REPLACE) -> ItemPatch:
    """Escrita ou remoção de uma propriedade isolada."""
    return ItemPatch(op=op, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)


def _submeter(kernel: WriteKernel, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
    """Submete o lote sob o papel informado."""
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=operacoes, justificativa="teste")
    return kernel.submeter_patch(PropostaPatch.criar(dados))


@pytest.fixture
def kernel() -> WriteKernel:
    """Projeto, Setor e Sessao escritos pelo humano: o lugar onde a Evidence nasce."""
    kernel = montar_kernel_em_memoria()
    recibo = _submeter(
        kernel,
        PapelAutor.HUMANO,
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _registrar_evidencia(kernel: WriteKernel, papel: PapelAutor, propriedades: dict[str, object]) -> ResultadoSubmissao:
    """A Evidence pendurada na sessão pelo papel informado."""
    return _submeter(kernel, papel, _no("evi", TipoNo.EVIDENCE, propriedades), _aresta("sess", "evi", TipoAresta.PRODUZ))


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("120", FaixaDeLinhas(120, 120)), ("120-135", FaixaDeLinhas(120, 135)), (" 7 - 9 ", FaixaDeLinhas(7, 9)),
     ("120–135", FaixaDeLinhas(120, 135)), (42, FaixaDeLinhas(42, 42))],
)
def test_faixa_de_linhas_aceita_as_formas_que_um_ponteiro_usa_nominal(valor: object, esperado: FaixaDeLinhas) -> None:
    """Uma linha, uma faixa com hífen ou travessão, ou o inteiro puro."""
    assert interpretar_faixa(valor) == esperado


@pytest.mark.parametrize("valor", ["0", "135-120", "abc", "", True, 0, None, "12-", [1, 2]])
def test_faixa_de_linhas_recusa_o_que_nao_e_faixa_edge_case(valor: object) -> None:
    """Caso de borda: linha zero, faixa invertida, texto solto e tipos errados não são faixa."""
    assert interpretar_faixa(valor) is None


def test_diagnostico_aponta_o_campo_que_falta_nominal() -> None:
    """Cada lacuna tem a sua frase, para o autor corrigir sem adivinhar."""
    assert diagnosticar_localizacao(PONTEIRO) is None
    assert "arquivo" in str(diagnosticar_localizacao({**PONTEIRO, "arquivo": " "}))
    assert "linhas" in str(diagnosticar_localizacao({**PONTEIRO, "linhas": "x"}))
    assert "trecho" in str(diagnosticar_localizacao({**PONTEIRO, "trecho": ""}))


def test_trecho_maior_que_a_faixa_nao_e_literal_edge_case() -> None:
    """Caso de borda: três linhas de trecho numa faixa de duas não vieram daquelas linhas."""
    problema = diagnosticar_localizacao({**PONTEIRO, "linhas": "40-41"})

    assert problema is not None
    assert "3 linhas" in problema


def test_planejador_registra_leitura_localizada_e_a_liga_a_decisao_nominal(kernel: WriteKernel) -> None:
    """O orquestrador lê o trecho, registra a Evidence e justifica a decisão com ela."""
    recibo = _submeter(
        kernel,
        PapelAutor.PLANEJADOR,
        _no("evi", TipoNo.EVIDENCE, dict(PONTEIRO)),
        _aresta("sess", "evi", TipoAresta.PRODUZ),
        _no("dec", TipoNo.DECISION),
        _aresta("sess", "dec", TipoAresta.PRODUZ),
        _aresta("evi", "dec", TipoAresta.JUSTIFICA),
    )

    assert recibo.sucesso, recibo.mensagem


def test_planejador_sem_trecho_e_recusado_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: a conclusão sem o trecho que a sustenta não entra como fato."""
    recibo = _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, {"arquivo": "src/precos/fator.py", "linhas": "40-42"})

    assert recibo.sucesso is False
    assert recibo.modo_de_falha == "evidencia_sem_localizacao"
    assert "trecho" in recibo.mensagem


def test_planejador_sem_ponteiro_algum_e_recusado_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: a Evidence do planejador é sempre leitura de código, mesmo sem citar linhas."""
    recibo = _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, {"resumo": "o fator usa base 252"})

    assert recibo.modo_de_falha == "evidencia_sem_localizacao"


def test_executor_anexa_log_de_teste_sem_ponteiro_nominal(kernel: WriteKernel) -> None:
    """A saída de teste do executor cita o arquivo de log e não precisa de faixa de linhas."""
    recibo = _registrar_evidencia(kernel, PapelAutor.EXECUTOR, {"arquivo": "saida/pytest.log", "resultado": "14 passed"})

    assert recibo.sucesso, recibo.mensagem


def test_executor_com_ponteiro_pela_metade_e_recusado_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: quem cita linhas cita o ponteiro inteiro, de qualquer papel."""
    recibo = _registrar_evidencia(kernel, PapelAutor.EXECUTOR, {"arquivo": "src/precos/fator.py", "linhas": "40-42"})

    assert recibo.modo_de_falha == "evidencia_sem_localizacao"


def test_humano_tambem_nao_registra_ponteiro_pela_metade_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: a regra é sobre a forma do grafo, não sobre quem escreve."""
    recibo = _registrar_evidencia(kernel, PapelAutor.HUMANO, {"trecho": "return (1 + taxa) ** (-dias / 252)"})

    assert recibo.modo_de_falha == "evidencia_sem_localizacao"


@pytest.mark.parametrize(
    "edicao",
    [_propriedade("evi", "trecho", ""), _propriedade("evi", "trecho", None, OperacaoPatch.REMOVE),
     _propriedade("evi", "linhas", "42-40")],
)
def test_evidencia_localizada_nao_perde_o_ponteiro_depois_edge_case(kernel: WriteKernel, edicao: ItemPatch) -> None:
    """Caso de borda: nascer inteira e perder o trecho no lote seguinte também é recusado."""
    assert _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, dict(PONTEIRO)).sucesso

    recibo = _submeter(kernel, PapelAutor.PLANEJADOR, edicao)

    assert recibo.modo_de_falha == "evidencia_sem_localizacao"
    assert kernel.obter_view().obter_no("evi").obter_propriedade("trecho") == TRECHO_DE_TRES_LINHAS


def test_edicao_que_mantem_o_ponteiro_passa_nominal(kernel: WriteKernel) -> None:
    """Acrescentar a relevância a uma Evidence localizada não esbarra no portão."""
    assert _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, dict(PONTEIRO)).sucesso

    recibo = _submeter(kernel, PapelAutor.PLANEJADOR, _propriedade("evi", "relevancia", "converte taxa em fator", OperacaoPatch.ADD))

    assert recibo.sucesso, recibo.mensagem


def test_edicao_de_evidencia_antiga_sem_ponteiro_segue_livre_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: a Evidence do executor anterior à regra continua editável se não cita linhas."""
    assert _registrar_evidencia(kernel, PapelAutor.EXECUTOR, {"resultado": "14 passed"}).sucesso

    recibo = _submeter(kernel, PapelAutor.EXECUTOR, _propriedade("evi", "observacao", "rodado no CI", OperacaoPatch.ADD))

    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize(
    "edicao",
    [
        ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/evi/trecho", value="a\nb\nc\nd\ne"),
        ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/evi/linhas"),
        ItemPatch(op=OperacaoPatch.MOVE, path="/nos/evi/propriedades/trecho", from_path="/nos/evi/propriedades/rascunho"),
        ItemPatch(op=OperacaoPatch.COPY, path="/nos/evi/propriedades/linhas", from_path="/nos/evi/propriedades/rascunho"),
        ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/evi/propriedades/qualquer/trecho", value="a\nb\nc\nd\ne"),
    ],
)
def test_nenhum_caminho_de_edicao_escapa_do_portao_edge_case(kernel: WriteKernel, edicao: ItemPatch) -> None:
    """Caso de borda: o portão julga como o conversor grava, e não só o formato que ele esperava.

    `replace` em `/nos/<id>/trecho`, `remove` sem `/propriedades/`, `move`,
    `copy` e caminho mais fundo gravam a propriedade pelo último segmento; a
    projeção própria do portão deixava todos passarem. Cobra-se o resultado,
    o lote recusado e a Evidence intacta, e não qual portão o recusa.
    """
    assert _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, dict(PONTEIRO)).sucesso

    recibo = _submeter(kernel, PapelAutor.PLANEJADOR, edicao)

    assert recibo.sucesso is False
    assert kernel.obter_view().obter_no("evi").propriedades == PONTEIRO


def test_recriar_a_evidence_de_outro_papel_sem_ponteiro_e_recusado_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: um `add` sobre o id da Evidence de outro papel não a troca por uma sem ponteiro."""
    assert _registrar_evidencia(kernel, PapelAutor.EXECUTOR, {"resultado": "14 passed"}).sucesso

    recibo = _registrar_evidencia(kernel, PapelAutor.PLANEJADOR, {"resumo": "o fator usa base 252"})

    assert recibo.sucesso is False
    assert kernel.obter_view().obter_no("evi").proveniencia.papel == PapelAutor.EXECUTOR.value


def test_id_do_valor_diferente_do_caminho_nao_escapa_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: o conversor cria o nó pelo id do valor, e é por ele que o portão julga."""
    valor = {"id": "evi-escondida", "tipo": TipoNo.EVIDENCE.value, "rotulo": "x", "propriedades": {"resumo": "sem trecho"}}
    recibo = _submeter(
        kernel,
        PapelAutor.PLANEJADOR,
        ItemPatch(op=OperacaoPatch.ADD, path="/nos/outro-id", value=valor),
        _aresta("sess", "evi-escondida", TipoAresta.PRODUZ),
    )

    assert recibo.sucesso is False
    assert kernel.obter_view().obter_no("evi-escondida") is None


@pytest.mark.parametrize("trecho", ["\x0c\nint main(void) {", 'const s = "a\u2028b";\nreturn s;', "a\r\nb\r\n"])
def test_trecho_literal_com_caractere_raro_cabe_na_faixa_nominal(trecho: str) -> None:
    """Form feed e U+2028 aparecem dentro de linhas de código de verdade; só a quebra de linha separa."""
    assert diagnosticar_localizacao({"arquivo": "src/x.c", "linhas": "10-11", "trecho": trecho}) is None
