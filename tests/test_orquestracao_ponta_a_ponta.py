"""O ciclo de uma orquestração sobre o grafo, papel por papel: decompor, executar, revisar, corrigir e medir.

Cada agente é um servidor MCP com a própria identidade sobre o mesmo kernel,
como numa orquestração real: o orquestrador no papel planejador, os executores e
o revisor com posse própria. Se um lote que um agente monta nesse ciclo esbarrar
num portão, é aqui que aparece, e não no primeiro despacho de verdade.
"""

from typing import Any

from graphow.avaliacao.orquestracao import MedidorDeOrquestracao
from graphow.core.events import TipoEvento
from graphow.core.types import PapelAutor, StatusTask
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer

SESSAO: str = "sess-orq"
TRECHO: str = "def taxa_para_fator(taxa, dias):\n    return (1 + taxa) ** (-dias / 252)"


def _no(id_no: str, tipo: str, **propriedades: object) -> dict[str, Any]:
    """Operação de criação de nó, no formato que o agente manda por propor_patch."""
    return {"op": "add", "path": f"/nos/{id_no}", "value": {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": propriedades}}


def _aresta(origem: str, destino: str, tipo: str) -> dict[str, Any]:
    """Operação de criação de aresta, com id derivado das pontas."""
    id_aresta = f"{tipo}-{origem}-{destino}"
    return {"op": "add", "path": f"/arestas/{id_aresta}", "value": {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo}}


def _produzido(id_no: str, tipo: str, **propriedades: object) -> list[dict[str, Any]]:
    """O nó e a aresta produz vinda da sessão do orquestrador."""
    return [_no(id_no, tipo, **propriedades), _aresta(SESSAO, id_no, "produz")]


def _chamar(agente: GraphowMCPServer, ferramenta: str, **argumentos: object) -> dict[str, Any]:
    """Chama a ferramenta e exige sucesso, mostrando a recusa quando houver."""
    recibo = agente.executar_ferramenta(ferramenta, argumentos)
    assert recibo["sucesso"], recibo
    return recibo


def _agente(kernel: WriteKernel, autor: str, papel: str) -> GraphowMCPServer:
    """Um servidor MCP com a identidade fixada, como cada subagente o abre."""
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar(autor, papel))


def _montar_goal() -> WriteKernel:
    """O humano abre o Goal numa sessão sua; o harness abriu a sessão do orquestrador."""
    kernel = montar_kernel_em_memoria()
    operacoes = tuple(
        ItemPatch(op=OperacaoPatch(op["op"]), path=op["path"], value=op["value"])
        for op in [
            _no("proj", "Projeto"), _no("setor", "Setor"), _aresta("proj", "setor", "contem"),
            _no("sess-h", "Sessao"), _aresta("setor", "sess-h", "contem"),
            _no(SESSAO, "Sessao"), _aresta("setor", SESSAO, "contem"),
            _no("goal", "Goal", configuracao="padrao"), _aresta("sess-h", "goal", "produz"),
        ]
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="goal")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso
    return kernel


def _decompor(orquestrador: GraphowMCPServer) -> None:
    """Passo 2: a leitura localizada, a decisão que ela justifica e a Task que a decisão orienta."""
    lote = [
        *_produzido("evi-fator", "Evidence", arquivo="src/precos/fator.py", linhas="40-41", trecho=TRECHO),
        *_produzido("dec-fator", "Decision", motivo="reusar a funcao que ja aplica a base 252"),
        _aresta("evi-fator", "dec-fator", "justifica"),
    ]
    _chamar(orquestrador, "propor_patch", operacoes=lote, justificativa="leitura e decisao")
    _chamar(
        orquestrador, "criar_tarefa", titulo="Preco usa o fator", id_task="t1", id_sessao=SESSAO, id_tarefa_pai="goal",
        criterio_pronto="o preco usa taxa_para_fator e o teste de base 252 passa", arquivos_alvo=["src/precos/preco.py"],
        modelo="opus", motivo_modelo="convencao de calendario", decisoes=["dec-fator"],
    )


def _entrega(id_task: str, id_artifact: str) -> list[dict[str, Any]]:
    """O lote único do passo 6 do executor: Artifact, Evidence da verificação e a troca de status."""
    id_evidencia = f"evi-verif-{id_task}"
    return [
        *_produzido(id_artifact, "Artifact", arquivos=["src/precos/preco.py"], resumo="preco via taxa_para_fator"),
        _aresta(id_artifact, id_task, "deriva_de"),
        *_produzido(id_evidencia, "Evidence", comando="pytest tests/precos", resultado="3 passed"),
        _aresta(id_evidencia, id_artifact, "deriva_de"),
        _aresta(id_evidencia, id_task, "deriva_de"),
        {"op": "replace", "path": f"/nos/{id_task}/propriedades/status", "value": StatusTask.PRONTO_PARA_REVISAO.value},
    ]


def _executar(executor: GraphowMCPServer, id_task: str, id_artifact: str) -> None:
    """O protocolo do executor despachado: posse, vista, um lote com Artifact, Evidence e status, e liberar."""
    _chamar(executor, "assumir_tarefa", id_task=id_task)
    vista = _chamar(executor, "ler_vista", id_alvo=id_task, orcamento_tokens=2500)["conteudo"]
    assert "dec-fator" in vista
    _chamar(executor, "propor_patch", operacoes=_entrega(id_task, id_artifact), justificativa="entrega")
    _chamar(executor, "liberar_tarefa", id_task=id_task)


def _revisar(
    revisor: GraphowMCPServer, id_artifact: str, id_task: str, *, aprovar: bool, gravidade: str = "bloqueante"
) -> str:
    """O protocolo do revisor despachado: o veredito deriva do Artifact e da Task; a reprovação traz o trecho e a gravidade."""
    vista = _chamar(revisor, "ler_vista", id_alvo=id_artifact)["conteudo"]
    assert "Decisoes Que Governam Esta Tarefa" in vista
    id_veredito = f"evi-veredito-{id_artifact}"
    lote = [
        *_produzido(id_veredito, "Evidence", veredito="aprovado" if aprovar else "rejeitado", criterios="base 252"),
        _aresta(id_veredito, id_artifact, "deriva_de"),
        _aresta(id_veredito, id_task, "deriva_de"),
    ]
    if not aprovar:
        id_falha = f"evi-falha-{id_artifact}"
        trecho = "fator = 1 / (1 + taxa)"
        lote += [
            *_produzido(id_falha, "Evidence", arquivo="src/precos/preco.py", linhas="12", trecho=trecho, gravidade=gravidade),
            _aresta(id_falha, id_task, "deriva_de"),
            _aresta(id_falha, f"evi-verif-{id_task}", "contradiz"),
        ]
    _chamar(revisor, "propor_patch", operacoes=lote, justificativa="veredito")
    return id_veredito


def _corrigir(orquestrador: GraphowMCPServer, rejeicao: str) -> None:
    """A correção da t1, como o condutor a cria depois da primeira reprovação."""
    _chamar(
        orquestrador, "criar_tarefa", titulo="Corrigir o fator", id_task="t1c", id_sessao=SESSAO, id_tarefa_pai="t1",
        corrige=rejeicao, modelo="opus", motivo_modelo="falhou uma revisao", arquivos_alvo=["src/precos/preco.py"],
        criterio_pronto="o preco usa taxa_para_fator e o teste de base 252 passa; sem o fator 1/(1+taxa) da linha 12",
    )


def _fechar(kernel: WriteKernel, *ids_tasks: str) -> None:
    """O executor de fechamento: posse, conclusão e devolução, uma tarefa por vez."""
    fechador = _agente(kernel, "executor-sonnet#e5", "executor")
    for id_task in ids_tasks:
        _chamar(fechador, "assumir_tarefa", id_task=id_task)
        _chamar(fechador, "concluir_tarefa", id_task=id_task, justificativa="revisao aprovada ou aceite pelo teto")
        _chamar(fechador, "liberar_tarefa", id_task=id_task)


def test_ciclo_completo_da_orquestracao_passa_pelos_portoes_nominal() -> None:
    """Decompor, testar o executor frio, executar, reprovar, corrigir, aprovar, fechar e medir."""
    kernel = _montar_goal()
    orquestrador = _agente(kernel, "orquestrador", "planejador")
    _decompor(orquestrador)

    fria = _chamar(orquestrador, "ler_vista", id_alvo="t1", perspectiva="executor")["conteudo"]
    assert "## Decisoes Que Governam Esta Tarefa\n- [dec-fator]" in fria
    assert "src/precos/preco.py" in fria

    _executar(_agente(kernel, "executor-opus#a1", "executor"), "t1", "art-1")
    rejeicao = _revisar(_agente(kernel, "revisor-opus#b2", "revisor"), "art-1", "t1", aprovar=False)
    _corrigir(orquestrador, rejeicao)
    assert "evi-falha" in _chamar(orquestrador, "ler_vista", id_alvo="t1c", perspectiva="executor")["conteudo"]
    fila = _chamar(orquestrador, "proximas_tarefas", id_sessao="goal")
    assert [tarefa["id"] for tarefa in fila["tarefas"]] == ["t1c"]
    assert {"id": "t1", "motivo": "dependencia_pendente"}.items() <= fila["impedidas"][0].items()

    revisao_da_correcao = _chamar(_agente(kernel, "revisor-opus#x9", "revisor"), "ler_vista", id_alvo="t1c")["conteudo"]
    assert "sem o fator 1/(1+taxa)" in revisao_da_correcao
    assert rejeicao in revisao_da_correcao
    _executar(_agente(kernel, "executor-opus#c3", "executor"), "t1c", "art-2")
    _revisar(_agente(kernel, "revisor-opus#d4", "revisor"), "art-2", "t1c", aprovar=True)
    _fechar(kernel, "t1c", "t1")

    pedido = PedidoDeExecucao(
        id_run="run-exec", id_sessao=SESSAO, tipo_evento=TipoEvento.EXECUCAO_CONCLUIDA,
        dados={"agente": "graphow-executor-opus", "tarefas": ["t1", "t1c"], "tokens_entrada": 900, "tokens_saida": 100},
    )
    assert kernel.registrar_execucao(pedido).sucesso
    (medicao,) = MedidorDeOrquestracao(kernel.obter_view()).medir(["goal"])
    assert (medicao.tarefas, medicao.concluidas, medicao.concluidas_sem_retrabalho) == (1, 1, 0)
    assert (medicao.correcoes, medicao.rejeicoes, medicao.aprovacoes) == (1, 1, 1)
    assert medicao.tokens_por_agente == {"graphow-executor-opus": 1000}


def test_executor_que_reinicia_no_meio_da_tarefa_fecha_sem_o_humano_edge_case() -> None:
    """Caso de borda: o servidor do executor volta com outro sufixo e perde a posse; a revisão aprova e o fechamento a retoma."""
    kernel = _montar_goal()
    _decompor(_agente(kernel, "orquestrador", "planejador"))
    _chamar(_agente(kernel, "executor-opus#a1", "executor"), "assumir_tarefa", id_task="t1")
    reiniciado = _agente(kernel, "executor-opus#a2", "executor")

    recusa = reiniciado.executar_ferramenta("propor_patch", {"operacoes": _entrega("t1", "art-1"), "justificativa": "entrega"})
    assert recusa["modo_de_falha"] == "conflito_concorrencia_lock"
    sem_status = [op for op in _entrega("t1", "art-1") if not op["path"].endswith("/status")]
    _chamar(reiniciado, "propor_patch", operacoes=sem_status, justificativa="entrega sem a troca de status")
    assert reiniciado.executar_ferramenta("liberar_tarefa", {"id_task": "t1"})["sucesso"] is False

    _revisar(_agente(kernel, "revisor-opus#b2", "revisor"), "art-1", "t1", aprovar=True)
    fechador = _agente(kernel, "executor-sonnet#e5", "executor")
    assert _chamar(fechador, "assumir_tarefa", id_task="t1")["posse_retomada_de"] == "executor-opus#a1"
    _chamar(fechador, "concluir_tarefa", id_task="t1", justificativa="revisao aprovada")
    _chamar(fechador, "liberar_tarefa", id_task="t1")

    assert kernel.obter_view().obter_no("t1").obter_propriedade("status") == StatusTask.CONCLUIDO.value
    assert kernel.obter_dono_do_lock("t1") is None
    (medicao,) = MedidorDeOrquestracao(kernel.obter_view()).medir(["goal"])
    assert (medicao.concluidas_sem_retrabalho, medicao.rejeicoes, medicao.aprovacoes) == (1, 0, 1)


def test_segunda_reprovacao_sem_bloqueante_fecha_pelo_teto_edge_case() -> None:
    """Caso de borda: a correção reprovada só com acompanhamento fecha com a original, e o resto vira outra Task.

    O veredito vigente das duas é `rejeitado`, e nenhum portão olha para ele no
    fechamento: com a posse livre, o executor assume e conclui como sempre. A
    tarefa de acompanhamento nasce no Goal e sem `corrige`, e por isso não
    prende a original.
    """
    kernel = _montar_goal()
    orquestrador = _agente(kernel, "orquestrador", "planejador")
    _decompor(orquestrador)
    _executar(_agente(kernel, "executor-opus#a1", "executor"), "t1", "art-1")
    _corrigir(orquestrador, _revisar(_agente(kernel, "revisor-opus#b2", "revisor"), "art-1", "t1", aprovar=False))
    _executar(_agente(kernel, "executor-opus#c3", "executor"), "t1c", "art-2")
    segunda = _revisar(_agente(kernel, "revisor-opus#d4", "revisor"), "art-2", "t1c", aprovar=False, gravidade="acompanhamento")

    aceite = [
        *_produzido("dec-aceite", "Decision", acao="aceite_apos_reprovacao", motivo="so ficou criterio de acompanhamento"),
        _aresta(segunda, "dec-aceite", "justifica"),
        _aresta("dec-aceite", "t1", "orienta"),
        _aresta("dec-aceite", "t1c", "orienta"),
    ]
    _chamar(orquestrador, "propor_patch", operacoes=aceite, justificativa="aceite apos segunda reprovacao")
    _chamar(
        orquestrador, "criar_tarefa", titulo="Acompanhar o fator da linha 12", id_task="t1-acomp", id_sessao=SESSAO,
        id_tarefa_pai="goal", decisoes=["dec-aceite"], arquivos_alvo=["src/precos/preco.py"],
        criterio_pronto="sem o fator 1/(1+taxa) da linha 12 (evi-falha-art-2)",
    )
    _fechar(kernel, "t1c", "t1")

    view = kernel.obter_view()
    assert {view.obter_no(id_task).obter_propriedade("status") for id_task in ("t1", "t1c")} == {StatusTask.CONCLUIDO.value}
    fila = _chamar(orquestrador, "proximas_tarefas", id_sessao="goal")
    assert [tarefa["id"] for tarefa in fila["tarefas"]] == ["t1-acomp"]


def test_executor_sem_posse_nao_entrega_a_tarefa_de_outro_edge_case() -> None:
    """Caso de borda: dois executores da mesma definição, cada um com posse própria, não se confundem."""
    kernel = _montar_goal()
    _decompor(_agente(kernel, "orquestrador", "planejador"))
    _chamar(_agente(kernel, "executor-sonnet#a1", "executor"), "assumir_tarefa", id_task="t1")

    recusa = _agente(kernel, "executor-sonnet#b2", "executor").executar_ferramenta("assumir_tarefa", {"id_task": "t1"})

    assert recusa["sucesso"] is False
    assert recusa["dono_atual"] == "executor-sonnet#a1"


def test_orquestrador_nao_registra_leitura_sem_trecho_edge_case() -> None:
    """Caso de borda: a conclusão do orquestrador sem o trecho que a sustenta não entra no grafo."""
    kernel = _montar_goal()
    orquestrador = _agente(kernel, "orquestrador", "planejador")

    recibo = orquestrador.executar_ferramenta(
        "propor_patch",
        {"operacoes": _produzido("evi", "Evidence", arquivo="src/precos/fator.py", resumo="usa base 252"), "justificativa": "x"},
    )

    assert recibo["sucesso"] is False
    assert recibo["modo_de_falha"] == "evidencia_sem_localizacao"
    assert kernel.obter_view().obter_no("evi") is None
