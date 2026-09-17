"""Testes da vista de uma sessão encerrada: ela abre pelo fechamento, não pela contagem."""

from graphow.context.fechamento import ACAO_DE_CONDENSACAO, TITULO_FECHAMENTO, esta_encerrada
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.panorama import TITULO_PANORAMA
from graphow.context.secoes import MARCA_DE_CONTEUDO_NAO_CONFIAVEL
from graphow.core.types import PapelAutor, StatusSessao, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel

ORCAMENTO: int = 1500


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
    dados = DadosPropostaPatch(autor="autor-teste", papel=papel, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem


def _montar_kernel(status_da_sessao: str = StatusSessao.CONCLUIDA.value) -> WriteKernel:
    """Projeto, setor e uma sessão com decisão, dúvida aberta, restrição e artefato."""
    kernel = montar_kernel_em_memoria()
    _submeter(
        kernel,
        [
            _no("proj", TipoNo.PROJETO, "Projeto"),
            _no("setor", TipoNo.SETOR, "Setor"),
            _aresta("proj", "setor", TipoAresta.CONTEM),
            _no("sess", TipoNo.SESSAO, "Fatia 2", status=status_da_sessao, resumo="tres tarefas fechadas"),
            _aresta("setor", "sess", TipoAresta.CONTEM),
            _no("dec-a", TipoNo.DECISION, "Transacao unica por lote"),
            _aresta("sess", "dec-a", TipoAresta.PRODUZ),
            _no("q-1", TipoNo.QUESTION, "TTL estrito?", status="aberta"),
            _aresta("sess", "q-1", TipoAresta.PRODUZ),
            _no("const-1", TipoNo.CONSTRAINT, "Zero dependencias"),
            _aresta("sess", "const-1", TipoAresta.PRODUZ),
            _no("art-1", TipoNo.ARTIFACT, "kernel.py"),
            _aresta("sess", "art-1", TipoAresta.PRODUZ),
            _no("t-1", TipoNo.TASK, "Tarefa feita", status="concluido"),
            _aresta("sess", "t-1", TipoAresta.PRODUZ),
        ],
    )
    return kernel


def _vista(kernel: WriteKernel, id_alvo: str) -> str:
    """Materializa a vista do planejador sobre o alvo, no orçamento padrão."""
    requisicao = RequisicaoVista(id_alvo=id_alvo, papel=PapelAutor.PLANEJADOR, orcamento_tokens=ORCAMENTO)
    return MaterializadorContexto().materializar(requisicao, kernel.obter_view()).conteudo_formatado


def test_sessao_encerrada_abre_pelo_fechamento_nominal() -> None:
    """A primeira seção da vista é o fechamento, antes de qualquer panorama."""
    conteudo = _vista(_montar_kernel(), "sess")

    assert conteudo.index(TITULO_FECHAMENTO) < conteudo.index(TITULO_PANORAMA)
    assert "- decisao vigente: [dec-a] Transacao unica por lote" in conteudo
    assert "- duvida aberta: [q-1] TTL estrito?" in conteudo
    assert "- restricao: [const-1] Zero dependencias" in conteudo
    assert "- ultimo artefato: [art-1] kernel.py" in conteudo
    assert "resumo declarado: tres tarefas fechadas" in conteudo


def test_sessao_ativa_nao_ganha_fechamento_edge_case() -> None:
    """Caso de borda: numa sessão viva o fechamento ainda está mudando."""
    conteudo = _vista(_montar_kernel(StatusSessao.ATIVA.value), "sess")

    assert TITULO_FECHAMENTO not in conteudo


def test_panorama_do_setor_carrega_o_fechamento_da_sessao_nominal() -> None:
    """A linha da sessão no panorama diz o que vigora, sem que ninguém a abra."""
    conteudo = _vista(_montar_kernel(), "setor")

    assert "vigora: dec-a" in conteudo
    assert "aberto: 1 duvidas" in conteudo
    assert "ultimo artefato: art-1" in conteudo


def test_condensacao_de_agente_abre_a_vista_marcada_como_nao_confiavel_nominal() -> None:
    """A prosa escrita por agente vira a leitura padrão, com a marca que a qualifica."""
    kernel = _montar_kernel()
    _submeter(
        kernel,
        [
            _no(
                "nota-cond",
                TipoNo.NOTE,
                "Condensacao da Fatia 2",
                acao=ACAO_DE_CONDENSACAO,
                id_alvo="sess",
                corpo="Vigora a transacao unica por lote.\nFicou aberto o TTL.",
            ),
            _aresta("sess", "nota-cond", TipoAresta.PRODUZ),
            _aresta("nota-cond", "dec-a", TipoAresta.DERIVA_DE),
        ],
        PapelAutor.REVISOR,
    )

    conteudo = _vista(kernel, "sess")

    assert "- condensacao [nota-cond]" in conteudo
    assert MARCA_DE_CONTEUDO_NAO_CONFIAVEL in conteudo
    assert "  Vigora a transacao unica por lote.\n  Ficou aberto o TTL." in conteudo


def test_esta_encerrada_so_reconhece_sessao_concluida_edge_case() -> None:
    """Caso de borda: uma Task concluída não é uma sessão encerrada."""
    view = _montar_kernel().obter_view()

    assert esta_encerrada(view.obter_no("sess")) is True
    assert esta_encerrada(view.obter_no("t-1")) is False
