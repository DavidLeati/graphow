"""Migração segura do banco de eventos entre localizações, preservando o WAL."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from graphow.core.exceptions import GraphowError


@dataclass(frozen=True)
class PlanoMigracao:
    """Diagnóstico imutável do que uma migração faria, sem executá-la."""

    caminho_origem: Path
    caminho_destino: Path
    eventos_na_origem: int
    destino_ja_existe: bool
    deve_migrar: bool
    motivo: str


class AcessoBancoSQLite(ABC):
    """Contrato de operações de infraestrutura sobre arquivos SQLite."""

    @abstractmethod
    def arquivo_existe(self, caminho: Path) -> bool:
        """Informa se o arquivo de banco está presente no sistema de arquivos."""
        raise NotImplementedError

    @abstractmethod
    def contar_eventos(self, caminho: Path) -> int:
        """Conta os eventos persistidos, incluindo os que ainda vivem apenas no WAL."""
        raise NotImplementedError

    @abstractmethod
    def copiar_com_checkpoint(self, caminho_origem: Path, caminho_destino: Path) -> None:
        """Consolida o WAL e replica o banco íntegro no destino."""
        raise NotImplementedError


class AcessoBancoSQLitePadrao(AcessoBancoSQLite):
    """Adaptador concreto sobre o driver sqlite3 da biblioteca padrão."""

    def arquivo_existe(self, caminho: Path) -> bool:
        """Verifica presença do arquivo principal do banco."""
        return caminho.is_file()

    def contar_eventos(self, caminho: Path) -> int:
        """Abre o banco em modo leitura e conta a tabela de eventos."""
        conexao = sqlite3.connect(str(caminho))
        try:
            return self._ler_total_eventos(conexao, caminho)
        finally:
            conexao.close()

    def _ler_total_eventos(self, conexao: sqlite3.Connection, caminho: Path) -> int:
        """Executa a contagem tratando a ausência da tabela como banco vazio."""
        try:
            linha = conexao.execute("SELECT COUNT(*) FROM eventos;").fetchone()
        except sqlite3.OperationalError as erro:
            if "no such table" in str(erro):
                return 0
            raise GraphowError(
                f"Falha ao inspecionar o banco de eventos: {erro}",
                {"caminho": str(caminho)},
            ) from erro
        return int(linha[0]) if linha else 0

    def copiar_com_checkpoint(self, caminho_origem: Path, caminho_destino: Path) -> None:
        """Consolida o WAL na origem e usa a API de backup do SQLite para replicar."""
        conexao_origem = sqlite3.connect(str(caminho_origem))
        conexao_destino = sqlite3.connect(str(caminho_destino))
        try:
            conexao_origem.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conexao_origem.backup(conexao_destino)
        except sqlite3.Error as erro:
            raise GraphowError(
                f"Falha ao copiar o banco de eventos: {erro}",
                {"origem": str(caminho_origem), "destino": str(caminho_destino)},
            ) from erro
        finally:
            conexao_origem.close()
            conexao_destino.close()


class AnalisadorMigracaoBanco:
    """Consulta pura que decide se e por que uma migração deve ocorrer."""

    def __init__(self, acesso_banco: AcessoBancoSQLite | None = None) -> None:
        self._acesso_banco: AcessoBancoSQLite = acesso_banco or AcessoBancoSQLitePadrao()

    def planejar(self, caminho_origem: Path, caminho_destino: Path) -> PlanoMigracao:
        """Monta o plano de migração sem alterar nada em disco."""
        if not self._acesso_banco.arquivo_existe(caminho_origem):
            return self._plano_negativo(caminho_origem, caminho_destino, "Origem inexistente")

        destino_existe = self._acesso_banco.arquivo_existe(caminho_destino)
        if destino_existe:
            return self._plano_negativo(caminho_origem, caminho_destino, "Destino já possui um banco")

        eventos = self._acesso_banco.contar_eventos(caminho_origem)
        return PlanoMigracao(
            caminho_origem=caminho_origem,
            caminho_destino=caminho_destino,
            eventos_na_origem=eventos,
            destino_ja_existe=False,
            deve_migrar=True,
            motivo=f"{eventos} eventos a preservar",
        )

    def _plano_negativo(self, origem: Path, destino: Path, motivo: str) -> PlanoMigracao:
        """Constrói um plano que indica explicitamente a ausência de migração."""
        return PlanoMigracao(
            caminho_origem=origem,
            caminho_destino=destino,
            eventos_na_origem=0,
            destino_ja_existe=self._acesso_banco.arquivo_existe(destino),
            deve_migrar=False,
            motivo=motivo,
        )


class MigradorBancoEventos:
    """Comando que executa um plano de migração previamente calculado."""

    def __init__(self, acesso_banco: AcessoBancoSQLite | None = None) -> None:
        self._acesso_banco: AcessoBancoSQLite = acesso_banco or AcessoBancoSQLitePadrao()

    def executar(self, plano: PlanoMigracao) -> None:
        """Replica o banco no destino. A origem permanece intacta como backup."""
        if not plano.deve_migrar:
            return
        self._acesso_banco.copiar_com_checkpoint(plano.caminho_origem, plano.caminho_destino)
