"""Cenário compartilhado dos testes do placar de escopo na web: um Goal com plano aprovado e desvio acima de K."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoEdicaoNo, RequisicaoNovaAresta, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController

EMERGENTES: int = 4


def _criar(canvas: CanvasWebController, requisicoes: tuple[RequisicaoNovoNo, ...]) -> None:
    """Cria cada nó pelo canvas, sob a identidade humana do servidor."""
    for req in requisicoes:
        recibo = canvas.criar_no(req)
        assert recibo.sucesso is True, f"{req.id_no}: {recibo.mensagem}"


def _ligar(canvas: CanvasWebController, ligacoes: tuple[tuple[str, str, str], ...]) -> None:
    """Cria cada aresta (origem, tipo, destino)."""
    for origem, tipo, destino in ligacoes:
        req = RequisicaoNovaAresta(origem_id=origem, destino_id=destino, tipo=tipo, id_aresta=f"{origem}-{tipo}-{destino}")
        recibo = canvas.criar_aresta(req)
        assert recibo.sucesso is True, recibo.mensagem


def montar_kernel(com_plano: bool = True, emergentes: int = EMERGENTES) -> WriteKernel:
    """Projeto > Sessão > Goal com uma Task do plano; aprovado o plano, `emergentes` Tasks B3 motivadas por `d1`."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    _criar(
        canvas,
        (
            RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto E", id_no="proj-e"),
            RequisicaoNovoNo(tipo="Setor", rotulo="Setor E", id_no="setor-e", contido_em="proj-e"),
            RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao E", id_no="sess-e", contido_em="setor-e"),
            RequisicaoNovoNo(tipo="Goal", rotulo="Goal E", id_no="goal-e", sessao_id="sess-e"),
            RequisicaoNovoNo(tipo="Constraint", rotulo="Cumpre o fluxo", id_no="crit-e", sessao_id="sess-e", propriedades={"tipo": "criterio_aceite"}),
            RequisicaoNovoNo(tipo="Decision", rotulo="Hub do contrato", id_no="d1", sessao_id="sess-e"),
            RequisicaoNovoNo(tipo="Task", rotulo="Task do plano", id_no="t-plano", sessao_id="sess-e", propriedades={"status": "pendente"}),
        ),
    )
    _ligar(canvas, (("crit-e", "escopa", "goal-e"), ("goal-e", "decompoe", "t-plano")))
    if com_plano:
        plano = {"versao": 1, "seq": kernel.obter_view().versao_log, "aprovado_por": "humano-ui", "papel": "humano"}
        recibo = canvas.editar_no(RequisicaoEdicaoNo(id_no="goal-e", novas_propriedades={"planos": [plano]}))
        assert recibo.sucesso is True, recibo.mensagem
    for i in range(emergentes):
        propriedades = {"status": "pendente", "atende_criterio": "crit-e"}
        _criar(canvas, (RequisicaoNovoNo(tipo="Task", rotulo=f"Emergente {i}", id_no=f"e{i}", sessao_id="sess-e", propriedades=propriedades),))
        _ligar(canvas, (("goal-e", "decompoe", f"e{i}"), (f"e{i}", "motivada_por", "d1")))
    return kernel
