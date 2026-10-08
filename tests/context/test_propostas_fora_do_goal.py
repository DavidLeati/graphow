"""A seção Propostas Fora Do Goal é do humano: Projeto e Goal a veem, o planejador não."""

from graphow.context.exploracao import ExploradorSubgrafo
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.politicas import AmbienteDoRecorte
from graphow.context.propostas_fora_do_goal import TITULO_DA_SECAO_DE_PROPOSTAS, montar_secao_de_propostas
from graphow.context.secoes import PrioridadeRetencao
from graphow.core.escopo import ACAO_PROPOSTA_FORA_DO_GOAL
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, str] | None = None) -> NoGrafo:
    """Nó com rótulo igual ao id."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=propriedades or {})


def _view(com_proposta_aberta: bool = True) -> GrafoView:
    """Projeto com Goal, Task e Sessão; uma proposta aberta derivada da Task e uma já descartada."""
    nos = [
        _no("proj", TipoNo.PROJETO), _no("goal", TipoNo.GOAL), _no("task", TipoNo.TASK), _no("sess", TipoNo.SESSAO),
        _no("prop-2", TipoNo.NOTE, {"acao": ACAO_PROPOSTA_FORA_DO_GOAL, "status": "descartada"}),
    ]
    ligacoes = [
        ("proj", "goal", TipoAresta.CONTEM), ("goal", "task", TipoAresta.DECOMPOE), ("proj", "sess", TipoAresta.CONTEM),
        ("sess", "prop-2", TipoAresta.PRODUZ),
    ]
    if com_proposta_aberta:
        nos.append(_no("prop-1", TipoNo.NOTE, {"acao": ACAO_PROPOSTA_FORA_DO_GOAL, "status": "aberta"}))
        ligacoes += [("sess", "prop-1", TipoAresta.PRODUZ), ("prop-1", "task", TipoAresta.DERIVA_DE)]
    arestas = {f"{o}->{d}": ArestaGrafo(id=f"{o}->{d}", origem_id=o, destino_id=d, tipo=t) for o, d, t in ligacoes}
    return GrafoView(GrafoEstado(nos={no.id: no for no in nos}, arestas=arestas))


def _vista(id_alvo: str, papel: PapelAutor, view: GrafoView | None = None) -> str:
    """O texto da vista do alvo para o papel."""
    requisicao = RequisicaoVista(id_alvo=id_alvo, papel=papel)
    return MaterializadorContexto().materializar(requisicao, view or _view()).conteudo_formatado


def test_humano_ve_a_proposta_aberta_no_projeto_e_no_goal_nominal() -> None:
    """A seção lista a aberta, com origem e sessão, e deixa a descartada de fora."""
    for alvo in ("proj", "goal"):
        texto = _vista(alvo, PapelAutor.HUMANO)
        assert f"## {TITULO_DA_SECAO_DE_PROPOSTAS}" in texto
        assert "prop-1" in texto and "origem: task" in texto and "sessao: sess" in texto
        assert "prop-2" not in texto


def test_planejador_e_os_outros_papeis_nao_veem_a_secao_nominal() -> None:
    """A proposta não chega ao planejador, nem ao executor, revisor ou árbitro."""
    for papel in (PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.ARBITRO):
        for alvo in ("proj", "goal"):
            texto = _vista(alvo, papel)
            assert TITULO_DA_SECAO_DE_PROPOSTAS not in texto
            assert "prop-1" not in texto


def test_task_do_humano_nao_ganha_a_secao_edge_case() -> None:
    """Caso de borda: a seção é do Projeto e do Goal; numa Task ela não existe."""
    assert TITULO_DA_SECAO_DE_PROPOSTAS not in _vista("task", PapelAutor.HUMANO)


def test_sem_proposta_aberta_a_secao_some_edge_case() -> None:
    """Caso de borda: sem proposta aberta a seção não é renderizada."""
    assert TITULO_DA_SECAO_DE_PROPOSTAS not in _vista("proj", PapelAutor.HUMANO, _view(com_proposta_aberta=False))


def test_a_secao_cai_cedo_sob_orcamento_nominal() -> None:
    """A proposta é a primeira a sair: tem a prioridade de corte mais baixa."""
    view = _view()
    ambiente = AmbienteDoRecorte(view=view, explorador=ExploradorSubgrafo(view))
    secao = montar_secao_de_propostas(view.obter_no("proj"), ambiente)
    assert secao.prioridade_retencao == PrioridadeRetencao.CONTEXTO == max(PrioridadeRetencao)
