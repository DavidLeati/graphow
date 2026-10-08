"""D2: a Task criada sob Goal com plano aprovado declara de onde veio, de qualquer autor."""

from collections.abc import Callable

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.lineage.replay_engine import ReplayEngine
from tests.kernel.cenario_escopo import (
    AUTORES,
    definir_lista,
    entrada_do_plano,
    montar_kernel_com_goal,
    submeter,
)
from tests.kernel.cenario_governanca import criar_aresta, criar_no, escrever

MAXIMA: str = "governanca_maxima"
PLANEJADOR: PapelAutor = PapelAutor.PLANEJADOR
HUMANO: PapelAutor = PapelAutor.HUMANO
FALHA: str = ModoFalhaMAST.LIGACAO_DE_ESCOPO_AUSENTE.value


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object] | None = None) -> ItemPatch:
    """A criação do nó com as propriedades dadas (o nome `tipo` é também uma propriedade de Constraint)."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _task(id_task: str, *extras: ItemPatch, pai: str | None = "goal", **propriedades: object) -> tuple[ItemPatch, ...]:
    """A Task pendente, produzida pela sessão, sob o pai por `decompoe`, com as operações a mais."""
    base = [criar_no(id_task, TipoNo.TASK, status="pendente", **propriedades), criar_aresta(f"prod-{id_task}", "sess", id_task, TipoAresta.PRODUZ)]
    if pai is not None:
        base.append(criar_aresta(f"dec-{pai}-{id_task}", pai, id_task, TipoAresta.DECOMPOE))
    return (*base, *extras)


def _ligar(origem: str, tipo: TipoAresta, destino: str) -> ItemPatch:
    """A aresta de ligação de escopo com id derivado das pontas."""
    return criar_aresta(f"{tipo.value}-{origem}-{destino}", origem, destino, tipo)


def _apoio() -> tuple[ItemPatch, ...]:
    """O que as ligações apontam: critério, Evidence rejeitada e aprovada, aceite, Decision revogada e Artifact da t1."""
    return (
        _no("crit", TipoNo.CONSTRAINT, {"tipo": "criterio_aceite"}),
        criar_aresta("prod-crit", "sess", "crit", TipoAresta.PRODUZ),
        criar_aresta("escopa-crit", "crit", "goal", TipoAresta.ESCOPA),
        criar_no("ev-rej", TipoNo.EVIDENCE, veredito="rejeitado"),
        criar_aresta("prod-ev-rej", "sess", "ev-rej", TipoAresta.PRODUZ),
        criar_no("ev-ok", TipoNo.EVIDENCE, veredito="aprovado"),
        criar_aresta("prod-ev-ok", "sess", "ev-ok", TipoAresta.PRODUZ),
        criar_no("dec-aceite", TipoNo.DECISION, acao="aceite_apos_reprovacao"),
        criar_aresta("prod-dec-aceite", "sess", "dec-aceite", TipoAresta.PRODUZ),
        criar_aresta("just-ev-rej", "ev-rej", "dec-aceite", TipoAresta.JUSTIFICA),
        criar_no("dec-velha", TipoNo.DECISION, status="revogada"),
        criar_aresta("prod-dec-velha", "sess", "dec-velha", TipoAresta.PRODUZ),
        criar_no("art", TipoNo.ARTIFACT),
        criar_aresta("prod-art", "sess", "art", TipoAresta.PRODUZ),
        criar_aresta("deriva-art-t1", "art", "t1", TipoAresta.DERIVA_DE),
    )


def _kernel_com_plano() -> WriteKernel:
    """O Goal com a `t1` no plano aprovado pelo humano e o apoio das ligações já no grafo."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert submeter(kernel, HUMANO, *_apoio()).sucesso
    recibo = submeter(kernel, HUMANO, definir_lista("planos", [entrada_do_plano(kernel, HUMANO)]))
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _criar(kernel: WriteKernel, papel: PapelAutor, *operacoes: ItemPatch) -> ResultadoSubmissao:
    """Submete a criação sob o papel."""
    return submeter(kernel, papel, *operacoes)


LIGACOES: dict[str, Callable[[], tuple[ItemPatch, ...]]] = {
    "subdivisao": lambda: _task("nova", pai="t1"),
    "correcao": lambda: _task("nova", corrige="ev-rej"),
    "acompanhamento": lambda: _task("nova", _ligar("nova", TipoAresta.ACOMPANHA, "ev-rej")),
    "integracao": lambda: _task("nova", _ligar("nova", TipoAresta.INTEGRA, "t1")),
    "reversao": lambda: _task("nova", _ligar("nova", TipoAresta.DESFAZ, "dec-velha")),
    "emergente": lambda: _task(
        "nova", _ligar("nova", TipoAresta.MOTIVADA_POR, "dec-1"), atende_criterio=["crit"]
    ),
}


@pytest.mark.parametrize("papel", [PLANEJADOR, HUMANO])
@pytest.mark.parametrize("classe", sorted(LIGACOES))
def test_cada_ligacao_aceita_passa_nominal(classe: str, papel: PapelAutor) -> None:
    """Cada classe de ligação, com o alvo do tipo certo, deixa a Task nascer, do planejador e do humano."""
    kernel = _kernel_com_plano()
    recibo = _criar(kernel, papel, *LIGACOES[classe]())
    assert recibo.sucesso, recibo.mensagem
    assert "nova" in kernel.obter_estado().nos


@pytest.mark.parametrize("papel", [PLANEJADOR, HUMANO])
def test_task_so_com_o_goal_como_pai_e_recusada_com_a_lista_nominal(papel: PapelAutor) -> None:
    """O pai Goal sozinho não basta: a recusa vem do modo certo, com as ligações aceitas e um exemplo."""
    kernel = _kernel_com_plano()
    recibo = _criar(kernel, papel, *_task("nova"))
    assert not recibo.sucesso
    assert recibo.modo_de_falha == FALHA
    assert "Ligações aceitas" in recibo.mensagem
    assert "motivada_por" in recibo.mensagem and "corrige" in recibo.mensagem and "integra" in recibo.mensagem
    assert "criar_tarefa(" in recibo.mensagem
    assert "nova" not in kernel.obter_estado().nos


def test_task_de_nome_correcao_sem_corrige_e_recusada_edge_case() -> None:
    """Caso de borda: a classe vem da estrutura, não do título: 'Correção' sem `corrige` não tem ligação."""
    kernel = _kernel_com_plano()
    operacoes = list(_task("nova"))
    operacoes[0] = criar_no("nova", TipoNo.TASK, status="pendente", descricao="Correção da entrega")
    assert _criar(kernel, PLANEJADOR, *operacoes).modo_de_falha == FALHA


def test_corrige_para_evidence_aprovada_e_recusado_edge_case() -> None:
    """Caso de borda: `corrige` aponta uma Evidence de veredito aprovado, e isso não é correção."""
    kernel = _kernel_com_plano()
    assert _criar(kernel, PLANEJADOR, *_task("nova", corrige="ev-ok")).modo_de_falha == FALHA


def test_motivada_por_sem_critico_do_goal_e_recusada_edge_case() -> None:
    """Caso de borda: `motivada_por` sem `atende_criterio` não basta, nem com critério que não é do Goal."""
    kernel = _kernel_com_plano()
    sem_criterio = _task("a", _ligar("a", TipoAresta.MOTIVADA_POR, "dec-1"))
    assert _criar(kernel, PLANEJADOR, *sem_criterio).modo_de_falha == FALHA
    criterio_alheio = _task("b", _ligar("b", TipoAresta.MOTIVADA_POR, "dec-1"), atende_criterio=["dec-1"])
    assert _criar(kernel, PLANEJADOR, *criterio_alheio).modo_de_falha == FALHA


def test_ligacao_criada_no_mesmo_lote_conta_edge_case() -> None:
    """Caso de borda: a Decision que motiva e a Task motivada por ela nascem juntas, e o lote passa."""
    kernel = _kernel_com_plano()
    motivo = (
        criar_no("dec-motivo", TipoNo.DECISION),
        criar_aresta("prod-dec-motivo", "sess", "dec-motivo", TipoAresta.PRODUZ),
    )
    emergente = _task("nova", _ligar("nova", TipoAresta.MOTIVADA_POR, "dec-motivo"), atende_criterio=["crit"])
    recibo = _criar(kernel, PLANEJADOR, *motivo, *emergente)
    assert recibo.sucesso, recibo.mensagem


def test_ligacao_removida_no_mesmo_lote_nao_conta_edge_case() -> None:
    """Caso de borda: criar a ligação e removê-la no mesmo lote deixa a Task sem ela, até para o humano."""
    kernel = _kernel_com_plano()
    ligacao = _ligar("nova", TipoAresta.INTEGRA, "t1")
    remocao = ItemPatch(op=OperacaoPatch.REMOVE, path="/arestas/integra-nova-t1")
    recibo = _criar(kernel, HUMANO, *_task("nova", ligacao, remocao))
    assert recibo.modo_de_falha == FALHA


def test_goal_sem_plano_aprovado_e_livre_edge_case() -> None:
    """Caso de borda: sem plano a ligação não é exigida, de ninguém."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _criar(kernel, PLANEJADOR, *_task("a")).sucesso
    assert _criar(kernel, HUMANO, *_task("b")).sucesso


def test_task_sem_goal_acima_e_livre_edge_case() -> None:
    """Caso de borda: a Task fora de qualquer Goal não tem plano a respeitar."""
    kernel = _kernel_com_plano()
    assert _criar(kernel, PLANEJADOR, *_task("solta-2", pai=None)).sucesso


def test_edicao_de_task_existente_nao_pede_ligacao_edge_case() -> None:
    """Caso de borda: a regra é da criação; mexer na Task que já existia não a reavalia."""
    kernel = _kernel_com_plano()
    assert _criar(kernel, PLANEJADOR, escrever(OperacaoPatch.REPLACE, "t1", "descricao", "mais claro")).sucesso


def _decision(id_decisao: str, alvo: str, *extras: ItemPatch) -> tuple[ItemPatch, ...]:
    """A Decision produzida pela sessão que orienta o alvo."""
    return (
        criar_no(id_decisao, TipoNo.DECISION),
        criar_aresta(f"prod-{id_decisao}", "sess", id_decisao, TipoAresta.PRODUZ),
        criar_aresta(f"orienta-{id_decisao}-{alvo}", id_decisao, alvo, TipoAresta.ORIENTA),
        *extras,
    )


@pytest.mark.parametrize("alvo", ["t1", "goal"])
def test_decision_do_planejador_sem_motivada_por_e_recusada_nominal(alvo: str) -> None:
    """A Decision que orienta Task do plano, ou o Goal, nasce com `motivada_por` ou é recusada."""
    kernel = _kernel_com_plano()
    recibo = _criar(kernel, PLANEJADOR, *_decision("dec-2", alvo))
    assert recibo.modo_de_falha == FALHA
    assert "motivada_por" in recibo.mensagem


def test_decision_do_planejador_com_motivada_por_passa_nominal() -> None:
    """Com a aresta `motivada_por` no mesmo lote, a Decision passa."""
    kernel = _kernel_com_plano()
    recibo = _criar(kernel, PLANEJADOR, *_decision("dec-2", "t1", _ligar("dec-2", TipoAresta.MOTIVADA_POR, "ev-rej")))
    assert recibo.sucesso, recibo.mensagem


def test_decision_do_humano_e_livre_edge_case() -> None:
    """Caso de borda: o humano decide sem motivar, e a Decision de Goal sem plano também é livre."""
    kernel = _kernel_com_plano()
    assert _criar(kernel, HUMANO, *_decision("dec-2", "t1")).sucesso
    sem_plano = montar_kernel_com_goal(MAXIMA)
    assert _criar(sem_plano, PLANEJADOR, *_decision("dec-3", "t1")).sucesso


def test_decision_que_nao_orienta_trabalho_do_goal_e_livre_edge_case() -> None:
    """Caso de borda: a Decision solta na sessão, que não orienta Task nem Goal, não leva `motivada_por`."""
    kernel = _kernel_com_plano()
    solta = (criar_no("dec-4", TipoNo.DECISION), criar_aresta("prod-dec-4", "sess", "dec-4", TipoAresta.PRODUZ))
    assert _criar(kernel, PLANEJADOR, *solta).sucesso


def _evento_antigo(seq: int, tipo: TipoEvento, payload: dict[str, object]) -> EventoLog:
    """O evento que um planejador gravou antes da 1.5.0, sem que nenhum portão olhasse a ligação."""
    dados = DadosCriacaoEvento(
        seq=seq, autor=AUTORES[PLANEJADOR], papel=PLANEJADOR, tipo_evento=tipo,
        payload=payload, origem=OrigemEvento.HARNESS, ramo_id="main",
    )
    return EventoLog.criar(dados)


def test_log_antigo_com_task_sem_ligacao_depois_de_goal_com_planos_reproduz_edge_case() -> None:
    """Caso de borda: os portões só rodam na submissão; o replay do log gravado à mão não os consulta."""
    kernel = _kernel_com_plano()
    base = kernel.obter_estado().versao_log
    kernel.repositorio.append_eventos([
        _evento_antigo(base + 1, TipoEvento.NO_CRIADO, {"id": "velha", "tipo": "Task", "rotulo": "velha", "propriedades": {"status": "pendente"}}),
        _evento_antigo(base + 2, TipoEvento.ARESTA_CRIADA, {"id": "dec-goal-velha", "origem_id": "goal", "destino_id": "velha", "tipo": "decompoe"}),
    ])
    estado = ReplayEngine(kernel.repositorio).reproduzir_ate_seq("main", base + 2)
    assert "velha" in estado.nos
    assert estado.nos["goal"].propriedades["planos"]
    assert "velha" in kernel.obter_estado().nos
