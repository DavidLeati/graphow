"""O que o orquestrador grava na Task e lê de volta: modelo, arquivos-alvo e decisões."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer


def _no(id_no: str, tipo: TipoNo) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": id_no})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _montar() -> tuple[WriteKernel, GraphowMCPServer]:
    """O humano abre o Goal numa sessão; o planejador decide noutra, e é dela que cria as tarefas."""
    kernel = montar_kernel_em_memoria()
    operacoes = (
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess-humano", TipoNo.SESSAO), _aresta("setor", "sess-humano", TipoAresta.CONTEM),
        _no("sess-orq", TipoNo.SESSAO), _aresta("setor", "sess-orq", TipoAresta.CONTEM),
        _no("goal", TipoNo.GOAL), _aresta("sess-humano", "goal", TipoAresta.PRODUZ),
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="base")
    assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso
    planejador = GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("orquestrador", "planejador"))
    decisao = [
        {"op": "add", "path": "/nos/dec", "value": {"id": "dec", "tipo": "Decision", "rotulo": "Reusar taxa_para_fator"}},
        {"op": "add", "path": "/arestas/prod-dec", "value": {"id": "prod-dec", "origem_id": "sess-orq", "destino_id": "dec", "tipo": "produz"}},
    ]
    assert planejador.executar_ferramenta("propor_patch", {"operacoes": decisao, "justificativa": "decidir"})["sucesso"]
    return kernel, planejador


def _criar(planejador: GraphowMCPServer, id_task: str, **extras: object) -> dict:
    """Task da sessão do orquestrador decompondo o Goal."""
    argumentos = {"titulo": id_task, "id_task": id_task, "id_sessao": "sess-orq", "id_tarefa_pai": "goal", **extras}
    return planejador.executar_ferramenta("criar_tarefa", argumentos)


def test_criar_tarefa_grava_modelo_arquivos_e_orienta_nominal() -> None:
    """Modelo com motivo, arquivos-alvo e a decisão ligada pela aresta orienta, num lote só."""
    kernel, planejador = _montar()

    recibo = _criar(
        planejador, "t1", modelo="Opus", motivo_modelo="convencao de calendario",
        arquivos_alvo=["src/precos/fator.py", "src/precos/fator.py", " "], decisoes=["dec"],
    )

    assert recibo["sucesso"] is True, recibo
    tarefa = kernel.obter_view().obter_no("t1")
    assert tarefa.obter_propriedade("modelo") == "opus"
    assert tarefa.obter_propriedade("motivo_modelo") == "convencao de calendario"
    assert tarefa.obter_propriedade("arquivos_alvo") == ["src/precos/fator.py"]
    orientacoes = kernel.obter_view().obter_arestas_entrada("t1", TipoAresta.ORIENTA)
    assert [aresta.origem_id for aresta in orientacoes] == ["dec"]


def test_modelo_sem_motivo_e_recusado_edge_case() -> None:
    """Caso de borda: a escolha de modelo sem motivo não fica auditável, e a tarefa não nasce."""
    kernel, planejador = _montar()

    recibo = _criar(planejador, "t1", modelo="opus")

    assert recibo["sucesso"] is False
    assert "motivo_modelo" in recibo["erro"]
    assert kernel.obter_view().obter_no("t1") is None


def test_decisao_inexistente_derruba_o_lote_inteiro_edge_case() -> None:
    """Caso de borda: a aresta para uma decisão que não existe não deixa a tarefa nascer pela metade."""
    kernel, planejador = _montar()

    recibo = _criar(planejador, "t1", decisoes=["dec-fantasma"])

    assert recibo["sucesso"] is False
    assert kernel.obter_view().obter_no("t1") is None


def test_tarefa_sem_orquestracao_nao_muda_de_forma_edge_case() -> None:
    """Caso de borda: quem não usa a orquestração continua recebendo a Task de sempre."""
    kernel, planejador = _montar()

    assert _criar(planejador, "t1")["sucesso"]

    propriedades = kernel.obter_view().obter_no("t1").propriedades
    assert set(propriedades) == {"status", "descricao", "criterio_pronto"}


def test_fila_do_goal_traz_o_que_decide_o_despacho_nominal() -> None:
    """A fila pedida pelo Goal devolve modelo e arquivos-alvo de cada tarefa pronta."""
    _, planejador = _montar()
    _criar(planejador, "t1", modelo="opus", motivo_modelo="dominio", arquivos_alvo=["a.py"])
    _criar(planejador, "t2", arquivos_alvo=["b.py"])

    fila = planejador.executar_ferramenta("proximas_tarefas", {"id_sessao": "goal"})

    por_id = {tarefa["id"]: tarefa for tarefa in fila["tarefas"]}
    assert por_id["t1"]["modelo"] == "opus"
    assert por_id["t1"]["arquivos_alvo"] == ["a.py"]
    assert por_id["t2"]["modelo"] == ""
    assert por_id["t2"]["arquivos_alvo"] == ["b.py"]
