"""Simulação de integração ponta a ponta de ciclo completo do Graphow."""

from typing import Any

from graphow.core.types import PapelAutor, StatusQuestion, StatusTask
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.lineage.lineage_tracer import LineageTracer
from graphow.lineage.replay_engine import ReplayEngine
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from graphow.storage.in_memory_store import InMemoryEventStore


def _submeter_como_humano(kernel: WriteKernel, operacoes: list[dict[str, Any]], justificativa: str) -> bool:
    """Submete um lote de operações sob a identidade humana e devolve o sucesso."""
    itens = tuple(
        ItemPatch(op=OperacaoPatch(bruta["op"]), path=bruta["path"], value=bruta.get("value"))
        for bruta in operacoes
    )
    dados = DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=itens, justificativa=justificativa
    )
    return kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def _montar_navegacao_e_goal(kernel: WriteKernel) -> bool:
    """Cria a hierarquia de navegação, o Goal e a Constraint que o escopa."""
    operacoes: list[dict[str, Any]] = [
        {"op": "add", "path": "/nos/p1", "value": {"id": "p1", "tipo": "Projeto", "rotulo": "Graphow Core"}},
        {"op": "add", "path": "/nos/s1", "value": {"id": "s1", "tipo": "Setor", "rotulo": "Engenharia"}},
        {"op": "add", "path": "/arestas/e-contem-s1", "value": {"id": "e-contem-s1", "origem_id": "p1", "destino_id": "s1", "tipo": "contem"}},
        {"op": "add", "path": "/nos/sess-01", "value": {"id": "sess-01", "tipo": "Sessao", "rotulo": "Sessao Alpha"}},
        {"op": "add", "path": "/arestas/e-contem-sess", "value": {"id": "e-contem-sess", "origem_id": "s1", "destino_id": "sess-01", "tipo": "contem"}},
        {"op": "add", "path": "/nos/goal-1", "value": {"id": "goal-1", "tipo": "Goal", "rotulo": "Substrato Bilateral"}},
        {"op": "add", "path": "/arestas/e-prod-g1", "value": {"id": "e-prod-g1", "origem_id": "sess-01", "destino_id": "goal-1", "tipo": "produz"}},
        {"op": "add", "path": "/nos/c1", "value": {"id": "c1", "tipo": "Constraint", "rotulo": "Imutabilidade Obrigatoria"}},
        {"op": "add", "path": "/arestas/e-escopa", "value": {"id": "e-escopa", "origem_id": "c1", "destino_id": "goal-1", "tipo": "escopa"}},
    ]
    return _submeter_como_humano(kernel, operacoes, "Bootstrap da navegacao e do objetivo")


def _decompor_goal_em_task(servidor_planejador: GraphowMCPServer) -> dict[str, Any]:
    """O planejador decompõe o Goal em uma Task técnica; `decompoe` é dele."""
    return servidor_planejador.executar_ferramenta(
        "propor_patch",
        {
            "justificativa": "Decomposicao em tarefa tecnica",
            "operacoes": [
                {"op": "add", "path": "/nos/t1", "value": {"id": "t1", "tipo": "Task", "rotulo": "Criar Modelos Frozen", "propriedades": {"status": "pendente"}}},
                {"op": "add", "path": "/arestas/e-dec-g1", "value": {"id": "e-dec-g1", "origem_id": "goal-1", "destino_id": "t1", "tipo": "decompoe"}},
            ],
        },
    )


def _tentar_escopar_constraint(servidor_planejador: GraphowMCPServer) -> dict[str, Any]:
    """O planejador tenta escopar a Constraint sobre a Task: `escopa` é do humano."""
    return servidor_planejador.executar_ferramenta(
        "propor_patch",
        {
            "justificativa": "Herdando a restricao para a tarefa",
            "operacoes": [
                {"op": "add", "path": "/arestas/e-esc-t1", "value": {"id": "e-esc-t1", "origem_id": "c1", "destino_id": "t1", "tipo": "escopa"}},
            ],
        },
    )


def _escopar_constraint_como_humano(kernel: WriteKernel) -> bool:
    """O humano estende o escopo da Constraint até a Task decomposta."""
    operacoes: list[dict[str, Any]] = [
        {"op": "add", "path": "/arestas/e-esc-t1", "value": {"id": "e-esc-t1", "origem_id": "c1", "destino_id": "t1", "tipo": "escopa"}},
    ]
    return _submeter_como_humano(kernel, operacoes, "Escopo da restricao sobre a tarefa")


def _produzir_artefato(servidor_executor: GraphowMCPServer) -> dict[str, Any]:
    """O executor registra o artefato produzido e move a Task para revisão."""
    return servidor_executor.executar_ferramenta(
        "propor_patch",
        {
            "justificativa": "Artefato pronto para revisao",
            "operacoes": [
                {"op": "add", "path": "/nos/art-1", "value": {"id": "art-1", "tipo": "Artifact", "rotulo": "models.py", "propriedades": {"linhas": 45}}},
                {"op": "add", "path": "/arestas/e-art-deriva", "value": {"id": "e-art-deriva", "origem_id": "art-1", "destino_id": "t1", "tipo": "deriva_de"}},
                {"op": "replace", "path": "/nos/t1/propriedades/status", "value": StatusTask.PRONTO_PARA_REVISAO.value},
            ],
        },
    )


def test_simulacao_completa_ponta_a_ponta() -> None:
    """Exercita o ecossistema completo: Kernel, MCP por papel, Linhagem e Replay."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    planejador = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("agente-planejador", "planejador"))
    executor = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("agente-executor", "executor"))

    assert _montar_navegacao_e_goal(kernel) is True

    vista = planejador.executar_ferramenta("ler_vista", {"id_alvo": "goal-1", "orcamento_tokens": 1000})
    assert vista["sucesso"] is True
    assert "Imutabilidade Obrigatoria" in vista["conteudo"]

    assert _decompor_goal_em_task(planejador)["sucesso"] is True
    assert _tentar_escopar_constraint(planejador)["sucesso"] is False
    assert _escopar_constraint_como_humano(kernel) is True
    assert kernel.adquirir_lock_task("t1", "agente-executor") is True

    id_questao = _executar_ciclo_de_bloqueio(executor, kernel)
    assert _produzir_artefato(executor)["sucesso"] is True
    assert kernel.obter_view().obter_no(id_questao) is not None

    _verificar_linhagem_e_replay(kernel, store)


def _executar_ciclo_de_bloqueio(executor: GraphowMCPServer, kernel: WriteKernel) -> str:
    """O executor abre dúvida, é barrado, e só o humano consegue destravar."""
    abertura = executor.executar_ferramenta(
        "abrir_questao",
        {"pergunta": "Usar dataclass(frozen=True) ou NamedTuple?", "id_no_bloqueado": "t1", "id_sessao": "sess-01"},
    )
    assert abertura["sucesso"] is True
    id_questao = str(abertura["id_questao"])

    tentativa = executor.executar_ferramenta(
        "propor_patch",
        {
            "justificativa": "Tentando fechar",
            "operacoes": [{"op": "replace", "path": "/nos/t1/propriedades/status", "value": "concluido"}],
        },
    )
    assert tentativa["sucesso"] is False

    autorresposta = executor.executar_ferramenta(
        "responder_questao", {"id_questao": id_questao, "resposta": "Eu mesmo decido"}
    )
    assert autorresposta["sucesso"] is False

    _responder_como_humano(kernel, id_questao)
    assert kernel.obter_view().esta_bloqueada("t1") is False
    return id_questao


def _responder_como_humano(kernel: WriteKernel, id_questao: str) -> None:
    """O humano responde à dúvida e registra a decisão correspondente."""
    operacoes: list[dict[str, Any]] = [
        {"op": "replace", "path": f"/nos/{id_questao}/propriedades/status", "value": StatusQuestion.RESPONDIDA.value},
        {"op": "add", "path": "/nos/d1", "value": {"id": "d1", "tipo": "Decision", "rotulo": "Decisao: usar dataclass frozen"}},
        {"op": "add", "path": "/arestas/e-prod-d1", "value": {"id": "e-prod-d1", "origem_id": "sess-01", "destino_id": "d1", "tipo": "produz"}},
    ]
    assert _submeter_como_humano(kernel, operacoes, "Resposta humana a duvida bloqueante") is True


def _verificar_linhagem_e_replay(kernel: WriteKernel, store: InMemoryEventStore) -> None:
    """Confere a linhagem reversa até o Goal e a paridade entre replay e projeção."""
    caminho = LineageTracer().rastrear_linhagem("art-1", kernel.obter_view())
    assert caminho.goal_raiz is not None
    assert caminho.goal_raiz.id == "goal-1"
    assert len(caminho.nos_cadeia) >= 3

    eventos = store.ler_eventos("main")
    assert len(eventos) >= 15
    estado_reconstruido = ReplayEngine(store).reproduzir_ate_seq("main", len(eventos))
    assert estado_reconstruido.serializar_para_json() == kernel.obter_estado("main").serializar_para_json()
