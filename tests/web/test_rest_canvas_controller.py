"""Testes unitários para o CanvasWebController."""

from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import (
    RequisicaoEdicaoNo,
    RequisicaoExclusaoLote,
    RequisicaoExclusaoProjeto,
    RequisicaoNovaAresta,
    RequisicaoNovoNo,
)
from graphow.web.rest_canvas_controller import CanvasWebController


def _criar_controller_com_sessao() -> tuple[CanvasWebController, str]:
    """Utilitário para criar controller com uma Sessão inicial."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    ctrl = CanvasWebController(kernel)
    req_sessao = RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 1", id_no="sess-01")
    ctrl.criar_no(req_sessao)
    return ctrl, "sess-01"


def test_criar_e_obter_canvas_fluxo_nominal() -> None:
    """Valida fluxo nominal de criação de nós, arestas e consulta do canvas."""
    ctrl, sess_id = _criar_controller_com_sessao()

    # Cria Goal e Task vinculada à sessão
    rec_goal = ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Meta Principal", id_no="goal-1", sessao_id=sess_id))
    assert rec_goal.sucesso is True

    rec_task = ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Construir UI", id_no="task-1", sessao_id=sess_id))
    assert rec_task.sucesso is True

    # Conecta Goal -> Task via decompoe
    rec_aresta = ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="goal-1", destino_id="task-1", tipo="decompoe"))
    assert rec_aresta.sucesso is True

    canvas = ctrl.obter_canvas()
    assert canvas.total_nos == 3  # Sessao + Goal + Task
    assert canvas.total_arestas == 3  # 2 produz + 1 decompoe


def test_deteccao_task_bloqueada_por_question_edge_case() -> None:
    """Valida que tasks vinculadas a questões abertas são marcadas como bloqueadas no canvas."""
    ctrl, sess_id = _criar_controller_com_sessao()
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Tarefa Bloqueável", id_no="task-b", sessao_id=sess_id))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Question", rotulo="Dúvida Crítica", id_no="q-1", sessao_id=sess_id))

    # Cria aresta bloqueia: Question -> Task
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="q-1", destino_id="task-b", tipo="bloqueia"))

    canvas = ctrl.obter_canvas()
    no_task = next(n for n in canvas.nos if n.id == "task-b")
    assert no_task.esta_bloqueado is True


def test_filtro_por_sessao_inexistente_edge_case() -> None:
    """Valida que filtro de sessão inexistente retorna apenas contêineres ou lista vazia."""
    ctrl, _ = _criar_controller_com_sessao()
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Task Solta", id_no="t-solta"))

    canvas = ctrl.obter_canvas(sessao_id="sess-inexistente")
    # Nós de trabalho de outra sessão são filtrados
    assert all(n.id != "t-solta" for n in canvas.nos)


def test_edicao_e_remocao_de_elementos_edge_case() -> None:
    """Valida edição de propriedades e remoção com tratamento de erro."""
    ctrl, _ = _criar_controller_com_sessao()
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Task Original", id_no="t-edit"))

    rec_edit = ctrl.editar_no(RequisicaoEdicaoNo(id_no="t-edit", novo_rotulo="Task Renomeada", novas_propriedades={"status": "concluido"}))
    assert rec_edit.sucesso is True

    # Remoção inválida
    rec_invalido = ctrl.remover_elemento("tipo_invalido", "t-edit")
    assert rec_invalido.sucesso is False

    # Remoção válida
    rec_del = ctrl.remover_elemento("nos", "t-edit")
    assert rec_del.sucesso is True


def test_remocao_em_lote_nominal() -> None:
    """Valida exclusão em lote de múltiplos nós."""
    ctrl, sess_id = _criar_controller_com_sessao()
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="T1", id_no="t-1", sessao_id=sess_id))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="T2", id_no="t-2", sessao_id=sess_id))
    assert ctrl.obter_canvas().total_nos == 3

    rec_lote = ctrl.remover_lote(RequisicaoExclusaoLote(ids_nos=("t-1", "t-2")))
    assert rec_lote.sucesso is True
    assert ctrl.obter_canvas().total_nos == 1


def test_remocao_projeto_em_cascata_nominal() -> None:
    """Valida exclusão em cascata de um projeto e todos os seus descendentes."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    ctrl = CanvasWebController(kernel)

    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Meu Projeto", id_no="proj-1"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Setor 1", id_no="set-1"))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="proj-1", destino_id="set-1", tipo="contem"))

    ctrl.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao 1", id_no="sess-1"))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="set-1", destino_id="sess-1", tipo="contem"))

    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Task 1", id_no="t-1", sessao_id="sess-1"))
    assert ctrl.obter_canvas().total_nos == 4

    rec = ctrl.remover_projeto_completo(RequisicaoExclusaoProjeto(id_projeto="proj-1"))
    assert rec.sucesso is True
    assert ctrl.obter_canvas().total_nos == 0


def test_filtro_canvas_por_projeto_nominal() -> None:
    """Valida que o canvas isola os nós pertencentes a cada projeto específico."""
    store = InMemoryEventStore()
    kernel = WriteKernel(store)
    ctrl = CanvasWebController(kernel)

    # Projeto A
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Proj A", id_no="pa"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Set A", id_no="sa"))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="pa", destino_id="sa", tipo="contem"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Sessao", rotulo="Sess A", id_no="sessa"))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="sa", destino_id="sessa", tipo="contem"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Task", rotulo="Task A", id_no="ta", sessao_id="sessa"))

    # Projeto B
    ctrl.criar_no(RequisicaoNovoNo(tipo="Projeto", rotulo="Proj B", id_no="pb"))
    ctrl.criar_no(RequisicaoNovoNo(tipo="Setor", rotulo="Set B", id_no="sb"))
    ctrl.criar_aresta(RequisicaoNovaAresta(origem_id="pb", destino_id="sb", tipo="contem"))

    # Total geral
    assert ctrl.obter_canvas().total_nos == 6

    # Filtrado por Projeto A
    canvas_a = ctrl.obter_canvas(projeto_id="pa")
    ids_a = {n.id for n in canvas_a.nos}
    assert ids_a == {"pa", "sa", "sessa", "ta"}

    # Filtrado por Projeto B
    canvas_b = ctrl.obter_canvas(projeto_id="pb")
    ids_b = {n.id for n in canvas_b.nos}
    assert ids_b == {"pb", "sb"}



def test_canvas_publica_idade_e_ordem_de_cada_no_nominal() -> None:
    """O card só consegue dizer a própria idade se a API mandar a data e a sequência."""
    ctrl, sess_id = _criar_controller_com_sessao()
    ctrl.criar_no(RequisicaoNovoNo(tipo="Goal", rotulo="Meta", id_no="goal-1", sessao_id=sess_id))

    nos = {no.id: no for no in ctrl.obter_canvas().nos}

    assert nos["sess-01"].criado_em != ""
    assert nos["sess-01"].seq_criacao > 0
    assert nos["goal-1"].seq_criacao > nos["sess-01"].seq_criacao


def test_edicao_move_a_marca_de_alteracao_sem_mover_a_de_criacao_nominal() -> None:
    """Editar um nó não o rejuvenesce nem o envelhece: só marca o último toque."""
    ctrl, _ = _criar_controller_com_sessao()

    antes = {no.id: no for no in ctrl.obter_canvas().nos}["sess-01"]
    ctrl.editar_no(RequisicaoEdicaoNo(id_no="sess-01", novas_propriedades={}, novo_rotulo="Sessao renomeada"))
    depois = {no.id: no for no in ctrl.obter_canvas().nos}["sess-01"]

    assert depois.seq_criacao == antes.seq_criacao
    assert depois.criado_em == antes.criado_em
    assert depois.seq_atualizacao > antes.seq_atualizacao
    assert depois.atualizado_em is not None
