"""D6: o teto de expansão, desligado por padrão, recusa a Task emergente de agente acima da conta."""

from typing import Any

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from tests.kernel.cenario_escopo import montar_kernel_com_goal, submeter
from tests.kernel.cenario_governanca import criar_aresta, criar_no
from tests.mcp.cenario_governanca import servidor

PLANEJADOR: PapelAutor = PapelAutor.PLANEJADOR
HUMANO: PapelAutor = PapelAutor.HUMANO
FALHA: str = ModoFalhaMAST.ORCAMENTO_DE_ESCOPO_ESGOTADO.value


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object]) -> ItemPatch:
    """A criação do nó com as propriedades dadas."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _emergente(id_task: str, sessao: str = "sess", *extras: ItemPatch) -> tuple[ItemPatch, ...]:
    """A Task B3: filha do Goal, motivada por `dec-1` e atendendo o critério `crit`."""
    return (
        _no(id_task, TipoNo.TASK, {"status": "pendente", "atende_criterio": ["crit"]}),
        criar_aresta(f"prod-{id_task}", sessao, id_task, TipoAresta.PRODUZ),
        criar_aresta(f"dec-goal-{id_task}", "goal", id_task, TipoAresta.DECOMPOE),
        criar_aresta(f"motivada_por-{id_task}", id_task, "dec-1", TipoAresta.MOTIVADA_POR),
        *extras,
    )


def _kernel_com_plano(teto: int | None = None) -> WriteKernel:
    """O Goal com o critério e o plano aprovado pelo humano; `teto` liga a leitura na política global."""
    kernel = montar_kernel_com_goal("personalizada", {"teto_expansao": teto} if teto is not None else None)
    criterio = (
        _no("crit", TipoNo.CONSTRAINT, {"tipo": "criterio_aceite"}),
        criar_aresta("prod-crit", "sess", "crit", TipoAresta.PRODUZ),
        criar_aresta("escopa-crit", "crit", "goal", TipoAresta.ESCOPA),
    )
    assert submeter(kernel, HUMANO, *criterio).sucesso
    _humano(kernel, "aprovar_plano")
    return kernel


def _humano(kernel: WriteKernel, ferramenta: str, **argumentos: Any) -> None:
    """O humano exerce o gesto pela ferramenta."""
    resposta = servidor(kernel, "humano").executar_ferramenta(ferramenta, {"id_goal": "goal", **argumentos})
    assert resposta["sucesso"] is True, resposta


def _criar(kernel: WriteKernel, id_task: str, papel: PapelAutor = PLANEJADOR, sessao: str = "sess") -> ResultadoSubmissao:
    """Submete a Task emergente sob o papel."""
    return submeter(kernel, papel, *_emergente(id_task, sessao))


def test_desligado_nao_recusa_nominal() -> None:
    """Sem `teto_expansao` (0), o agente cria quantas emergentes quiser, e nenhum teste antigo muda."""
    kernel = _kernel_com_plano()
    assert all(_criar(kernel, f"e{i}").sucesso for i in range(6))


def test_ligado_recusa_a_emergente_seguinte_ao_teto_nominal() -> None:
    """Com teto 2, as duas primeiras passam e a terceira é recusada, dizendo quem reabre."""
    kernel = _kernel_com_plano(teto=2)
    assert _criar(kernel, "e1").sucesso and _criar(kernel, "e2").sucesso
    recibo = _criar(kernel, "e3")
    assert not recibo.sucesso
    assert recibo.modo_de_falha == FALHA
    assert "responder_desvio" in recibo.mensagem and "humano" in recibo.mensagem
    assert "e3" not in kernel.obter_estado().nos


def test_humano_cria_acima_do_teto_e_nao_o_gasta_edge_case() -> None:
    """Caso de borda: a Task do humano passa do teto sem recusa e não entra na conta do agente."""
    kernel = _kernel_com_plano(teto=1)
    assert _criar(kernel, "h1", HUMANO).sucesso and _criar(kernel, "h2", HUMANO).sucesso
    assert _criar(kernel, "e1").sucesso
    assert _criar(kernel, "e2").modo_de_falha == FALHA
    assert _criar(kernel, "h3", HUMANO).sucesso


def test_responder_desvio_do_humano_reabre_edge_case() -> None:
    """Caso de borda: a resposta do humano zera a conta, e o agente volta a criar até o teto."""
    kernel = _kernel_com_plano(teto=1)
    assert _criar(kernel, "e1").sucesso
    assert _criar(kernel, "e2").modo_de_falha == FALHA
    _humano(kernel, "responder_desvio", resposta="seguir")
    assert _criar(kernel, "e2").sucesso
    assert _criar(kernel, "e3").modo_de_falha == FALHA


def test_nova_versao_do_plano_pelo_humano_reabre_edge_case() -> None:
    """Caso de borda: o `aprovar_plano` do humano também zera a conta."""
    kernel = _kernel_com_plano(teto=1)
    assert _criar(kernel, "e1").sucesso
    assert _criar(kernel, "e2").modo_de_falha == FALHA
    _humano(kernel, "aprovar_plano")
    assert _criar(kernel, "e2").sucesso


def test_lote_com_varias_emergentes_conta_na_ordem_edge_case() -> None:
    """Caso de borda: três emergentes no mesmo lote com teto 2 recusam o lote, e nenhuma nasce."""
    kernel = _kernel_com_plano(teto=2)
    lote = (*_emergente("e1"), *_emergente("e2"), *_emergente("e3"))
    assert submeter(kernel, PLANEJADOR, *lote).modo_de_falha == FALHA
    assert not {"e1", "e2", "e3"} & set(kernel.obter_estado().nos)


def test_subdivisao_do_plano_nao_entra_na_conta_edge_case() -> None:
    """Caso de borda: o teto é das emergentes; subdividir uma Task do plano segue livre."""
    kernel = _kernel_com_plano(teto=1)
    assert _criar(kernel, "e1").sucesso
    subdivisao = (
        criar_no("sub", TipoNo.TASK, status="pendente"),
        criar_aresta("prod-sub", "sess", "sub", TipoAresta.PRODUZ),
        criar_aresta("dec-t1-sub", "t1", "sub", TipoAresta.DECOMPOE),
    )
    assert submeter(kernel, PLANEJADOR, *subdivisao).sucesso


def _segundo_projeto_com_teto(kernel: WriteKernel, teto: int) -> None:
    """Um segundo Projeto com a sessão `sess-2` e a política própria com `teto_expansao`."""
    estrutura = (
        criar_no("proj-2", TipoNo.PROJETO),
        criar_no("setor-2", TipoNo.SETOR),
        criar_aresta("cont-proj-2-setor-2", "proj-2", "setor-2", TipoAresta.CONTEM),
        criar_no("sess-2", TipoNo.SESSAO),
        criar_aresta("cont-setor-2-sess-2", "setor-2", "sess-2", TipoAresta.CONTEM),
    )
    assert submeter(kernel, HUMANO, *estrutura).sucesso
    pedido = {"escopo": "proj-2", "preset": "personalizada", "personalizada": {"teto_expansao": teto}}
    resposta = servidor(kernel, "humano").executar_ferramenta("configurar_governanca", pedido)
    assert resposta["sucesso"] is True, resposta


def test_vale_o_mais_restritivo_entre_dois_projetos_edge_case() -> None:
    """Caso de borda: a Task contida por dois Projetos obedece o menor teto positivo."""
    kernel = _kernel_com_plano(teto=5)
    _segundo_projeto_com_teto(kernel, teto=1)
    assert _criar(kernel, "e1", sessao="sess-2").sucesso
    assert _criar(kernel, "e2", sessao="sess-2").modo_de_falha == FALHA
    assert _criar(kernel, "e3").sucesso


def test_projeto_com_teto_desligado_perde_para_o_global_edge_case() -> None:
    """Caso de borda: o 0 do Projeto não desliga o teto positivo da política global."""
    kernel = _kernel_com_plano(teto=1)
    _segundo_projeto_com_teto(kernel, teto=0)
    assert _criar(kernel, "e1", sessao="sess-2").sucesso
    assert _criar(kernel, "e2", sessao="sess-2").modo_de_falha == FALHA
