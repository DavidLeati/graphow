"""Testes unitários para GraphowCLI."""

from graphow.api.cli import GraphowCLI, descrever_localizacao_banco, main
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.storage.localizador_banco import LocalizacaoBanco, OrigemCaminhoBanco
from pathlib import Path


def _construir_cli_com_sessao() -> tuple[GraphowCLI, WriteKernel]:
    """Cria uma CLI sobre um kernel em memória com uma Sessão já registrada."""
    kernel = WriteKernel(InMemoryEventStore())
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
                    )
                ],
            )
        )
    )
    return GraphowCLI(kernel, EscritorConsoleEmMemoria()), kernel


def test_cli_criar_e_listar_tasks_nominal() -> None:
    """Testa criação e listagem de tarefas via CLI."""
    cli, _ = _construir_cli_com_sessao()

    id_task = cli.criar_task("Implementar Parser", "sess-1", "david")
    assert id_task.startswith("task-")

    tarefas = cli.listar_tasks("main")
    assert len(tarefas) == 1
    assert tarefas[0].rotulo == "Implementar Parser"
    assert tarefas[0].status == "pendente"


def test_cli_montar_sumario_grafo_vazio_edge_case() -> None:
    """Caso de borda: sumário de um grafo sem nós nem arestas."""
    kernel = WriteKernel(InMemoryEventStore())
    cli = GraphowCLI(kernel, EscritorConsoleEmMemoria())

    sumario = cli.montar_sumario_grafo("main")
    assert "GRAFO GRAPHOW" in sumario
    assert "Nos (0):" in sumario
    assert "Arestas (0):" in sumario


def test_cli_listar_tasks_em_ramo_inexistente_edge_case() -> None:
    """Caso de borda: ramo sem eventos devolve coleção vazia, não erro."""
    cli, _ = _construir_cli_com_sessao()
    assert cli.listar_tasks("ramo-que-nunca-existiu") == ()


def test_cli_main_sem_argumentos_exibe_ajuda_edge_case() -> None:
    """Caso de borda: execução sem subcomando retorna 0 sem tocar no banco."""
    assert main([]) == 0


def test_descrever_localizacao_banco_alerta_pasta_sincronizada_edge_case() -> None:
    """Caso de borda: caminho em pasta de nuvem produz alerta explícito."""
    localizacao = LocalizacaoBanco(
        caminho=Path("C:/Users/alguem/OneDrive/Documentos/graphow/graphow.db"),
        origem=OrigemCaminhoBanco.ARGUMENTO_EXPLICITO,
        esta_em_pasta_sincronizada=True,
    )
    linhas = descrever_localizacao_banco(localizacao)
    assert any("AVISO" in linha for linha in linhas)
    assert any("migrar-banco" in linha for linha in linhas)


def test_descrever_localizacao_banco_sem_alerta_nominal() -> None:
    """Caminho fora de pastas sincronizadas não gera alerta."""
    localizacao = LocalizacaoBanco(
        caminho=Path("C:/Users/alguem/AppData/Local/graphow/graphow.db"),
        origem=OrigemCaminhoBanco.DIRETORIO_DADOS_USUARIO,
        esta_em_pasta_sincronizada=False,
    )
    linhas = descrever_localizacao_banco(localizacao)
    assert not any("AVISO" in linha for linha in linhas)
