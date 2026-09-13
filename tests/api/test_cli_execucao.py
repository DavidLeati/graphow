"""Testes de integração da execução de subcomandos da linha de comando."""

import io
from pathlib import Path

import pytest

from graphow.api.cli_execucao import CODIGO_SUCESSO, ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos
from graphow.storage.sqlite_store import SQLiteEventStore


def _executar(argumentos: list[str], diretorio_dados: Path) -> tuple[int, EscritorConsoleEmMemoria]:
    """Executa um subcomando com o diretório de dados apontado para um caminho temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(diretorio_dados)}, diretorio_dados)
    executor = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente))
    return executor.executar(construir_parser().parse_args(argumentos)), console


def test_banco_info_mostra_caminho_resolvido_nominal(tmp_path: Path) -> None:
    """O comando de diagnóstico revela onde o banco será aberto."""
    codigo, console = _executar(["banco-info"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("graphow.db" in linha for linha in console.linhas)
    assert not any("AVISO" in linha for linha in console.linhas)


def test_banco_info_alerta_quando_caminho_esta_no_onedrive_edge_case(tmp_path: Path) -> None:
    """Caso de borda: caminho explícito em pasta de nuvem dispara o alerta."""
    caminho_arriscado = str(tmp_path / "OneDrive" / "Documentos" / "graphow.db")
    codigo, console = _executar(["--db", caminho_arriscado, "banco-info"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("AVISO" in linha for linha in console.linhas)


def test_init_cria_o_banco_no_diretorio_de_dados_nominal(tmp_path: Path) -> None:
    """O comando de inicialização cria diretório e arquivo do banco."""
    codigo, console = _executar(["init"], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert (tmp_path / "graphow" / "graphow.db").is_file()
    assert any("inicializado" in linha for linha in console.linhas)


def test_migracao_copia_eventos_do_banco_antigo_nominal(tmp_path: Path) -> None:
    """A migração preserva os eventos e mantém a origem intacta."""
    origem = tmp_path / "antigo" / "graphow.db"
    origem.parent.mkdir(parents=True)
    with SQLiteEventStore(str(origem)) as store:
        _popular(store)

    codigo, console = _executar(["migrar-banco", "--origem", str(origem)], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("Migrados 3 eventos" in linha for linha in console.linhas)
    assert origem.is_file()
    assert (tmp_path / "graphow" / "graphow.db").is_file()


def test_migracao_nao_sobrescreve_banco_existente_edge_case(tmp_path: Path) -> None:
    """Caso de borda: destino já povoado não é sobrescrito pela migração."""
    _executar(["init"], tmp_path)
    origem = tmp_path / "antigo.db"
    with SQLiteEventStore(str(origem)) as store:
        _popular(store)

    codigo, console = _executar(["migrar-banco", "--origem", str(origem)], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("nao realizada" in linha for linha in console.linhas)


def test_migracao_de_origem_inexistente_nao_falha_edge_case(tmp_path: Path) -> None:
    """Caso de borda: origem ausente devolve mensagem clara em vez de exceção."""
    codigo, console = _executar(["migrar-banco", "--origem", str(tmp_path / "nada.db")], tmp_path)
    assert codigo == CODIGO_SUCESSO
    assert any("Origem inexistente" in linha for linha in console.linhas)


def test_task_create_e_task_list_persistem_entre_execucoes_nominal(tmp_path: Path) -> None:
    """Duas execuções distintas compartilham o mesmo banco resolvido."""
    _criar_sessao_no_banco(tmp_path)
    codigo_criacao, console_criacao = _executar(
        ["task-create", "--titulo", "Escrever documentacao", "--sessao", "sess-1"], tmp_path
    )
    assert codigo_criacao == CODIGO_SUCESSO
    assert any("Task criada com sucesso" in linha for linha in console_criacao.linhas)

    _, console_listagem = _executar(["task-list"], tmp_path)
    assert any("Escrever documentacao" in linha for linha in console_listagem.linhas)


def _criar_sessao_no_banco(diretorio_dados: Path) -> None:
    """Prepara uma Sessão no banco resolvido, para as tarefas terem onde nascer."""
    from graphow.core.types import PapelAutor, TipoNo
    from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
    from graphow.kernel.write_kernel import WriteKernel

    caminho = diretorio_dados / "graphow" / "graphow.db"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteEventStore(str(caminho)) as store:
        WriteKernel(store).submeter_patch(
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


def _executar_com_payload(
    argumentos: list[str],
    diretorio_dados: Path,
    payload: str,
) -> tuple[int, EscritorConsoleEmMemoria]:
    """Executa um subcomando com o JSON do hook posto na entrada padrão."""
    with pytest.MonkeyPatch.context() as ambiente:
        ambiente.setattr("sys.stdin", io.StringIO(payload))
        return _executar(argumentos, diretorio_dados)


def test_harness_le_a_sessao_do_payload_do_hook_nominal(tmp_path: Path) -> None:
    """O id da sessão chega no JSON da entrada padrão, não em variável de ambiente."""
    codigo, console = _executar_com_payload(
        ["harness", "--fase", "inicio", "--entrada-hook"],
        tmp_path,
        '{"session_id": "sess-do-hook", "model": "claude-opus-5", "source": "startup"}',
    )

    assert codigo == CODIGO_SUCESSO
    assert any("run-sess-do-hook" in linha for linha in console.linhas)


def test_harness_sem_sessao_no_payload_recusa_em_vez_de_estourar_edge_case(tmp_path: Path) -> None:
    """Caso de borda: era aqui que o comando terminava em IndexError no SchemaGate."""
    codigo, console = _executar_com_payload(
        ["harness", "--fase", "inicio", "--entrada-hook", "--setor", "setor-1"], tmp_path, "{}"
    )

    assert codigo == 1
    assert any("session_id" in linha for linha in console.linhas)


def test_harness_com_payload_ilegivel_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: payload quebrado é recusa explícita, não traceback."""
    codigo, _ = _executar_com_payload(
        ["harness", "--fase", "fim", "--entrada-hook"], tmp_path, "nao e json"
    )

    assert codigo == 1


def _popular(store: SQLiteEventStore) -> None:
    """Grava três eventos mínimos no repositório informado."""
    from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
    from graphow.core.types import OrigemEvento, PapelAutor

    for seq in range(1, 4):
        store.append_evento(
            EventoLog.criar(
                DadosCriacaoEvento(
                    seq=seq,
                    autor="david",
                    papel=PapelAutor.HUMANO,
                    tipo_evento=TipoEvento.NO_CRIADO,
                    payload={"id": f"n{seq}", "tipo": "Note", "rotulo": f"Nota {seq}"},
                    origem=OrigemEvento.HUMANO,
                )
            )
        )
