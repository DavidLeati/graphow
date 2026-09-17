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
