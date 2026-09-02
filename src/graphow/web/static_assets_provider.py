"""Provedor seguro de arquivos estáticos para a Single-Page Application do Graphow."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecursoEstatico:
    """Representação imutável de um asset estático lido do disco."""

    conteudo: bytes
    tipo_conteudo: str
    status_code: int = 200


class StaticAssetsProvider:
    """Localiza, valida segurança de path traversal e serve assets estáticos da interface web."""

    MIME_MAPA: dict[str, str] = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8",
        ".ico": "image/x-icon",
        ".png": "image/png",
    }

    def __init__(self, diretorio_raiz: Path | None = None) -> None:
        if diretorio_raiz is not None:
            self._raiz: Path = diretorio_raiz.resolve()
        else:
            self._raiz = (Path(__file__).parent / "static").resolve()

    def obter_recurso(self, caminho_relativo: str) -> RecursoEstatico:
        """Resolve e carrega o arquivo estático com proteção estrita contra Directory Traversal."""
        caminho_limpo = self._sanitizar_caminho(caminho_relativo)
        caminho_completo = (self._raiz / caminho_limpo).resolve()
        if not self._pertence_a_raiz(caminho_completo):
            return RecursoEstatico(conteudo=b"403 Proibido - Tentativa de Path Traversal", tipo_conteudo="text/plain", status_code=403)
        if not caminho_completo.is_file():
            return RecursoEstatico(conteudo=b"404 Recurso Nao Encontrado", tipo_conteudo="text/plain", status_code=404)
        extensao = caminho_completo.suffix.lower()
        tipo_mime = self.MIME_MAPA.get(extensao, "application/octet-stream")
        conteudo = caminho_completo.read_bytes()
        return RecursoEstatico(conteudo=conteudo, tipo_conteudo=tipo_mime, status_code=200)

    def _sanitizar_caminho(self, caminho_relativo: str) -> str:
        """Limpa barras e rota default index.html."""
        limpo = caminho_relativo.lstrip("/")
        if not limpo or limpo == "":
            return "index.html"
        return limpo

    def _pertence_a_raiz(self, caminho_alvo: Path) -> bool:
        """Verifica se o caminho resolvido está confinado dentro da pasta de assets."""
        try:
            caminho_alvo.relative_to(self._raiz)
            return True
        except ValueError:
            return False
