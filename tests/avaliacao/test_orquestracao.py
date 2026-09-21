"""A medição da orquestração: retrabalho, vereditos e tokens de cada Goal, lado a lado por configuração."""

from graphow.avaliacao.orquestracao import MedicaoDeGoal, MedidorDeOrquestracao
from graphow.avaliacao.relatorio_orquestracao import SEM_GOALS, formatar_relatorio
from graphow.core.events import TipoEvento
from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


def _no(id_no: str, tipo: TipoNo, **propriedades: object) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _tarefa(id_task: str, pai: str, **propriedades: object) -> tuple[ItemPatch, ...]:
    """Task produzida pela sessão do orquestrador e decomposta do pai."""
    return (
        _no(id_task, TipoNo.TASK, **propriedades),
        _aresta("sess-orq", id_task, TipoAresta.PRODUZ),
        _aresta(pai, id_task, TipoAresta.DECOMPOE),
    )


def _derivado(id_no: str, tipo: TipoNo, alvos: tuple[str, ...], **propriedades: object) -> tuple[ItemPatch, ...]:
    """Artifact ou Evidence da sessão do orquestrador, derivado dos alvos."""
    arestas = tuple(_aresta(id_no, alvo, TipoAresta.DERIVA_DE) for alvo in alvos)
    return (_no(id_no, tipo, **propriedades), _aresta("sess-orq", id_no, TipoAresta.PRODUZ), *arestas)


def _run(kernel: WriteKernel, id_run: str, **dados: object) -> None:
    """Um Run como o harness grava, pendurado na sessão do orquestrador."""
    pedido = PedidoDeExecucao(id_run=id_run, id_sessao="sess-orq", tipo_evento=TipoEvento.EXECUCAO_CONCLUIDA, dados=dados)
    assert kernel.registrar_execucao(pedido).sucesso


def _montar() -> WriteKernel:
    """Dois Goals sob configurações diferentes, orquestrados pela mesma sessão."""
    kernel = montar_kernel_em_memoria()
    operacoes = (
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-h", TipoNo.SESSAO), _aresta("setor", "sess-h", TipoAresta.CONTEM),
        _no("sess-orq", TipoNo.SESSAO), _aresta("setor", "sess-orq", TipoAresta.CONTEM),
        _no("goal-a", TipoNo.GOAL, configuracao="padrao"), _aresta("sess-h", "goal-a", TipoAresta.PRODUZ),
        _no("goal-b", TipoNo.GOAL, configuracao="tudo-opus"), _aresta("sess-h", "goal-b", TipoAresta.PRODUZ),
        *_tarefa("t1", "goal-a", modelo="sonnet", status=StatusTask.CONCLUIDO.value),
        *_tarefa("t2", "goal-a", modelo="opus", status=StatusTask.CONCLUIDO.value),
        *_tarefa("t3", "goal-b", modelo="opus", status=StatusTask.PENDENTE.value),
        *_derivado("art1", TipoNo.ARTIFACT, ("t1",)),
        *_derivado("art2", TipoNo.ARTIFACT, ("t2",)),
        *_derivado("evi-rej", TipoNo.EVIDENCE, ("art1", "t1"), veredito="rejeitado"),
        *_derivado("evi-ok", TipoNo.EVIDENCE, ("art2",), veredito="aprovado"),
        *_tarefa("t1c", "t1", corrige="evi-rej", status=StatusTask.CONCLUIDO.value),
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    recibo = kernel.submeter_patch(PropostaPatch.criar(dados))
    assert recibo.sucesso, recibo.mensagem
    _run(kernel, "run-sess-orq", tokens_entrada=400, tokens_saida=200)
    _run(kernel, "run-exec-1", agente="graphow-executor", tarefas=["t1", "t1c"], tokens_entrada=700, tokens_saida=300)
    _run(kernel, "run-exec-2", agente="graphow-executor-opus", tarefas=["t2"], tokens_entrada=1500, tokens_saida=500)
    _run(kernel, "run-explorador", agente="graphow-explorador", tokens_entrada=80, tokens_saida=20)
    _run(kernel, "run-perdido", agente="graphow-revisor", tarefas=["t2"])
    return kernel


def _por_goal(kernel: WriteKernel) -> dict[str, MedicaoDeGoal]:
    """As medições de todos os Goals com tarefas, por id."""
    return {medicao.id_goal: medicao for medicao in MedidorDeOrquestracao(kernel.obter_view()).medir()}


def test_goal_conta_retrabalho_e_vereditos_da_revisao_nominal() -> None:
    """A correção não conta como tarefa; a tarefa corrigida conta como retrabalho."""
    medicao = _por_goal(_montar())["goal-a"]

    assert medicao.configuracao == "padrao"
    assert (medicao.tarefas, medicao.concluidas, medicao.concluidas_sem_retrabalho) == (2, 2, 1)
    assert (medicao.com_retrabalho, medicao.correcoes) == (1, 1)
    assert (medicao.rejeicoes, medicao.aprovacoes) == (1, 1)
    assert medicao.modelos_por_tarefa == {"sonnet": 1, "opus": 1}


def test_tokens_do_subagente_seguem_a_tarefa_e_os_da_sessao_se_dividem_nominal() -> None:
    """Subagente pelas tarefas que assumiu; orquestrador e explorador pela sessão, dividida entre os dois Goals."""
    medicoes = _por_goal(_montar())

    assert medicoes["goal-a"].tokens_por_agente == {
        "graphow-executor": 1000,
        "graphow-executor-opus": 2000,
        "graphow-explorador": 50,
        "graphow-revisor": 0,
        "orquestrador": 300,
    }
    assert medicoes["goal-b"].tokens_por_agente == {"graphow-explorador": 50, "orquestrador": 300}


def test_run_sem_tokens_e_contado_a_parte_edge_case() -> None:
    """Caso de borda: o Run sem transcrição legível não vira zero silencioso; o relatório o aponta."""
    medicao = _por_goal(_montar())["goal-a"]

    assert medicao.runs_sem_tokens == 1
    assert any("1 Run sem tokens" in linha for linha in formatar_relatorio((medicao,)))


def test_relatorio_compara_as_configuracoes_nominal() -> None:
    """Uma linha por configuração, com a taxa sem retrabalho e o custo por tarefa concluída."""
    linhas = formatar_relatorio(tuple(_por_goal(_montar()).values()))

    padrao = next(linha for linha in linhas if linha.strip().startswith("padrao:"))
    assert "2 concluidas, 1 sem retrabalho (50%)" in padrao
    assert "1 rejeicoes" in padrao
    assert "3.350 tokens" in padrao
    assert "1.675 por tarefa concluida" in padrao
    assert any(linha.strip().startswith("tudo-opus:") and "sem conclusao" in linha for linha in linhas)


def test_goal_sem_configuracao_e_sem_tarefas_edge_case() -> None:
    """Caso de borda: Goal sem tarefas fica de fora; pedido sem nada a medir diz isso."""
    kernel = montar_kernel_em_memoria()

    assert MedidorDeOrquestracao(kernel.obter_view()).medir() == ()
    assert formatar_relatorio(()) == (SEM_GOALS,)
