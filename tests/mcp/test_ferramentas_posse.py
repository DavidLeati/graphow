"""Testes da posse de tarefa exposta pelo MCP: assumir, colidir e devolver."""

from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer


def _montar_sessao_com_tarefa() -> WriteKernel:
    """Cria uma Sessao com uma Task pendente, tudo escrito pelo humano."""
    kernel = montar_kernel_em_memoria()
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/sess-1",
                        value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sprint"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/t1",
                        value={
                            "id": "t1",
                            "tipo": TipoNo.TASK.value,
                            "rotulo": "Implementar cache",
                            "propriedades": {"status": StatusTask.PENDENTE.value},
                        },
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/arestas/prod-t1",
                        value={
                            "id": "prod-t1",
                            "origem_id": "sess-1",
                            "destino_id": "t1",
                            "tipo": TipoAresta.PRODUZ.value,
                        },
                    ),
                ),
                justificativa="bootstrap",
            )
        )
    )
    return kernel


def _servidor(kernel: WriteKernel, autor: str, papel: str = "executor") -> GraphowMCPServer:
    """Abre um servidor MCP sobre o kernel com a identidade informada."""
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar(autor, papel))


def test_assumir_tarefa_adquire_lock_e_move_status_nominal() -> None:
    """A posse e o status andam juntos: assumir é um gesto só."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")

    recibo = executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert kernel.obter_dono_do_lock("t1") == "agente-a"
    tarefa = kernel.obter_view().obter_no("t1")
    assert tarefa.obter_propriedade("status") == StatusTask.EM_ANDAMENTO.value
    assert tarefa.obter_propriedade("assumida_por") == "agente-a"


def test_segundo_executor_nao_assume_tarefa_ocupada_edge_case() -> None:
    """Caso de borda: dois executores na mesma Task agora colidem no kernel."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "agente-a").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = _servidor(kernel, "agente-b").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert recibo["dono_atual"] == "agente-a"
    assert kernel.obter_dono_do_lock("t1") == "agente-a"


def test_concluir_tarefa_sem_posse_e_recusado_edge_case() -> None:
    """Caso de borda: concluir a tarefa de outro era aceito e passa a falhar."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "agente-a").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = _servidor(kernel, "agente-b").executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") != StatusTask.CONCLUIDO.value


def test_concluir_tarefa_sem_lock_algum_e_recusado_edge_case() -> None:
    """Caso de borda: ausência de posse não é permissão implícita."""
    kernel = _montar_sessao_com_tarefa()

    recibo = _servidor(kernel, "agente-a").executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert "assumir_tarefa" in str(recibo["mensagem"])


def test_dono_conclui_a_propria_tarefa_nominal() -> None:
    """Com a posse em mãos, o fluxo normal segue funcionando."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")
    executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = executor.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.CONCLUIDO.value


def test_liberar_tarefa_devolve_a_posse_nominal() -> None:
    """Liberar devolve o lock e deixa o status como estava."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")
    executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = executor.executar_ferramenta("liberar_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert kernel.obter_dono_do_lock("t1") is None
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.EM_ANDAMENTO.value


def test_liberar_tarefa_de_outro_autor_e_recusado_edge_case() -> None:
    """Caso de borda: ninguém devolve a posse que não detém."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "agente-a").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = _servidor(kernel, "agente-b").executar_ferramenta("liberar_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert kernel.obter_dono_do_lock("t1") == "agente-a"


def test_humano_altera_status_sem_precisar_de_posse_nominal() -> None:
    """O humano é dono do grafo, não um dos escritores paralelos que disputam posse."""
    kernel = _montar_sessao_com_tarefa()

    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.REPLACE,
                        path="/nos/t1/propriedades/status",
                        value=StatusTask.PENDENTE.value,
                    ),
                ),
                justificativa="reversao humana",
            )
        )
    )

    assert kernel.obter_dono_do_lock("t1") is None
    assert recibo.sucesso is True
