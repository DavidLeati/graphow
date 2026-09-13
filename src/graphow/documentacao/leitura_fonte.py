"""Acesso ao código-fonte do repositório, atrás de interface injetável."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from graphow.core.exceptions import GraphowError

ARQUIVO_DE_PACOTE: str = "__init__.py"


@dataclass(frozen=True)
class ArquivoFonte:
    """Conteúdo de um módulo Python junto do caminho pelo qual ele é referenciado."""

    caminho_relativo: str
    conteudo: str

    @property
    def nome_modulo(self) -> str:
        """Caminho de importação do módulo, derivado do caminho no disco."""
        sem_extensao = self.caminho_relativo.removesuffix(".py")
        partes = sem_extensao.replace("\\", "/").split("/")
        if partes[-1] == "__init__":
            partes = partes[:-1]
        return ".".join(("graphow",) + tuple(partes))

    @property
    def total_linhas(self) -> int:
        """Quantidade de linhas do arquivo."""
        return len(self.conteudo.splitlines())


class LeitorCodigoFonte(ABC):
    """Contrato de leitura dos módulos de um pacote do projeto."""

    @abstractmethod
    def listar_pacotes(self) -> tuple[str, ...]:
        """Enumera os pacotes de primeiro nível sob a raiz do código."""
        raise NotImplementedError

    @abstractmethod
    def ler_modulos(self, pacote: str) -> tuple[ArquivoFonte, ...]:
        """Lê todos os módulos de um pacote, em ordem estável."""
        raise NotImplementedError


class LeitorCodigoFonteEmDisco(LeitorCodigoFonte):
    """Adaptador concreto sobre o sistema de arquivos do repositório."""

    def __init__(self, raiz_codigo: Path) -> None:
        self._raiz_codigo: Path = raiz_codigo

    def listar_pacotes(self) -> tuple[str, ...]:
        """Enumera os diretórios que contêm um __init__.py."""
        if not self._raiz_codigo.is_dir():
            raise GraphowError(
                "Raiz do codigo-fonte inexistente", {"caminho": str(self._raiz_codigo)}
            )
        candidatos = (item for item in sorted(self._raiz_codigo.iterdir()) if item.is_dir())
        return tuple(item.name for item in candidatos if (item / ARQUIVO_DE_PACOTE).is_file())

    def ler_modulos(self, pacote: str) -> tuple[ArquivoFonte, ...]:
        """Lê os módulos do pacote ordenados por caminho, para saída determinística."""
        diretorio = self._raiz_codigo / pacote
        arquivos = sorted(diretorio.rglob("*.py"), key=lambda caminho: caminho.as_posix())
        return tuple(self._ler_arquivo(caminho) for caminho in arquivos)

    def _ler_arquivo(self, caminho: Path) -> ArquivoFonte:
        """Converte um caminho absoluto no DTO de arquivo-fonte."""
        return ArquivoFonte(
            caminho_relativo=caminho.relative_to(self._raiz_codigo).as_posix(),
            conteudo=caminho.read_text(encoding="utf-8"),
        )


class LeitorCodigoFonteEmMemoria(LeitorCodigoFonte):
    """Leitor determinístico alimentado por um dicionário, para testes."""

    def __init__(self, modulos_por_pacote: dict[str, tuple[ArquivoFonte, ...]]) -> None:
        self._modulos_por_pacote: dict[str, tuple[ArquivoFonte, ...]] = dict(modulos_por_pacote)

    def listar_pacotes(self) -> tuple[str, ...]:
        """Enumera os pacotes fornecidos na construção."""
        return tuple(sorted(self._modulos_por_pacote))

    def ler_modulos(self, pacote: str) -> tuple[ArquivoFonte, ...]:
        """Devolve os módulos do pacote informado."""
        return self._modulos_por_pacote.get(pacote, ())
