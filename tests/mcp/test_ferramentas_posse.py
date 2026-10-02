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
                        path="/nos/proj-1",
                        value={"id": "proj-1", "tipo": TipoNo.PROJETO.value, "rotulo": "Projeto"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/setor-1",
                        value={"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "Engenharia"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/arestas/contem-setor-1",
                        value={
                            "id": "contem-setor-1",
                            "origem_id": "proj-1",
                            "destino_id": "setor-1",
                            "tipo": TipoAresta.CONTEM.value,
                        },
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/sess-1",
                        value={"id": "sess-1", "tipo": TipoNo.SESSAO.value, "rotulo": "Sprint"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/arestas/contem-sess-1",
                        value={
                            "id": "contem-sess-1",
                            "origem_id": "setor-1",
                            "destino_id": "sess-1",
                            "tipo": TipoAresta.CONTEM.value,
                        },
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


def _julgar(kernel: WriteKernel, id_evidencia: str, veredito: str) -> None:
    """O revisor grava o veredito sobre a Task, produzido pela sessão."""
    operacoes = [
        {"op": "add", "path": f"/nos/{id_evidencia}", "value": {
            "id": id_evidencia, "tipo": TipoNo.EVIDENCE.value, "rotulo": id_evidencia, "propriedades": {"veredito": veredito},
        }},
        {"op": "add", "path": f"/arestas/prod-{id_evidencia}", "value": {
            "id": f"prod-{id_evidencia}", "origem_id": "sess-1", "destino_id": id_evidencia, "tipo": TipoAresta.PRODUZ.value,
        }},
        {"op": "add", "path": f"/arestas/deriva-{id_evidencia}", "value": {
            "id": f"deriva-{id_evidencia}", "origem_id": id_evidencia, "destino_id": "t1", "tipo": TipoAresta.DERIVA_DE.value,
        }},
    ]
    revisor = _servidor(kernel, "revisor#r1", "revisor")
    recibo = revisor.executar_ferramenta("propor_patch", {"operacoes": operacoes, "justificativa": "veredito"})
    assert recibo["sucesso"], recibo


def test_assumir_tarefa_adquire_lock_e_move_status_nominal() -> None:
    """A posse e o status andam juntos: assumir é um gesto só."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")

    recibo = executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert recibo["autor"] == "agente-a"
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
    assert recibo["autor"] == "agente-b"
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
    _julgar(kernel, "evi-ok", "aprovado")

    recibo = executor.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.CONCLUIDO.value


def test_dono_sem_veredito_aprovado_nao_conclui_a_tarefa_edge_case() -> None:
    """Caso de borda: com a posse mas sem revisão aprovada, o kernel recusa o fechamento."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")
    executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    sem_revisao = executor.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})
    _julgar(kernel, "evi-no", "rejeitado")
    reprovada = executor.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert sem_revisao["sucesso"] is False and reprovada["sucesso"] is False
    assert sem_revisao["modo_de_falha"] == "fechamento_sem_veredito_aprovado"
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.EM_ANDAMENTO.value


def test_executor_nao_cria_a_propria_aprovacao_para_concluir_edge_case() -> None:
    """Caso de borda: a Evidence `veredito=aprovado` do executor é recusada, e a Task segue sem fechar."""
    kernel = _montar_sessao_com_tarefa()
    executor = _servidor(kernel, "agente-a")
    executor.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})
    operacoes = [
        {"op": "add", "path": "/nos/evi-eu", "value": {
            "id": "evi-eu", "tipo": TipoNo.EVIDENCE.value, "rotulo": "evi-eu", "propriedades": {"veredito": "aprovado"},
        }},
        {"op": "add", "path": "/arestas/prod-evi-eu", "value": {
            "id": "prod-evi-eu", "origem_id": "sess-1", "destino_id": "evi-eu", "tipo": TipoAresta.PRODUZ.value,
        }},
        {"op": "add", "path": "/arestas/deriva-evi-eu", "value": {
            "id": "deriva-evi-eu", "origem_id": "evi-eu", "destino_id": "t1", "tipo": TipoAresta.DERIVA_DE.value,
        }},
    ]

    criacao = executor.executar_ferramenta("propor_patch", {"operacoes": operacoes, "justificativa": "auto-aprovacao"})
    fechamento = executor.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})

    assert criacao["sucesso"] is False and criacao["modo_de_falha"] == "violacao_permissao_papel"
    assert fechamento["sucesso"] is False
    assert fechamento["modo_de_falha"] == "fechamento_sem_veredito_aprovado"


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


def test_humano_devolve_a_posse_de_um_subagente_que_terminou_nominal() -> None:
    """O subagente que morre sem liberar deixa a tarefa presa; o humano a solta."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "executor#a1b2c3").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = _servidor(kernel, "david", "humano").executar_ferramenta("liberar_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True
    assert "executor#a1b2c3" in recibo["mensagem"]
    assert kernel.obter_dono_do_lock("t1") is None
    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.EM_ANDAMENTO.value


def test_humano_liberando_tarefa_sem_posse_alguma_recusa_edge_case() -> None:
    """Caso de borda: não há o que devolver, e a recusa diz isso em vez de fingir sucesso."""
    kernel = _montar_sessao_com_tarefa()

    recibo = _servidor(kernel, "david", "humano").executar_ferramenta("liberar_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert recibo["dono_atual"] is None


def test_executor_retoma_posse_orfa_de_tarefa_aprovada_nominal() -> None:
    """O executor que vem fechar a tarefa aprovada tira a posse do autor que não voltou."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "executor#a1").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})
    _julgar(kernel, "evi-ok", "aprovado")
    fechador = _servidor(kernel, "executor#b2")

    recibo = fechador.executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is True, recibo
    assert recibo["posse_retomada_de"] == "executor#a1"
    assert kernel.obter_dono_do_lock("t1") == "executor#b2"
    tarefa = kernel.obter_view().obter_no("t1")
    assert tarefa.obter_propriedade("assumida_por") == "executor#b2"
    assert tarefa.obter_propriedade("posse_retomada_de") == "executor#a1"
    assert fechador.executar_ferramenta("concluir_tarefa", {"id_task": "t1"})["sucesso"] is True


def test_executor_nao_retoma_posse_sem_veredito_edge_case() -> None:
    """Caso de borda: sem revisão, a posse de outro segue sendo de outro."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "executor#a1").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    recibo = _servidor(kernel, "executor#b2").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert recibo["dono_atual"] == "executor#a1"
    assert kernel.obter_dono_do_lock("t1") == "executor#a1"


def test_executor_nao_retoma_posse_com_rejeicao_mais_recente_edge_case() -> None:
    """Caso de borda: a aprovação que uma rejeição posterior derrubou não libera a posse."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "executor#a1").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})
    _julgar(kernel, "evi-ok", "aprovado")
    _julgar(kernel, "evi-rej", "rejeitado")

    recibo = _servidor(kernel, "executor#b2").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recibo["sucesso"] is False
    assert kernel.obter_dono_do_lock("t1") == "executor#a1"
    assert kernel.obter_view().obter_no("t1").obter_propriedade("posse_retomada_de") is None


def test_so_o_executor_retoma_posse_de_tarefa_aprovada_edge_case() -> None:
    """Caso de borda: fechar é do executor; o revisor e o planejador não tiram a posse de ninguém."""
    kernel = _montar_sessao_com_tarefa()
    _servidor(kernel, "executor#a1").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})
    _julgar(kernel, "evi-ok", "aprovado")

    for autor, papel in (("revisor#r2", "revisor"), ("condutor#c1", "planejador")):
        recibo = _servidor(kernel, autor, papel).executar_ferramenta("assumir_tarefa", {"id_task": "t1"})
        assert recibo["sucesso"] is False

    assert kernel.obter_dono_do_lock("t1") == "executor#a1"
