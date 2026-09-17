"""Publicação do acervo, com escrita atrás de interface injetável e conferência de deriva.

O grafo é a fonte; o acervo é leitura, regenerável do zero. `conferir` compara
o que está no diretório com o que o grafo produziria agora e nomeia cada
arquivo que diverge, falta ou sobra: uma nota escrita à mão no acervo é deriva,
porque ninguém a encontraria na vista do agente.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from graphow.notas.modelo import NotaDeAprendizado
from graphow.notas.renderizador import NOME_DO_INDICE, renderizar_indice, renderizar_nota

EXTENSAO_DAS_NOTAS: str = "*.md"


@dataclass(frozen=True)
class DocumentoDeNota:
    """Par imutável de caminho relativo e conteúdo pronto para gravação."""

    caminho_relativo: str
    conteudo: str


@dataclass(frozen=True)
class ResultadoDoAcervo:
    """Resumo do que a publicação produziu, para relato na linha de comando."""

    documentos_escritos: int
    documentos_removidos: tuple[str, ...]


class EscritorDeAcervo(ABC):
    """Contrato de leitura e gravação do diretório do acervo."""

    @abstractmethod
    def escrever(self, documento: DocumentoDeNota) -> None:
        """Grava um documento, criando o diretório se preciso."""
        raise NotImplementedError

    @abstractmethod
    def ler(self, caminho_relativo: str) -> str | None:
        """Conteúdo atual do documento, ou None quando ele não existe."""
        raise NotImplementedError

    @abstractmethod
    def listar_existentes(self) -> tuple[str, ...]:
        """Documentos Markdown presentes no acervo, em ordem estável."""
        raise NotImplementedError

    @abstractmethod
    def remover(self, caminho_relativo: str) -> None:
        """Apaga um documento que deixou de ser gerado."""
        raise NotImplementedError


class EscritorDeAcervoEmDisco(EscritorDeAcervo):
    """Adaptador concreto sobre um diretório do sistema de arquivos."""

    def __init__(self, raiz: Path) -> None:
        self._raiz: Path = raiz

    def escrever(self, documento: DocumentoDeNota) -> None:
        """Grava em UTF-8 com quebras de linha normalizadas."""
        destino = self._raiz / documento.caminho_relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(documento.conteudo, encoding="utf-8", newline="\n")

    def ler(self, caminho_relativo: str) -> str | None:
        """Lê o arquivo, se existir."""
        caminho = self._raiz / caminho_relativo
        if not caminho.is_file():
            return None
        return caminho.read_text(encoding="utf-8")

    def listar_existentes(self) -> tuple[str, ...]:
        """Os arquivos Markdown na raiz do acervo."""
        if not self._raiz.is_dir():
            return ()
        return tuple(arquivo.name for arquivo in sorted(self._raiz.glob(EXTENSAO_DAS_NOTAS)))

    def remover(self, caminho_relativo: str) -> None:
        """Apaga o arquivo, se ainda existir."""
        (self._raiz / caminho_relativo).unlink(missing_ok=True)


class EscritorDeAcervoEmMemoria(EscritorDeAcervo):
    """Escritor determinístico que guarda os documentos num dicionário, para testes."""

    def __init__(self, existentes: dict[str, str] | None = None) -> None:
        self.documentos: dict[str, str] = dict(existentes or {})
        self.removidos: list[str] = []

    def escrever(self, documento: DocumentoDeNota) -> None:
        """Guarda o conteúdo em memória."""
        self.documentos[documento.caminho_relativo] = documento.conteudo

    def ler(self, caminho_relativo: str) -> str | None:
        """Conteúdo guardado, ou None."""
        return self.documentos.get(caminho_relativo)

    def listar_existentes(self) -> tuple[str, ...]:
        """Os caminhos guardados, em ordem estável."""
        return tuple(sorted(self.documentos))

    def remover(self, caminho_relativo: str) -> None:
        """Registra e aplica a remoção."""
        self.removidos.append(caminho_relativo)
        self.documentos.pop(caminho_relativo, None)


class GeradorDeAcervo:
    """Renderiza as notas e publica ou confere o diretório do acervo."""

    def __init__(self, escritor: EscritorDeAcervo) -> None:
        self._escritor: EscritorDeAcervo = escritor

    def montar_documentos(self, notas: Sequence[NotaDeAprendizado]) -> tuple[DocumentoDeNota, ...]:
        """Consulta pura: o índice e uma nota por aprendizado, sem gravar nada."""
        indice = DocumentoDeNota(caminho_relativo=NOME_DO_INDICE, conteudo=renderizar_indice(notas))
        return (indice,) + tuple(
            DocumentoDeNota(caminho_relativo=nota.nome_arquivo, conteudo=renderizar_nota(nota)) for nota in notas
        )

    def publicar(self, notas: Sequence[NotaDeAprendizado]) -> ResultadoDoAcervo:
        """Comando: grava os documentos e remove o que sobrou de gerações anteriores."""
        documentos = self.montar_documentos(notas)
        for documento in documentos:
            self._escritor.escrever(documento)
        gerados = {documento.caminho_relativo for documento in documentos}
        sobras = tuple(caminho for caminho in self._escritor.listar_existentes() if caminho not in gerados)
        for caminho in sobras:
            self._escritor.remover(caminho)
        return ResultadoDoAcervo(documentos_escritos=len(documentos), documentos_removidos=sobras)

    def conferir(self, notas: Sequence[NotaDeAprendizado]) -> tuple[str, ...]:
        """Consulta pura: os documentos que divergem, faltam ou sobram no acervo."""
        documentos = self.montar_documentos(notas)
        gerados = {documento.caminho_relativo for documento in documentos}
        divergentes = [
            documento.caminho_relativo
            for documento in documentos
            if self._escritor.ler(documento.caminho_relativo) != documento.conteudo
        ]
        sobras = [caminho for caminho in self._escritor.listar_existentes() if caminho not in gerados]
        return tuple(sorted(divergentes + sobras))
