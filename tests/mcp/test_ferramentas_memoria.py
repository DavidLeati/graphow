"""Testes das ferramentas MCP de memória: encerrar a sessão pela superfície do agente."""

from graphow.core.types import PapelAutor, StatusSessao, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer


def _no(id_no: str, tipo: TipoNo, rotulo: str) -> ItemPatch:
    """Operação de criação de nó."""
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _montar_kernel() -> WriteKernel:
    """Hierarquia com uma sessão que já produziu uma decisão e um artefato."""
    kernel = montar_kernel_em_memoria()
    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=[
                    _no("proj", TipoNo.PROJETO, "Projeto"),
                    _no("setor", TipoNo.SETOR, "Setor"),
                    _aresta("proj", "setor", TipoAresta.CONTEM),
                    _no("sess", TipoNo.SESSAO, "Sessao"),
                    _aresta("setor", "sess", TipoAresta.CONTEM),
                    _no("dec-1", TipoNo.DECISION, "Decisao"),
                    _aresta("sess", "dec-1", TipoAresta.PRODUZ),
                    _no("art-1", TipoNo.ARTIFACT, "Artefato"),
                    _aresta("sess", "art-1", TipoAresta.PRODUZ),
                ],
                justificativa="cenario",
            )
        )
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _servidor(papel: str) -> tuple[GraphowMCPServer, WriteKernel]:
    """Servidor MCP sobre o cenário, sob o papel informado."""
    kernel = _montar_kernel()
    return GraphowMCPServer(kernel, IdentidadeSessaoMCP.criar("autor", papel)), kernel


def test_humano_encerra_a_sessao_e_recebe_o_fechamento_nominal() -> None:
    """Encerrar grava o status, o resumo, e devolve o esqueleto do que ficou em vigor."""
    servidor, kernel = _servidor("humano")

    resposta = servidor.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess", "resumo": "fatia pronta"})

    assert resposta["sucesso"] is True
    sessao = kernel.obter_view().obter_no("sess")
    assert sessao.obter_propriedade("status") == StatusSessao.CONCLUIDA.value
    assert sessao.obter_propriedade("resumo") == "fatia pronta"
    assert resposta["fechamento"]["decisoes_vigentes"] == ["dec-1"]
    assert resposta["fechamento"]["ultimo_artefato"] == "art-1"


def test_encerrar_sem_resumo_nao_grava_resumo_vazio_edge_case() -> None:
    """Caso de borda: um resumo em branco não vira propriedade em branco."""
    servidor, kernel = _servidor("humano")

    servidor.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess"})

    assert kernel.obter_view().obter_no("sess").obter_propriedade("resumo") is None


def test_agente_nao_encerra_sessao_edge_case() -> None:
    """Caso de borda: encerrar é gesto do humano ou do harness, não do agente."""
    servidor, kernel = _servidor("planejador")

    resposta = servidor.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess"})

    assert resposta["sucesso"] is False
    assert "exige uma sessao humana" in resposta["erro"]
    assert kernel.obter_view().obter_no("sess").obter_propriedade("status") is None


def test_encerrar_sessao_inexistente_e_recusa_explicada_edge_case() -> None:
    """Caso de borda: um id que não é Sessão devolve erro nomeado, não patch recusado."""
    servidor, _ = _servidor("humano")

    resposta = servidor.executar_ferramenta("encerrar_sessao", {"id_sessao": "dec-1"})

    assert resposta["sucesso"] is False
    assert "nao existe" in resposta["erro"]


def test_agente_registra_aprendizado_com_origens_nominal() -> None:
    """Registrar é de todo papel: o nó nasce pendurado na sessão e derivado de cada origem."""
    servidor, kernel = _servidor("executor")

    resposta = servidor.executar_ferramenta(
        "registrar_aprendizado",
        {
            "afirmacao": "Lote sem contencao e recusado inteiro",
            "como_aplicar": "Traga o produz no mesmo lote",
            "id_sessao": "sess",
            "origens": ["dec-1", "art-1"],
        },
    )

    assert resposta["sucesso"] is True, resposta
    view = kernel.obter_view()
    aprendizado = view.obter_no(resposta["id_aprendizado"])
    assert aprendizado.tipo == TipoNo.APRENDIZADO
    assert aprendizado.obter_propriedade("como_aplicar") == "Traga o produz no mesmo lote"
    destinos = {aresta.destino_id for aresta in view.obter_arestas_saida(aprendizado.id, TipoAresta.DERIVA_DE)}
    assert destinos == {"dec-1", "art-1"}


def test_registrar_sem_origem_e_recusa_explicada_edge_case() -> None:
    """Caso de borda: a ferramenta explica o que falta antes de o portão recusar."""
    servidor, _ = _servidor("executor")

    resposta = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Sem origem", "id_sessao": "sess", "origens": []}
    )

    assert resposta["sucesso"] is False
    assert "origens" in resposta["erro"]


def test_agente_nao_promove_aprendizado_edge_case() -> None:
    """Caso de borda: dar alcance é decisão humana, por qualquer superfície."""
    servidor, _ = _servidor("executor")
    registro = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Licao", "id_sessao": "sess", "origens": ["dec-1"]}
    )

    resposta = servidor.executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": registro["id_aprendizado"], "id_alvo": "proj"}
    )

    assert resposta["sucesso"] is False
    assert "exige uma sessao humana" in resposta["erro"]


def test_humano_promove_por_conteiner_e_por_marca_global_nominal() -> None:
    """A promoção tem duas formas: o alcance por contêiner e a marca global."""
    servidor, kernel = _servidor("humano")
    registro = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Licao", "id_sessao": "sess", "origens": ["dec-1"]}
    )
    id_aprendizado = registro["id_aprendizado"]

    por_conteiner = servidor.executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": id_aprendizado, "id_alvo": "setor"}
    )
    global_ = servidor.executar_ferramenta("promover_aprendizado", {"id_aprendizado": id_aprendizado, "global": True})

    assert por_conteiner["sucesso"] is True, por_conteiner
    assert global_["sucesso"] is True, global_
    view = kernel.obter_view()
    assert view.obter_arestas_saida(id_aprendizado, TipoAresta.VALE_PARA)[0].destino_id == "setor"
    assert view.obter_no(id_aprendizado).obter_propriedade("alcance") == "global"


def test_promover_de_novo_para_o_mesmo_alvo_nao_e_recusado_edge_case() -> None:
    """Caso de borda: a segunda promoção recriava `vale-<id>-<alvo>`, e `add` passou a só criar.

    O aprendizado já vale para o alvo; a ferramenta tira a aresta do lote em
    vez de pedir ao kernel uma criação que ele recusa.
    """
    servidor, kernel = _servidor("humano")
    registro = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Licao", "id_sessao": "sess", "origens": ["dec-1"]}
    )
    pedido = {"id_aprendizado": registro["id_aprendizado"], "id_alvo": "setor"}
    primeira = servidor.executar_ferramenta("promover_aprendizado", pedido)

    segunda = servidor.executar_ferramenta("promover_aprendizado", pedido)

    assert primeira["sucesso"] is True, primeira
    assert segunda["sucesso"] is True, segunda
    assert len(kernel.obter_view().obter_arestas_saida(registro["id_aprendizado"], TipoAresta.VALE_PARA)) == 1


def test_promover_sem_alvo_nem_global_e_recusa_explicada_edge_case() -> None:
    """Caso de borda: promover para lugar nenhum não é promover."""
    servidor, _ = _servidor("humano")

    resposta = servidor.executar_ferramenta("promover_aprendizado", {"id_aprendizado": "apr-x"})

    assert resposta["sucesso"] is False
    assert "id_alvo" in resposta["erro"]


def test_agente_consolida_registrando_com_substitui_nominal() -> None:
    """Consolidar é registrar com `substitui`: cada absorvido ganha a aresta no mesmo lote."""
    servidor, kernel = _servidor("revisor")
    primeiro = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Regra 1", "id_sessao": "sess", "origens": ["dec-1"]}
    )
    segundo = servidor.executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Regra 2", "id_sessao": "sess", "origens": ["art-1"]}
    )

    resposta = servidor.executar_ferramenta(
        "registrar_aprendizado",
        {
            "afirmacao": "Regra geral",
            "id_sessao": "sess",
            "origens": ["dec-1", "art-1"],
            "substitui": [primeiro["id_aprendizado"], segundo["id_aprendizado"]],
        },
    )

    assert resposta["sucesso"] is True, resposta
    view = kernel.obter_view()
    absorvidos = {a.destino_id for a in view.obter_arestas_saida(resposta["id_aprendizado"], TipoAresta.SUBSTITUI)}
    assert absorvidos == {primeiro["id_aprendizado"], segundo["id_aprendizado"]}
