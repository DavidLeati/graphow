"""Resolução do caminho do banco de eventos fora de pastas sincronizadas por nuvem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path

NOME_ARQUIVO_BANCO_PADRAO: str = "graphow.db"
NOME_PASTA_APLICACAO: str = "graphow"
VARIAVEL_CAMINHO_BANCO: str = "GRAPHOW_DB"

# Sincronizadores de nuvem replicam .db, -wal e -shm como arquivos independentes.
# Um checkpoint pendente no -wal que chegue dessincronizado do .db corrompe o log.
PASTAS_SINCRONIZADAS_CONHECIDAS: tuple[str, ...] = (
    "onedrive",
    "dropbox",
    "google drive",
    "googledrive",
    "icloud",
    "icloud drive",
    "nextcloud",
    "pcloud",
    "mega",
)


class OrigemCaminhoBanco(str, Enum):
    """De onde veio o caminho resolvido para o banco de eventos."""

    ARGUMENTO_EXPLICITO = "argumento_explicito"
    VARIAVEL_AMBIENTE = "variavel_ambiente"
    DIRETORIO_DADOS_USUARIO = "diretorio_dados_usuario"


@dataclass(frozen=True)
class LocalizacaoBanco:
    """Resultado imutável da resolução do caminho do banco de eventos."""

    caminho: Path
    origem: OrigemCaminhoBanco
    esta_em_pasta_sincronizada: bool

    @property
    def caminho_absoluto_texto(self) -> str:
        """Caminho em forma textual absoluta, pronto para o driver do SQLite."""
        return str(self.caminho)

    @property
    def diretorio_pai(self) -> Path:
        """Diretório que precisa existir antes de o banco ser aberto."""
        return self.caminho.parent


class ProvedorAmbiente(ABC):
    """Contrato de leitura do ambiente do sistema operacional."""

    @abstractmethod
    def obter_variavel(self, nome: str) -> str | None:
        """Lê uma variável de ambiente, ou None se não estiver definida."""
        raise NotImplementedError

    @abstractmethod
    def obter_diretorio_home(self) -> Path:
        """Retorna o diretório pessoal do usuário corrente."""
        raise NotImplementedError


class AmbienteSistemaOperacional(ProvedorAmbiente):
    """Adaptador concreto de leitura do ambiente real do processo."""

    def obter_variavel(self, nome: str) -> str | None:
        """Lê a variável diretamente de os.environ."""
        return os.environ.get(nome)

    def obter_diretorio_home(self) -> Path:
        """Resolve o diretório pessoal via pathlib."""
        return Path.home()


class AmbienteEmMemoria(ProvedorAmbiente):
    """Adaptador de ambiente controlado, para testes e simulações determinísticas."""

    def __init__(self, variaveis: dict[str, str], diretorio_home: Path) -> None:
        self._variaveis: dict[str, str] = dict(variaveis)
        self._diretorio_home: Path = diretorio_home

    def obter_variavel(self, nome: str) -> str | None:
        """Lê a variável do dicionário fornecido na construção."""
        return self._variaveis.get(nome)

    def obter_diretorio_home(self) -> Path:
        """Retorna o diretório pessoal fornecido na construção."""
        return self._diretorio_home


def caminho_esta_em_pasta_sincronizada(caminho: Path) -> bool:
    """Detecta se algum segmento do caminho pertence a um sincronizador de nuvem."""
    segmentos_normalizados = [parte.strip().lower() for parte in caminho.parts]
    return any(segmento in PASTAS_SINCRONIZADAS_CONHECIDAS for segmento in segmentos_normalizados)


class LocalizadorBancoEventos:
    """Resolve, sem efeitos colaterais, onde o banco de eventos deve residir."""

    def __init__(self, ambiente: ProvedorAmbiente | None = None) -> None:
        self._ambiente: ProvedorAmbiente = ambiente or AmbienteSistemaOperacional()

    def resolver(self, caminho_explicito: str | None = None) -> LocalizacaoBanco:
        """Consulta pura: precedência argumento > variável de ambiente > diretório de dados."""
        if caminho_explicito is not None:
            return self._montar_localizacao(Path(caminho_explicito), OrigemCaminhoBanco.ARGUMENTO_EXPLICITO)

        caminho_do_ambiente = self._ambiente.obter_variavel(VARIAVEL_CAMINHO_BANCO)
        if caminho_do_ambiente:
            return self._montar_localizacao(Path(caminho_do_ambiente), OrigemCaminhoBanco.VARIAVEL_AMBIENTE)

        caminho_padrao = self._obter_diretorio_dados_usuario() / NOME_ARQUIVO_BANCO_PADRAO
        return self._montar_localizacao(caminho_padrao, OrigemCaminhoBanco.DIRETORIO_DADOS_USUARIO)

    def _montar_localizacao(self, caminho: Path, origem: OrigemCaminhoBanco) -> LocalizacaoBanco:
        """Constrói o DTO imutável marcando o risco de sincronização em nuvem."""
        if self._eh_banco_apenas_em_memoria(caminho):
            return LocalizacaoBanco(caminho=caminho, origem=origem, esta_em_pasta_sincronizada=False)
        # Um caminho relativo precisa virar absoluto antes da deteccao: rodar a CLI
        # de dentro do OneDrive com --db graphow.db e justamente o caso arriscado.
        caminho_absoluto = Path(os.path.expandvars(str(caminho))).expanduser().resolve()
        return LocalizacaoBanco(
            caminho=caminho_absoluto,
            origem=origem,
            esta_em_pasta_sincronizada=caminho_esta_em_pasta_sincronizada(caminho_absoluto),
        )

    def _eh_banco_apenas_em_memoria(self, caminho: Path) -> bool:
        """Identifica o banco efêmero do SQLite, que não possui caminho em disco."""
        return str(caminho) == ":memory:"

    def _obter_diretorio_dados_usuario(self) -> Path:
        """Diretório de dados por plataforma, sempre fora de pastas sincronizadas."""
        local_app_data = self._ambiente.obter_variavel("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / NOME_PASTA_APLICACAO

        xdg_data_home = self._ambiente.obter_variavel("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / NOME_PASTA_APLICACAO

        return self._ambiente.obter_diretorio_home() / ".local" / "share" / NOME_PASTA_APLICACAO


class PreparadorDiretorioBanco:
    """Comando de infraestrutura que garante a existência do diretório do banco."""

    def garantir_diretorio(self, localizacao: LocalizacaoBanco) -> None:
        """Cria o diretório pai do banco, se ainda não existir."""
        if str(localizacao.caminho) == ":memory:":
            return
        localizacao.diretorio_pai.mkdir(parents=True, exist_ok=True)
