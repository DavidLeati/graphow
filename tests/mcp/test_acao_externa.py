"""A Task de ação externa (enviar e-mail, marcar reunião) é do humano, salvo quando a política a entrega ao executor.

O ciclo é o de sempre, com a entrega trocada: quem executa registra a prova numa
Evidence com `fonte` e `resultado`, o revisor julga e o executor fecha. O que
muda é quem pode assumir e entregar, e isso sai do gesto `acao_externa`.
"""

from typing import Any

import pytest

from graphow.core.governanca import Gesto, PresetGovernanca, VALOR_EXECUTOR, VALOR_HUMANO, compor_mais_restritiva, politica_do_preset
from graphow.core.types import PapelAutor, StatusTask
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer
from tests.mcp.cenario_governanca import montar_kernel as montar_kernel_de_dois_projetos

SESSAO: str = "sess-a"


def _servidor(kernel: WriteKernel, autor: str, papel: str) -> GraphowMCPServer:
    """Um servidor MCP com a identidade fixada."""
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar(autor, papel))


def _chamar(agente: GraphowMCPServer, ferramenta: str, **argumentos: object) -> dict[str, Any]:
    """Chama a ferramenta e devolve o recibo, aceito ou não."""
    return agente.executar_ferramenta(ferramenta, argumentos)


def _montar(acao_externa: str | None = None) -> WriteKernel:
    """O cenário de dois projetos, com a Task de envio criada pelo planejador no projeto 'a'."""
    kernel = montar_kernel_de_dois_projetos()
    if acao_externa is not None:
        recibo = _chamar(
            _servidor(kernel, "david", "humano"), "configurar_governanca",
            escopo="proj-a", preset="personalizada", personalizada={"acao_externa": acao_externa},
        )
        assert recibo["sucesso"], recibo
    recibo = _chamar(
        _servidor(kernel, "orquestrador", "planejador"), "criar_tarefa",
        titulo="Enviar o relatorio a diretoria", id_task="t-envio", id_sessao=SESSAO, entrega="acao_externa",
        criterio_pronto="e-mail enviado com o relatorio anexo",
    )
    assert recibo["sucesso"], recibo
    return kernel


def _entrega(id_task: str, autor: str) -> list[dict[str, Any]]:
    """Artifact sem arquivo, a prova do envio e a troca de status, no lote de quem executa."""
    def no(id_no: str, tipo: str, **propriedades: object) -> list[dict[str, Any]]:
        valor = {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": propriedades}
        produz = f"produz-{SESSAO}-{id_no}"
        return [
            {"op": "add", "path": f"/nos/{id_no}", "value": valor},
            {"op": "add", "path": f"/arestas/{produz}", "value": {"id": produz, "origem_id": SESSAO, "destino_id": id_no, "tipo": "produz"}},
        ]

    def deriva(origem: str, destino: str) -> dict[str, Any]:
        id_aresta = f"deriva_de-{origem}-{destino}"
        return {"op": "add", "path": f"/arestas/{id_aresta}", "value": {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": "deriva_de"}}

    return [
        *no("art-envio", "Artifact", resumo=f"relatorio enviado por {autor}"),
        deriva("art-envio", id_task),
        *no("evi-envio", "Evidence", fonte="caixa de saida", resultado="enviado 06/10 14:02 para a diretoria"),
        deriva("evi-envio", "art-envio"),
        deriva("evi-envio", id_task),
        {"op": "replace", "path": f"/nos/{id_task}/propriedades/status", "value": StatusTask.PRONTO_PARA_REVISAO.value},
    ]


def test_criar_tarefa_grava_a_entrega_e_a_fila_a_devolve_nominal() -> None:
    """A entrega vai para a Task e volta na fila; a Task sem ela vem como artefato."""
    kernel = _montar()
    fila = _chamar(_servidor(kernel, "orquestrador", "planejador"), "proximas_tarefas", id_sessao=SESSAO)

    entregas = {tarefa["id"]: tarefa["entrega"] for tarefa in fila["tarefas"]}
    assert entregas["t-envio"] == "acao_externa"
    assert all(entrega == "artefato" for id_task, entrega in entregas.items() if id_task != "t-envio")


def test_criar_tarefa_recusa_entrega_desconhecida_edge_case() -> None:
    """Caso de borda: um valor inventado tiraria a Task da reserva da política."""
    kernel = montar_kernel_de_dois_projetos()
    recibo = _chamar(
        _servidor(kernel, "orquestrador", "planejador"), "criar_tarefa",
        titulo="Ligar para o fornecedor", id_sessao=SESSAO, entrega="telefonema",
    )

    assert recibo["sucesso"] is False
    assert "acao_externa" in recibo["erro"]


def test_executor_nao_assume_acao_externa_sob_a_politica_padrao_edge_case() -> None:
    """Caso de borda: com o gesto do humano, o executor não pega a tarefa nem pelo lote direto."""
    kernel = _montar()
    executor = _servidor(kernel, "executor-sonnet#e1", "executor")

    recusa = _chamar(executor, "assumir_tarefa", id_task="t-envio")
    direto = _chamar(executor, "propor_patch", operacoes=_entrega("t-envio", "executor"), justificativa="entrega")

    assert recusa["sucesso"] is False
    assert "acao_externa" in str(recusa)
    assert kernel.obter_dono_do_lock("t-envio") is None
    assert direto["sucesso"] is False
    assert direto["modo_de_falha"] == "violacao_permissao_papel"


def test_humano_executa_o_revisor_aprova_e_o_executor_fecha_nominal() -> None:
    """A pessoa envia e registra a prova; a revisão julga a prova; o executor fecha como sempre."""
    kernel = _montar()
    humano = _servidor(kernel, "david", "humano")
    assert _chamar(humano, "assumir_tarefa", id_task="t-envio")["sucesso"]
    assert _chamar(humano, "propor_patch", operacoes=_entrega("t-envio", "david"), justificativa="enviei")["sucesso"]
    assert _chamar(humano, "liberar_tarefa", id_task="t-envio")["sucesso"]

    veredito = [
        {"op": "add", "path": "/nos/evi-ver", "value": {"id": "evi-ver", "tipo": "Evidence", "rotulo": "veredito", "propriedades": {"veredito": "aprovado"}}},
        {"op": "add", "path": "/arestas/p-ver", "value": {"id": "p-ver", "origem_id": SESSAO, "destino_id": "evi-ver", "tipo": "produz"}},
        {"op": "add", "path": "/arestas/d-ver", "value": {"id": "d-ver", "origem_id": "evi-ver", "destino_id": "art-envio", "tipo": "deriva_de"}},
    ]
    assert _chamar(_servidor(kernel, "revisor#r1", "revisor"), "propor_patch", operacoes=veredito, justificativa="veredito")["sucesso"]

    fechador = _servidor(kernel, "executor-sonnet#f1", "executor")
    assert _chamar(fechador, "assumir_tarefa", id_task="t-envio")["sucesso"]
    fechamento = _chamar(fechador, "concluir_tarefa", id_task="t-envio", justificativa="revisao aprovada")

    assert fechamento["sucesso"], fechamento
    assert kernel.obter_view().obter_no("t-envio").obter_propriedade("status") == StatusTask.CONCLUIDO.value


def test_politica_que_entrega_ao_executor_libera_o_ciclo_inteiro_nominal() -> None:
    """Com `acao_externa: executor`, o executor que tem as ferramentas assume e entrega."""
    kernel = _montar(acao_externa=VALOR_EXECUTOR)
    executor = _servidor(kernel, "executor-sonnet#e1", "executor")

    assert _chamar(executor, "assumir_tarefa", id_task="t-envio")["sucesso"]
    entrega = _chamar(executor, "propor_patch", operacoes=_entrega("t-envio", "executor"), justificativa="entrega")

    assert entrega["sucesso"], entrega
    vista = _chamar(executor, "ler_vista", id_alvo="t-envio")["conteudo"]
    assert "acao_externa com o executor" in vista


def test_executor_nao_troca_a_entrega_para_fugir_da_reserva_edge_case() -> None:
    """Caso de borda: tirar `acao_externa` da Task seria o atalho para assumi-la."""
    kernel = _montar()
    recibo = _chamar(_servidor(kernel, "executor-sonnet#e1", "executor"), "propor_patch", justificativa="atalho", operacoes=[
        {"op": "replace", "path": "/nos/t-envio/propriedades/entrega", "value": "artefato"},
    ])

    assert recibo["sucesso"] is False
    assert recibo["modo_de_falha"] == "violacao_permissao_papel"


def test_task_de_artefato_segue_livre_para_o_executor_edge_case() -> None:
    """Caso de borda: a reserva não toca a Task de sempre, que não declara entrega."""
    kernel = _montar()
    kernel.liberar_lock_task("task-a", "executor-alheio#abc123")
    assert _chamar(_servidor(kernel, "executor-sonnet#e1", "executor"), "assumir_tarefa", id_task="task-a")["sucesso"]


@pytest.mark.parametrize("preset", [PresetGovernanca.GOVERNANCA_MAXIMA, PresetGovernanca.ARBITRAGEM_MAXIMA])
def test_os_dois_presets_fixos_deixam_a_acao_externa_com_o_humano_nominal(preset: PresetGovernanca) -> None:
    """Agir no mundo em nome da pessoa não é julgamento: nem a arbitragem máxima o delega."""
    politica = politica_do_preset(preset)

    assert politica.valor(Gesto.ACAO_EXTERNA) == VALOR_HUMANO
    assert politica.acao_externa_com_executor is False


def test_composicao_mais_restritiva_devolve_a_acao_externa_ao_humano_edge_case() -> None:
    """Caso de borda: nó em dois projetos, um que delega e outro que não, fica com o humano."""
    base = politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA)
    delega = type(base)({**base.valores, Gesto.ACAO_EXTERNA: VALOR_EXECUTOR}, base.origens)

    composta = compor_mais_restritiva({"proj-a": delega, "proj-b": base})

    assert composta.valor(Gesto.ACAO_EXTERNA) == VALOR_HUMANO
    assert composta.origem(Gesto.ACAO_EXTERNA) == "projeto:proj-b"


def test_permite_recusa_perguntar_pela_acao_externa_edge_case() -> None:
    """Caso de borda: a ação externa não se decide por papel do árbitro; tem leitura própria."""
    with pytest.raises(ValueError):
        politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA).permite(Gesto.ACAO_EXTERNA, PapelAutor.EXECUTOR)
