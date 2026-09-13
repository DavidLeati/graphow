"""Testes das ferramentas MCP de leitura: busca ranqueada, escopo e panorama na vista."""

from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.mcp.identidade_sessao import IdentidadeSessaoMCP
from graphow.mcp.server import GraphowMCPServer


def _no(id_no: str, tipo: TipoNo, rotulo: str, **propriedades: str) -> ItemPatch:
    """Operação de criação de nó com propriedades opcionais."""
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/nos/{id_no}",
        value={"id": id_no, "tipo": tipo.value, "rotulo": rotulo, "propriedades": dict(propriedades)},
    )


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de aresta entre dois nós."""
    id_aresta = f"{origem}-{destino}"
    return ItemPatch(
        op=OperacaoPatch.ADD,
        path=f"/arestas/{id_aresta}",
        value={"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value},
    )


def _montar_operacoes() -> tuple[ItemPatch, ...]:
    """Dois setores: um com oito tarefas abertas, outro com trabalho já encerrado."""
    operacoes = [
        _no("proj-1", TipoNo.PROJETO, "Projeto de cache"),
        _no("setor-1", TipoNo.SETOR, "Setor de infraestrutura"),
        _no("sess-1", TipoNo.SESSAO, "Sessao corrente"),
        _no("setor-2", TipoNo.SETOR, "Setor arquivado"),
        _no("sess-2", TipoNo.SESSAO, "Sessao encerrada"),
        _no("t-velha", TipoNo.TASK, "Cache antigo desativado", status=StatusTask.CONCLUIDO.value),
        _aresta("proj-1", "setor-1", TipoAresta.CONTEM),
        _aresta("setor-1", "sess-1", TipoAresta.CONTEM),
        _aresta("proj-1", "setor-2", TipoAresta.CONTEM),
        _aresta("setor-2", "sess-2", TipoAresta.CONTEM),
        _aresta("sess-2", "t-velha", TipoAresta.PRODUZ),
    ]
    for indice in range(8):
        operacoes.append(
            _no(f"t{indice}", TipoNo.TASK, f"Tarefa de cache {indice}", status=StatusTask.PENDENTE.value)
        )
        operacoes.append(_aresta("sess-1", f"t{indice}", TipoAresta.PRODUZ))
    return tuple(operacoes)


def _montar_kernel() -> WriteKernel:
    """Escreve o cenário como humano, que é quem pode criar a camada de navegação."""
    kernel = montar_kernel_em_memoria()
    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=_montar_operacoes(),
                justificativa="Cenario de teste",
            )
        )
    )
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _servidor() -> GraphowMCPServer:
    """Servidor MCP com identidade de planejador fixada na abertura."""
    return GraphowMCPServer(_montar_kernel(), IdentidadeSessaoMCP.criar("agente", "planejador"))


def test_busca_corta_no_limite_e_declara_o_total() -> None:
    """Sem o total, o agente não sabe que precisa refinar o termo."""
    resposta = _servidor().executar_ferramenta("buscar", {"termo": "cache", "limite": 3})

    assert resposta["sucesso"] is True
    assert len(resposta["resultados"]) == 3
    assert resposta["total"] == 10
    assert resposta["truncado"] is True


def test_busca_usa_limite_padrao_quando_ele_nao_e_informado() -> None:
    """O padrão precisa ser pequeno: a resposta inteira era o problema."""
    resposta = _servidor().executar_ferramenta("buscar", {"termo": "cache"})

    assert len(resposta["resultados"]) == 5
    assert resposta["exibidos"] == 5


def test_resultado_da_busca_e_esqueletico() -> None:
    """Descrição longa e histórico não entram: é o que a busca economiza."""
    resposta = _servidor().executar_ferramenta("buscar", {"termo": "cache", "limite": 1})

    assert set(resposta["resultados"][0]) == {"id", "tipo", "rotulo", "seq_criacao", "casou_em"}


def test_tarefa_aberta_vence_a_concluida_no_ranking() -> None:
    """Empatado o casamento, o que ainda pede trabalho aparece antes."""
    resposta = _servidor().executar_ferramenta(
        "buscar", {"termo": "cache", "tipos_no": ["Task"], "limite": 9}
    )

    assert resposta["resultados"][-1]["id"] == "t-velha"


def test_tipo_de_no_invalido_devolve_recusa_explicada() -> None:
    """Antes isso levantava ValueError cru e virava erro de servidor."""
    resposta = _servidor().executar_ferramenta("buscar", {"termo": "cache", "tipos_no": ["Galaxia"]})

    assert resposta["sucesso"] is False
    assert "Galaxia" in resposta["mensagem"]


def test_filtro_de_tipo_valido_segue_funcionando() -> None:
    """A guarda de tipo inválido não pode ter quebrado o filtro legítimo."""
    resposta = _servidor().executar_ferramenta("buscar", {"termo": "cache", "tipos_no": ["Projeto"]})

    assert resposta["sucesso"] is True
    assert resposta["total"] == 1


def test_vista_de_conteiner_traz_o_panorama_agregado() -> None:
    """A vista do setor precisa dizer o progresso sem listar as oito tarefas."""
    resposta = _servidor().executar_ferramenta("ler_vista", {"id_alvo": "setor-1"})

    assert resposta["sucesso"] is True
    assert "Panorama dos Filhos" in resposta["conteudo"]
    assert "0/8 tarefas concluidas" in resposta["conteudo"]
    assert "trabalho aberto" in resposta["conteudo"]


def test_vista_do_projeto_aponta_o_setor_com_trabalho_aberto() -> None:
    """É o que troca a varredura da hierarquia por uma descida orientada."""
    resposta = _servidor().executar_ferramenta("ler_vista", {"id_alvo": "proj-1"})

    linhas = [linha for linha in resposta["conteudo"].splitlines() if "setor-" in linha]
    assert "setor-1" in linhas[0]
    assert "trabalho aberto" in linhas[0]


def test_escopo_ativo_e_opcional_e_desligado_por_padrao() -> None:
    """Esconder memória do agente por default custa mais do que economiza."""
    servidor = _servidor()
    padrao = servidor.executar_ferramenta("buscar", {"termo": "antigo"})
    ativo = servidor.executar_ferramenta("buscar", {"termo": "antigo", "escopo": "ativo"})

    assert padrao["total"] == 1
    assert ativo["total"] == 0
