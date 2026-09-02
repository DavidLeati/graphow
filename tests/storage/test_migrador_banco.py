"""Testes unitários para o planejamento e a execução da migração do banco."""

from pathlib import Path

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor
from graphow.storage.migrador_banco import (
    AcessoBancoSQLite,
    AcessoBancoSQLitePadrao,
    AnalisadorMigracaoBanco,
    MigradorBancoEventos,
)
from graphow.storage.sqlite_store import SQLiteEventStore


class AcessoBancoFalso(AcessoBancoSQLite):
    """Adaptador de banco controlado, sem tocar no sistema de arquivos."""

    def __init__(self, arquivos_existentes: set[str], total_eventos: int = 0) -> None:
        self._arquivos_existentes: frozenset[str] = frozenset(
            Path(caminho).as_posix() for caminho in arquivos_existentes
        )
        self._total_eventos: int = total_eventos
        self.copias_realizadas: list[tuple[str, str]] = []

    def arquivo_existe(self, caminho: Path) -> bool:
        """Consulta a lista de arquivos declarada na construção."""
        return caminho.as_posix() in self._arquivos_existentes

    def contar_eventos(self, caminho: Path) -> int:
        """Devolve a contagem fixa configurada."""
        return self._total_eventos

    def copiar_com_checkpoint(self, caminho_origem: Path, caminho_destino: Path) -> None:
        """Registra a cópia solicitada em vez de executá-la."""
        self.copias_realizadas.append((str(caminho_origem), str(caminho_destino)))


def _gravar_evento(store: SQLiteEventStore, seq: int) -> None:
    """Persiste um evento mínimo no repositório informado."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor="david",
        papel=PapelAutor.HUMANO,
        tipo_evento=TipoEvento.NO_CRIADO,
        payload={"id": f"n{seq}", "tipo": "Task", "rotulo": f"Tarefa {seq}"},
        origem=OrigemEvento.HUMANO,
    )
    store.append_evento(EventoLog.criar(dados))


def test_plano_indica_migracao_quando_origem_tem_eventos_nominal() -> None:
    """Origem existente e destino livre produzem um plano positivo."""
    acesso = AcessoBancoFalso({"/antigo/graphow.db"}, total_eventos=263)
    plano = AnalisadorMigracaoBanco(acesso).planejar(Path("/antigo/graphow.db"), Path("/novo/graphow.db"))
    assert plano.deve_migrar is True
    assert plano.eventos_na_origem == 263
    assert "263" in plano.motivo


def test_plano_recusa_quando_origem_nao_existe_edge_case() -> None:
    """Caso de borda: origem inexistente nunca gera migração."""
    plano = AnalisadorMigracaoBanco(AcessoBancoFalso(set())).planejar(Path("/nada.db"), Path("/novo.db"))
    assert plano.deve_migrar is False
    assert plano.motivo == "Origem inexistente"


def test_plano_recusa_quando_destino_ja_possui_banco_edge_case() -> None:
    """Caso de borda: destino ocupado impede sobrescrita silenciosa do log."""
    acesso = AcessoBancoFalso({"/antigo.db", "/novo.db"}, total_eventos=10)
    plano = AnalisadorMigracaoBanco(acesso).planejar(Path("/antigo.db"), Path("/novo.db"))
    assert plano.deve_migrar is False
    assert plano.destino_ja_existe is True


def test_migrador_nao_copia_plano_negativo_edge_case() -> None:
    """Caso de borda: executar um plano negativo é uma operação sem efeito."""
    acesso = AcessoBancoFalso(set())
    plano = AnalisadorMigracaoBanco(acesso).planejar(Path("/nada.db"), Path("/novo.db"))
    MigradorBancoEventos(acesso).executar(plano)
    assert acesso.copias_realizadas == []


def test_migracao_real_preserva_eventos_que_estavam_no_wal(tmp_path: Path) -> None:
    """A cópia consolida o WAL: o destino enxerga todos os eventos da origem."""
    origem = tmp_path / "origem.db"
    destino = tmp_path / "destino.db"
    store = SQLiteEventStore(str(origem))
    for seq in range(1, 6):
        _gravar_evento(store, seq)

    plano = AnalisadorMigracaoBanco().planejar(origem, destino)
    assert plano.eventos_na_origem == 5
    MigradorBancoEventos().executar(plano)
    store.fechar()

    assert AcessoBancoSQLitePadrao().contar_eventos(destino) == 5


def test_contagem_de_banco_sem_tabela_retorna_zero_edge_case(tmp_path: Path) -> None:
    """Caso de borda: arquivo SQLite sem a tabela de eventos conta como vazio."""
    import sqlite3

    caminho = tmp_path / "vazio.db"
    conexao = sqlite3.connect(str(caminho))
    conexao.execute("CREATE TABLE outra_coisa (id TEXT);")
    conexao.close()

    assert AcessoBancoSQLitePadrao().contar_eventos(caminho) == 0
