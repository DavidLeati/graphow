"""Testes do controlador de propostas: a caixa lê as abertas e o humano as aceita ou descarta pelo kernel."""

from graphow.core.escopo import ACAO_PROPOSTA_FORA_DO_GOAL
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoDecisaoDeProposta, RequisicaoNovaAresta, RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController
from graphow.web.rest_propostas_controller import PropostasWebController


def _montar() -> tuple[WriteKernel, PropostasWebController]:
    """Dois Projetos com Sessão; o primeiro tem uma Task, e duas propostas (uma derivada da Task)."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    proposta = {"acao": ACAO_PROPOSTA_FORA_DO_GOAL}
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto A", id_no="proj-a"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor A", id_no="setor-a", contido_em="proj-a"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao A", id_no="sess-a", contido_em="setor-a"),
        RequisicaoNovoNo(tipo="Task", rotulo="Task A", id_no="task-a", sessao_id="sess-a"),
        RequisicaoNovoNo(tipo="Note", rotulo="Migrar o log antigo", id_no="prop-1", sessao_id="sess-a", propriedades=proposta),
        RequisicaoNovoNo(tipo="Note", rotulo="Cache de leitura", id_no="prop-2", sessao_id="sess-a", propriedades={**proposta, "status": "aberta"}),
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto B", id_no="proj-b"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor B", id_no="setor-b", contido_em="proj-b"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao B", id_no="sess-b", contido_em="setor-b"),
        RequisicaoNovoNo(tipo="Note", rotulo="Outra ideia", id_no="prop-b", sessao_id="sess-b", propriedades=proposta),
    )
    for req in requisicoes:
        assert canvas.criar_no(req).sucesso is True, req.id_no
    ligacao = RequisicaoNovaAresta(origem_id="prop-1", destino_id="task-a", tipo="deriva_de", id_aresta="d-1")
    assert canvas.criar_aresta(ligacao).sucesso is True
    return kernel, PropostasWebController(kernel)


def test_caixa_lista_as_abertas_de_todos_os_projetos_com_origem_nominal() -> None:
    """Sem filtro, a caixa traz as propostas dos dois Projetos, com o rótulo do Projeto e a origem citada."""
    _, propostas = _montar()

    resposta = propostas.listar()

    assert resposta.sucesso is True
    assert sorted(p.id for p in resposta.propostas) == ["prop-1", "prop-2", "prop-b"]
    primeira = next(p for p in resposta.propostas if p.id == "prop-1")
    assert (primeira.projeto_id, primeira.projeto_rotulo, primeira.sessao_id) == ("proj-a", "Projeto A", "sess-a")
    assert [(o.id, o.tipo) for o in primeira.origens] == [("task-a", "Task")]


def test_caixa_filtra_por_projeto_nominal() -> None:
    """O filtro por Projeto devolve só as propostas dele."""
    _, propostas = _montar()

    assert [p.id for p in propostas.listar(id_projeto="proj-b").propostas] == ["prop-b"]


def test_aceitar_muda_o_status_pelo_kernel_e_tira_da_caixa_nominal() -> None:
    """A decisão do humano é um patch de `status`; a proposta deixa a caixa e o nó guarda a decisão."""
    kernel, propostas = _montar()

    recibo = propostas.decidir(RequisicaoDecisaoDeProposta(id_proposta="prop-1", status="aceita"))

    assert recibo.sucesso is True, recibo.mensagem
    assert kernel.obter_view().obter_no("prop-1").obter_propriedade("status") == "aceita"
    assert "prop-1" not in [p.id for p in propostas.listar().propostas]


def test_descartar_uma_proposta_com_status_aberto_explicito_nominal() -> None:
    """A proposta que já nasceu com `status: aberta` também se descarta."""
    kernel, propostas = _montar()

    recibo = propostas.decidir(RequisicaoDecisaoDeProposta(id_proposta="prop-2", status="descartada"))

    assert recibo.sucesso is True, recibo.mensagem
    assert kernel.obter_view().obter_no("prop-2").obter_propriedade("status") == "descartada"


def test_status_fora_de_aceita_e_descartada_e_recusado_edge_case() -> None:
    """Caso de borda: o humano só fecha a proposta; reabri-la ou inventar status não passa."""
    kernel, propostas = _montar()

    for status in ("aberta", "feita", ""):
        recibo = propostas.decidir(RequisicaoDecisaoDeProposta(id_proposta="prop-1", status=status))
        assert recibo.sucesso is False
    assert kernel.obter_view().obter_no("prop-1").obter_propriedade("status") is None


def test_decidir_o_que_nao_e_proposta_ou_ja_foi_decidida_e_recusado_edge_case() -> None:
    """Caso de borda: Task, id inexistente e proposta já fechada não chegam a mudar o grafo."""
    _, propostas = _montar()
    propostas.decidir(RequisicaoDecisaoDeProposta(id_proposta="prop-1", status="aceita"))

    for alvo in ("task-a", "nao-existe", "prop-1"):
        recibo = propostas.decidir(RequisicaoDecisaoDeProposta(id_proposta=alvo, status="descartada"))
        assert recibo.sucesso is False, alvo
