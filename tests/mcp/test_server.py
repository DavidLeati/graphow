"""Testes unitários para o GraphowMCPServer e a identidade fixada por sessão."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from graphow.storage.in_memory_store import InMemoryEventStore


def _construir_servidor(papel: str = "humano", autor: str = "david") -> tuple[GraphowMCPServer, WriteKernel]:
    """Cria um servidor MCP vazio sob a identidade informada."""
    kernel = WriteKernel(InMemoryEventStore())
    identidade = IdentidadeSessaoMCP.criar(autor, papel)
    return GraphowMCPServer(kernel, identidade), kernel


def _configurar_servidor_com_dados(papel: str = "humano") -> tuple[GraphowMCPServer, WriteKernel]:
    """Inicializa kernel, dados básicos e servidor MCP sob a identidade informada."""
    servidor, kernel = _construir_servidor(papel)
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                "david",
                PapelAutor.HUMANO,
                [
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/sess-1",
                        value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sessao 1"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/t1",
                        value={"id": "t1", "tipo": TipoNo.TASK.value, "rotulo": "Desenvolver MCP"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/arestas/e1",
                        value={
                            "id": "e1",
                            "origem_id": "sess-1",
                            "destino_id": "t1",
                            "tipo": TipoAresta.PRODUZ.value,
                        },
                    ),
                ],
            )
        )
    )
    return servidor, kernel


def test_mcp_listar_ferramentas_nominal() -> None:
    """Testa listagem de schemas das ferramentas MCP."""
    servidor, _ = _configurar_servidor_com_dados()
    nomes = {ferramenta["name"] for ferramenta in servidor.listar_ferramentas()}
    esperadas = {
        "ler_vista",
        "expandir_no",
        "propor_patch",
        "abrir_questao",
        "buscar",
        "criar_projeto",
        "criar_setor",
        "criar_sessao",
        "criar_tarefa",
        "responder_questao",
        "concluir_tarefa",
        "configurar_autonomia_projeto",
        "excluir_em_lote",
        "excluir_projeto",
        "proximas_tarefas",
        "assumir_tarefa",
        "liberar_tarefa",
        "minhas_questoes",
        "aguardar_resposta",
    }
    assert esperadas.issubset(nomes)
    assert esperadas == nomes


def test_mcp_schemas_nao_expoem_campo_papel_nominal() -> None:
    """O papel deixou de ser argumento: nenhum schema pode voltar a anunciá-lo."""
    servidor, _ = _configurar_servidor_com_dados()
    for ferramenta in servidor.listar_ferramentas():
        propriedades = ferramenta["inputSchema"]["properties"]
        assert "papel" not in propriedades, ferramenta["name"]


def test_mcp_ler_vista_e_expandir_no_nominal() -> None:
    """Testa execução de ler_vista e expandir_no."""
    servidor, _ = _configurar_servidor_com_dados("executor")

    resultado_vista = servidor.executar_ferramenta("ler_vista", {"id_alvo": "t1", "orcamento_tokens": 1000})
    assert resultado_vista["sucesso"] is True
    assert "Desenvolver MCP" in resultado_vista["conteudo"]

    resultado_expansao = servidor.executar_ferramenta("expandir_no", {"id_no": "t1"})
    assert resultado_expansao["sucesso"] is True
    assert resultado_expansao["detalhes"]["id"] == "t1"
    assert len(resultado_expansao["detalhes"]["arestas_entrada"]) == 1


def test_mcp_recusa_papel_declarado_pelo_agente_edge_case() -> None:
    """Caso de borda: declarar 'papel' na chamada é recusado, nunca silenciosamente aceito."""
    servidor, _ = _configurar_servidor_com_dados("executor")
    resultado = servidor.executar_ferramenta("ler_vista", {"id_alvo": "t1", "papel": "humano"})
    assert resultado["sucesso"] is False
    assert "'papel' nao e aceito" in resultado["erro"]


def test_mcp_agente_nao_responde_questao_edge_case() -> None:
    """Caso de borda: sessão de agente não pode encerrar a escalação ao humano."""
    servidor, _ = _configurar_servidor_com_dados("executor")
    abertura = servidor.executar_ferramenta(
        "abrir_questao",
        {"pergunta": "Posso apagar a base?", "id_no_bloqueado": "t1", "id_sessao": "sess-1"},
    )
    assert abertura["sucesso"] is True

    resposta = servidor.executar_ferramenta(
        "responder_questao", {"id_questao": abertura["id_questao"], "resposta": "Pode sim"}
    )
    assert resposta["sucesso"] is False
    assert "exige uma sessao humana" in resposta["erro"]


def test_mcp_agente_nao_configura_autonomia_nem_exclui_edge_case() -> None:
    """Caso de borda: ferramentas que desligam governança exigem sessão humana."""
    servidor, _ = _configurar_servidor_com_dados("planejador")
    autonomia = servidor.executar_ferramenta(
        "configurar_autonomia_projeto", {"id_projeto": "proj-1", "nivel_autonomia": "ilimitado"}
    )
    exclusao = servidor.executar_ferramenta("excluir_projeto", {"id_projeto": "proj-1"})
    assert autonomia["sucesso"] is False
    assert exclusao["sucesso"] is False


def test_mcp_abrir_questao_bloqueante_edge_case() -> None:
    """Caso de borda: agente abre questão e bloqueia a Task, registrando a própria autoria."""
    servidor, kernel = _configurar_servidor_com_dados("executor")
    resultado = servidor.executar_ferramenta(
        "abrir_questao",
        {
            "pergunta": "Qual formato de autenticacao?",
            "id_no_bloqueado": "t1",
            "id_sessao": "sess-1",
        },
    )
    assert resultado["sucesso"] is True

    view = kernel.obter_view("main")
    questao = view.obter_no(resultado["id_questao"])
    assert view.esta_bloqueada("t1") is True
    assert questao is not None
    assert questao.tipo == TipoNo.QUESTION
    assert questao.obter_propriedade("papel_de_quem_abriu") == "executor"


def test_mcp_ferramenta_desconhecida_e_erro_tratado_edge_case() -> None:
    """Caso de borda: ferramenta inexistente ou alvo inválido retorna erro estruturado."""
    servidor, _ = _configurar_servidor_com_dados("executor")
    desconhecida = servidor.executar_ferramenta("ferramenta_fantasma", {})
    assert desconhecida["sucesso"] is False
    assert "Ferramenta desconhecida" in desconhecida["erro"]

    alvo_invalido = servidor.executar_ferramenta("ler_vista", {"id_alvo": "alvo_inexistente"})
    assert alvo_invalido["sucesso"] is False
    assert "ERRO" in alvo_invalido["erro"]


def test_mcp_argumento_obrigatorio_ausente_edge_case() -> None:
    """Caso de borda: argumento obrigatório ausente vira erro nomeado, não exceção crua."""
    servidor, _ = _configurar_servidor_com_dados("executor")
    resultado = servidor.executar_ferramenta("expandir_no", {})
    assert resultado["sucesso"] is False
    assert "Argumento obrigatorio ausente" in resultado["erro"]


def test_mcp_fluxo_completo_sob_sessao_humana() -> None:
    """Fluxo completo de gerenciamento executado por uma sessão humana."""
    servidor, kernel = _construir_servidor("humano")
    id_projeto = servidor.executar_ferramenta(
        "criar_projeto", {"rotulo": "Projeto IA", "nivel_autonomia": "ilimitado"}
    )["id_projeto"]
    id_setor = servidor.executar_ferramenta(
        "criar_setor", {"rotulo": "Engenharia", "id_projeto": id_projeto}
    )["id_setor"]
    id_sessao = servidor.executar_ferramenta("criar_sessao", {"rotulo": "Sprint 1", "id_setor": id_setor})["id_sessao"]
    id_task = servidor.executar_ferramenta(
        "criar_tarefa", {"titulo": "Implementar Pipeline", "id_sessao": id_sessao}
    )["id_task"]

    id_questao = servidor.executar_ferramenta(
        "abrir_questao", {"pergunta": "Qual formato?", "id_no_bloqueado": id_task, "id_sessao": id_sessao}
    )["id_questao"]
    assert kernel.obter_view("main").esta_bloqueada(id_task) is True
    assert servidor.executar_ferramenta("concluir_tarefa", {"id_task": id_task})["sucesso"] is False

    assert servidor.executar_ferramenta(
        "responder_questao", {"id_questao": id_questao, "resposta": "Usar JSON puro"}
    )["sucesso"] is True
    assert kernel.obter_view("main").esta_bloqueada(id_task) is False
    assert servidor.executar_ferramenta("concluir_tarefa", {"id_task": id_task})["sucesso"] is True
    assert kernel.obter_view("main").obter_no(id_task).obter_propriedade("status") == "concluido"


def test_mcp_excluir_em_lote_e_excluir_projeto_cascata() -> None:
    """Valida exclusão em lote e remoção em cascata sob sessão humana."""
    servidor, kernel = _construir_servidor("humano")
    id_projeto = servidor.executar_ferramenta(
        "criar_projeto", {"rotulo": "Projeto Para Deletar", "nivel_autonomia": "ilimitado"}
    )["id_projeto"]
    id_setor = servidor.executar_ferramenta(
        "criar_setor", {"rotulo": "Setor Temporario", "id_projeto": id_projeto}
    )["id_setor"]
    id_sessao = servidor.executar_ferramenta(
        "criar_sessao", {"rotulo": "Sessao Temporaria", "id_setor": id_setor}
    )["id_sessao"]
    id_primeira = servidor.executar_ferramenta("criar_tarefa", {"titulo": "Task 1", "id_sessao": id_sessao})["id_task"]
    id_segunda = servidor.executar_ferramenta("criar_tarefa", {"titulo": "Task 2", "id_sessao": id_sessao})["id_task"]

    assert servidor.executar_ferramenta("excluir_em_lote", {"ids_nos": [id_primeira, id_segunda]})["sucesso"] is True
    view = kernel.obter_view("main")
    assert view.contem_no(id_primeira) is False
    assert view.contem_no(id_projeto) is True

    remocao = servidor.executar_ferramenta("excluir_projeto", {"id_projeto": id_projeto, "cascata": True})
    assert remocao["sucesso"] is True
    assert remocao["total_removidos"] >= 3
    view = kernel.obter_view("main")
    assert view.contem_no(id_projeto) is False
    assert view.contem_no(id_setor) is False
    assert view.contem_no(id_sessao) is False
