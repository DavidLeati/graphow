"""Testes da seção Aprendizados Aplicaveis: herança, léxico, índice injetável e as marcas de esquecimento."""

from collections.abc import Sequence

from graphow.context.aprendizados_aplicaveis import (
    LIMITE_DE_LINHAS_INTEIRAS_POR_HERANCA,
    SUFIXO_DE_LINHAS_CURTAS,
    TITULO_APRENDIZADOS,
    IndiceSemantico,
    PedidoDeMemoria,
    montar_secao_de_aprendizados,
)
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.secoes import MARCA_DE_CONTEUDO_NAO_CONFIAVEL, PrioridadeRetencao
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel

ORCAMENTO: int = 2000


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


def _submeter(kernel: WriteKernel, operacoes: list[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO) -> None:
    """Submete o lote sob o papel informado, exigindo aceitação."""
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem


def _hierarquia(sufixo: str, titulo_da_tarefa: str) -> list[ItemPatch]:
    """Projeto, setor, sessão e uma tarefa, todos com o sufixo informado."""
    return [
        _no(f"proj-{sufixo}", TipoNo.PROJETO, f"Projeto {sufixo}"),
        _no(f"setor-{sufixo}", TipoNo.SETOR, f"Setor {sufixo}"),
        _aresta(f"proj-{sufixo}", f"setor-{sufixo}", TipoAresta.CONTEM),
        _no(f"sess-{sufixo}", TipoNo.SESSAO, f"Sessao {sufixo}"),
        _aresta(f"setor-{sufixo}", f"sess-{sufixo}", TipoAresta.CONTEM),
        _no(f"task-{sufixo}", TipoNo.TASK, titulo_da_tarefa, status="pendente"),
        _aresta(f"sess-{sufixo}", f"task-{sufixo}", TipoAresta.PRODUZ),
    ]


def _aprendizado(id_no: str, rotulo: str, origem: str = "dec-a", **propriedades: str) -> list[ItemPatch]:
    """Aprendizado produzido pela sessão A e derivado da origem informada."""
    return [
        _no(id_no, TipoNo.APRENDIZADO, rotulo, **propriedades),
        _aresta("sess-a", id_no, TipoAresta.PRODUZ),
        _aresta(id_no, origem, TipoAresta.DERIVA_DE),
    ]


def _montar_kernel() -> WriteKernel:
    """Dois projetos; a memória nasce no primeiro e é promovida de formas distintas."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            *_hierarquia("a", "Definir a politica de eviccao do cache"),
            _no("dec-a", TipoNo.DECISION, "Decisao A"),
            _aresta("sess-a", "dec-a", TipoAresta.PRODUZ),
            _no("ev-a", TipoNo.EVIDENCE, "Evidencia A"),
            _aresta("sess-a", "ev-a", TipoAresta.PRODUZ),
            *_hierarquia("b", "Escolher a politica de eviccao"),
            _no("task-b2", TipoNo.TASK, "Migrar o banco antigo", status="pendente"),
            _aresta("sess-b", "task-b2", TipoAresta.PRODUZ),
        ],
    )
    _submeter(
        kernel,
        [
            *_aprendizado("apr-global", "Descarte por secao, nunca linha a linha", alcance="global", como_aplicar="Desca a escada de corte"),
            *_aprendizado("apr-proj", "Lote recusado inteiro sem contencao"),
            _aresta("apr-proj", "proj-a", TipoAresta.VALE_PARA),
            *_aprendizado("apr-setor", "Politica de eviccao por LRU com teto", como_aplicar="Meca o teto antes"),
            _aresta("apr-setor", "setor-a", TipoAresta.VALE_PARA),
            *_aprendizado("apr-velho", "Rollup incremental por aresta"),
            _aresta("apr-velho", "proj-a", TipoAresta.VALE_PARA),
            _aresta("apr-proj", "apr-velho", TipoAresta.SUBSTITUI),
            *_aprendizado("apr-expirado", "Memoria vencida", alcance="global", valido_ate="2000-01-01T00:00:00+00:00"),
            *_aprendizado("apr-contradito", "Reprocessar o log inteiro a cada commit"),
            _aresta("apr-contradito", "proj-a", TipoAresta.VALE_PARA),
            _aresta("ev-a", "apr-contradito", TipoAresta.CONTRADIZ),
            *_aprendizado("apr-solto", "Nunca promovido"),
        ],
    )
    _submeter(kernel, _aprendizado("apr-agente", "Escrito por agente", origem="ev-a"), PapelAutor.EXECUTOR)
    _submeter(kernel, [_aresta("apr-agente", "proj-a", TipoAresta.VALE_PARA)])
    return kernel


def _vista(kernel: WriteKernel, id_alvo: str, materializador: MaterializadorContexto | None = None) -> str:
    """Materializa a vista do planejador sobre o alvo."""
    requisicao = RequisicaoVista(id_alvo=id_alvo, papel=PapelAutor.PLANEJADOR, orcamento_tokens=ORCAMENTO)
    return (materializador or MaterializadorContexto()).materializar(requisicao, kernel.obter_view()).conteudo_formatado


def _linha_de(conteudo: str, id_no: str) -> str:
    """A linha da vista que cita o nó informado."""
    return next(linha for linha in conteudo.splitlines() if f"[{id_no}]" in linha)


def test_tarefa_herda_do_projeto_do_setor_e_do_global_nominal() -> None:
    """Herança pela hierarquia resolve o mesmo projeto sem busca nenhuma."""
    conteudo = _vista(_montar_kernel(), "task-a")

    assert f"## {TITULO_APRENDIZADOS} (herdados de global, proj-a, setor-a; {SUFIXO_DE_LINHAS_CURTAS})" in conteudo
    for id_no in ("apr-global", "apr-proj", "apr-setor"):
        assert f"[{id_no}]" in conteudo


def test_substituido_por_promovido_sai_da_vista_e_o_substituto_diz_quem_absorveu_nominal() -> None:
    """A vista carrega só o vigente: o antigo fica no grafo, e a linha do novo o cita."""
    conteudo = _vista(_montar_kernel(), "task-a")

    assert "[apr-velho]" not in conteudo
    assert "[substitui apr-velho]" in _linha_de(conteudo, "apr-proj")


def test_contradito_fica_marcado_e_nao_some_nominal() -> None:
    """Contradito não é substituído: segue valendo, com o pedido de revisão."""
    conteudo = _vista(_montar_kernel(), "task-a")

    assert "[CONTRADITO por ev-a: precisa de revisao]" in _linha_de(conteudo, "apr-contradito")


def test_substituto_sem_promocao_nao_tira_o_antigo_da_vista_edge_case() -> None:
    """Caso de borda: substituir é propor; até o humano promover o novo, o antigo vale, avisado."""
    kernel = _montar_kernel()
    novo = _aprendizado("apr-novo", "Politica de eviccao por LRU com teto e janela", origem="ev-a")
    _submeter(kernel, novo, PapelAutor.EXECUTOR)
    _submeter(kernel, [_aresta("apr-novo", "apr-setor", TipoAresta.SUBSTITUI)])

    conteudo = _vista(kernel, "task-a")

    assert "[apr-novo]" not in conteudo
    assert "[SUBSTITUTO PENDENTE: apr-novo aguarda promocao, siga este ate la]" in _linha_de(conteudo, "apr-setor")


def test_expirado_e_nao_promovido_nao_aparecem_edge_case() -> None:
    """Caso de borda: `valido_ate` vencido e ausência de alcance tiram o aprendizado da vista."""
    conteudo = _vista(_montar_kernel(), "task-a")

    assert "apr-expirado" not in conteudo
    assert "apr-solto" not in conteudo


def test_outro_projeto_recebe_o_global_e_o_casamento_lexical_nominal() -> None:
    """Sem conhecer a palavra: o texto da tarefa casa com o aprendizado do outro projeto."""
    conteudo = _vista(_montar_kernel(), "task-b")

    assert "[apr-global]" in conteudo
    assert "[apr-setor]" in conteudo
    assert "[apr-proj]" not in conteudo
    assert conteudo.index("[apr-global]") < conteudo.index("[apr-setor]")


def test_sem_palavra_em_comum_so_o_global_chega_edge_case() -> None:
    """Caso de borda: herança mais léxico não atravessam projetos sem palavra em comum."""
    conteudo = _vista(_montar_kernel(), "task-b2")

    assert "[apr-global]" in conteudo
    assert "[apr-setor]" not in conteudo
    assert "[apr-proj]" not in conteudo


class _IndiceFixo(IndiceSemantico):
    """Índice de teste que sempre sugere o mesmo aprendizado."""

    def sugerir(self, texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]:
        """Sugere o aprendizado do projeto A para qualquer texto."""
        return ("apr-proj",)

    def descrever(self) -> str:
        """Nome do índice de teste."""
        return "fixo"


def test_indice_semantico_injetado_traz_o_que_lexico_nao_alcanca_nominal() -> None:
    """O índice é o terceiro passo: só entra onde herança e léxico pararam."""
    kernel = _montar_kernel()

    conteudo = _vista(kernel, "task-b2", MaterializadorContexto(indice_semantico=_IndiceFixo()))

    assert "[apr-proj]" in conteudo
    assert MaterializadorContexto(indice_semantico=_IndiceFixo()).indice_semantico.descrever() == "fixo"


def test_aprendizado_de_agente_chega_marcado_como_nao_confiavel_nominal() -> None:
    """Memória escrita por agente tem a mesma defesa que Evidence e Artifact."""
    conteudo = _vista(_montar_kernel(), "task-a")

    assert MARCA_DE_CONTEUDO_NAO_CONFIAVEL in _linha_de(conteudo, "apr-agente")
    assert MARCA_DE_CONTEUDO_NAO_CONFIAVEL not in _linha_de(conteudo, "apr-proj")


def test_como_aplicar_origem_e_alcance_viajam_na_linha_do_que_casa_com_o_alvo_nominal() -> None:
    """A linha inteira diz o que fazer, de onde veio e onde vale: é a do aprendizado que casa com a tarefa."""
    linha = _linha_de(_vista(_montar_kernel(), "task-a"), "apr-setor")

    assert "-> como aplicar: Meca o teto antes" in linha
    assert "[vale_para setor-a]" in linha
    assert "[origem: dec-a]" in linha


def test_herdado_que_nao_casa_com_o_alvo_vai_so_com_a_afirmacao_nominal() -> None:
    """O que alcança o alvo sem casar com o texto dele chega curto: afirmação, proveniência e marcas."""
    conteudo = _vista(_montar_kernel(), "task-a")

    linha = _linha_de(conteudo, "apr-global")
    assert linha.startswith("- [apr-global] Descarte por secao, nunca linha a linha (log #")
    assert "como aplicar" not in linha
    assert "[origem:" not in linha
    assert "[vale_para" not in linha
    assert conteudo.index("[apr-setor]") < conteudo.index("[apr-global]")


def test_linha_curta_ainda_diz_quem_o_aprendizado_substitui_nominal() -> None:
    """Curta ou inteira, a linha do consolidado cita os absorvidos: é o que impede reabrir o que ele fechou."""
    linha = _linha_de(_vista(_montar_kernel(), "task-a"), "apr-proj")

    assert "como aplicar" not in linha
    assert "[substitui apr-velho]" in linha


def test_linhas_inteiras_por_heranca_tem_teto_edge_case() -> None:
    """Caso de borda: quando muitos casam com o alvo, só os primeiros vão inteiros; o resto fica curto, não some."""
    kernel = _montar_kernel()
    for numero in range(LIMITE_DE_LINHAS_INTEIRAS_POR_HERANCA + 2):
        _submeter(kernel, [*_aprendizado(f"apr-cache-{numero}", f"Cache com eviccao {numero}", como_aplicar="Meca"), _aresta(f"apr-cache-{numero}", "proj-a", TipoAresta.VALE_PARA)])

    linhas = [linha for linha in _vista(kernel, "task-a").splitlines() if linha.startswith("- [apr-")]

    assert sum(1 for linha in linhas if "-> como aplicar" in linha) == LIMITE_DE_LINHAS_INTEIRAS_POR_HERANCA
    assert sum(1 for linha in linhas if "[apr-cache-" in linha) == LIMITE_DE_LINHAS_INTEIRAS_POR_HERANCA + 2


def test_secao_retem_como_memoria_e_encolhe_por_grupo_nominal() -> None:
    """A memória cai no degrau da navegação, nunca antes, e encolhe por mecanismo."""
    view = _montar_kernel().obter_view()

    secao = montar_secao_de_aprendizados(PedidoDeMemoria(alvo=view.obter_no("task-a"), view=view))

    assert secao.prioridade_retencao == PrioridadeRetencao.MEMORIA
    assert secao.pode_encolher is True
    assert secao.reduzida(1).ids_incluidos != secao.ids_incluidos


def test_alvo_sem_aprendizado_algum_nao_ganha_secao_edge_case() -> None:
    """Caso de borda: um grafo sem memória promovida não gasta um cabeçalho vazio."""
    kernel = montar_kernel_em_memoria()
    _submeter(kernel, _hierarquia("c", "Tarefa sem memoria"))

    assert TITULO_APRENDIZADOS not in _vista(kernel, "task-c")


def test_secao_resumida_leva_toda_linha_a_forma_curta_e_avisa_no_titulo_nominal() -> None:
    """No degrau da memória resumida, até o que casa com o alvo vai só com a afirmação, e o título diz isso."""
    view = _montar_kernel().obter_view()
    secao = montar_secao_de_aprendizados(PedidoDeMemoria(alvo=view.obter_no("task-a"), view=view))

    resumida = secao.resumida()

    assert "-> como aplicar" in "\n".join(secao.linhas)
    assert "-> como aplicar" not in "\n".join(resumida.linhas)
    assert resumida.ids_incluidos == secao.ids_incluidos
    assert SUFIXO_DE_LINHAS_CURTAS in resumida.titulo


def test_entre_herdados_que_casam_igual_o_mais_recente_vem_primeiro_e_sobrevive_ao_corte_nominal() -> None:
    """A ordem é relevância e depois recência: ao encolher, o grupo mantém o que casa mais e o mais novo."""
    kernel = _montar_kernel()
    for numero in range(3):
        _submeter(
            kernel,
            [*_aprendizado(f"apr-cache-{numero}", f"Cache com eviccao {numero}"), _aresta(f"apr-cache-{numero}", "proj-a", TipoAresta.VALE_PARA)],
        )
    view = kernel.obter_view()
    alvo = view.obter_no("task-a")

    secao = montar_secao_de_aprendizados(PedidoDeMemoria(alvo=alvo, view=view))

    assert secao.ids_incluidos[:4] == ("apr-cache-2", "apr-cache-1", "apr-cache-0", "apr-setor")
    assert secao.reduzida(2).ids_incluidos == ("apr-cache-2", "apr-cache-1")
