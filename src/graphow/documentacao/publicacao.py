"""Publicação dos documentos gerados, com escrita atrás de interface injetável."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from graphow.documentacao.modelo import CatalogoRepositorio
from graphow.documentacao.renderizador_indice import RenderizadorIndice
from graphow.documentacao.renderizador_setor import RenderizadorSetor

NOME_ARQUIVO_INDICE: str = "INDEX.md"
NOME_DIRETORIO_SETORES: str = "setores"


@dataclass(frozen=True)
class DocumentoGerado:
    """Par imutável de caminho relativo e conteúdo pronto para gravação."""

    caminho_relativo: str
    conteudo: str


@dataclass(frozen=True)
class ResultadoPublicacao:
    """Resumo do que a geração produziu, para relato na linha de comando."""

    documentos_escritos: int
    documentos_removidos: tuple[str, ...]
    bytes_totais: int


class EscritorDocumentacao(ABC):
    """Contrato de gravação dos documentos gerados."""

    @abstractmethod
    def escrever(self, documento: DocumentoGerado) -> None:
        """Grava um documento, criando os diretórios necessários."""
        raise NotImplementedError

    @abstractmethod
    def listar_dossies_existentes(self) -> tuple[str, ...]:
        """Enumera os dossiês já presentes no destino."""
        raise NotImplementedError

    @abstractmethod
    def remover(self, caminho_relativo: str) -> None:
        """Apaga um documento que deixou de ser gerado."""
        raise NotImplementedError


class EscritorDocumentacaoEmDisco(EscritorDocumentacao):
    """Adaptador concreto que grava sob o diretório `docs/`."""

    def __init__(self, raiz_documentacao: Path) -> None:
        self._raiz: Path = raiz_documentacao

    def escrever(self, documento: DocumentoGerado) -> None:
        """Grava o documento em UTF-8 com quebras de linha normalizadas."""
        destino = self._raiz / documento.caminho_relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(documento.conteudo, encoding="utf-8", newline="\n")

    def listar_dossies_existentes(self) -> tuple[str, ...]:
        """Lista os arquivos Markdown presentes no diretório de setores."""
        diretorio = self._raiz / NOME_DIRETORIO_SETORES
        if not diretorio.is_dir():
            return ()
        return tuple(
            f"{NOME_DIRETORIO_SETORES}/{arquivo.name}" for arquivo in sorted(diretorio.glob("*.md"))
        )

    def remover(self, caminho_relativo: str) -> None:
        """Apaga o arquivo, se ele ainda existir."""
        (self._raiz / caminho_relativo).unlink(missing_ok=True)


class EscritorDocumentacaoEmMemoria(EscritorDocumentacao):
    """Escritor determinístico que acumula os documentos, para testes."""

    def __init__(self, dossies_existentes: tuple[str, ...] = ()) -> None:
        self._dossies_existentes: tuple[str, ...] = dossies_existentes
        self.documentos: dict[str, str] = {}
        self.removidos: list[str] = []

    def escrever(self, documento: DocumentoGerado) -> None:
        """Acumula o conteúdo em memória."""
        self.documentos[documento.caminho_relativo] = documento.conteudo

    def listar_dossies_existentes(self) -> tuple[str, ...]:
        """Devolve os dossiês declarados na construção."""
        return self._dossies_existentes

    def remover(self, caminho_relativo: str) -> None:
        """Registra a remoção solicitada."""
        self.removidos.append(caminho_relativo)


class GeradorDocumentacao:
    """Renderiza o catálogo e publica os documentos resultantes."""

    def __init__(self, escritor: EscritorDocumentacao) -> None:
        self._escritor: EscritorDocumentacao = escritor
        self._renderizador_indice: RenderizadorIndice = RenderizadorIndice()
        self._renderizador_setor: RenderizadorSetor = RenderizadorSetor()

    def montar_documentos(self, catalogo: CatalogoRepositorio) -> tuple[DocumentoGerado, ...]:
        """Consulta pura: renderiza índice e dossiês sem gravar nada."""
        indice = DocumentoGerado(
            caminho_relativo=NOME_ARQUIVO_INDICE,
            conteudo=self._renderizador_indice.renderizar(catalogo),
        )
        dossies = tuple(
            DocumentoGerado(
                caminho_relativo=f"{NOME_DIRETORIO_SETORES}/{setor.nome_arquivo}",
                conteudo=self._renderizador_setor.renderizar(setor),
            )
            for setor in catalogo.setores
        )
        return (indice,) + dossies

    def publicar(self, catalogo: CatalogoRepositorio) -> ResultadoPublicacao:
        """Comando: grava os documentos e remove dossiês de alas extintas."""
        documentos = self.montar_documentos(catalogo)
        for documento in documentos:
            self._escritor.escrever(documento)
        removidos = self._remover_dossies_obsoletos(documentos)
        return ResultadoPublicacao(
            documentos_escritos=len(documentos),
            documentos_removidos=removidos,
            bytes_totais=sum(len(documento.conteudo.encode("utf-8")) for documento in documentos),
        )

    def _remover_dossies_obsoletos(self, documentos: tuple[DocumentoGerado, ...]) -> tuple[str, ...]:
        """Apaga dossiês que sobraram de alas que já não existem."""
        gerados = {documento.caminho_relativo for documento in documentos}
        obsoletos = tuple(
            caminho for caminho in self._escritor.listar_dossies_existentes() if caminho not in gerados
        )
        for caminho in obsoletos:
            self._escritor.remover(caminho)
        return obsoletos
