"""O cruzamento puro entre o que o ramo base ganhou e o que o Goal toca.

Duas migrations com números diferentes no mesmo diretório não dão conflito no
merge, e é essa a colisão que custou duas horas num goal real: o git junta os
dois arquivos, e a quebra aparece depois, na ordem das migrations. Por isso a
colisão não é só o mesmo arquivo. É um arquivo do ramo base que casa com um
glob de `caminhos_de_colisao` e está no mesmo diretório de um caminho do Goal
que casa com o mesmo glob; o mesmo arquivo é o caso particular disso.

Nada aqui roda git nem lê o grafo, para o cruzamento se testar sozinho.
"""

from collections.abc import Iterable
from dataclasses import dataclass
import posixpath
import re

# `**/` casa com zero ou mais diretórios, `**` com qualquer coisa, `*` e `?`
# não atravessam `/`. O resto do glob é literal.
TOKENS_DE_GLOB: re.Pattern[str] = re.compile(r"\*\*/|\*\*|\*|\?|[^*?]+")
TRADUCAO_DE_CURINGAS: dict[str, str] = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*", "?": "[^/]"}
SEPARADOR_DE_REMOTO: str = "/"


@dataclass(frozen=True, order=True)
class Colisao:
    """Um arquivo que o ramo base ganhou e o caminho do Goal com que ele colide."""

    arquivo_da_base: str
    caminho_do_goal: str

    def formatar(self) -> str:
        """A linha que o comando imprime: `<arquivo do ramo base> x <caminho do goal>`."""
        return f"{self.arquivo_da_base} x {self.caminho_do_goal}"


def normalizar_caminho(caminho: str) -> str:
    """O caminho relativo à raiz do repositório como o git o escreve: barra normal e sem `./` na frente.

    O `arquivos_alvo` é escrito à mão pelo condutor, às vezes com a barra do
    Windows, e o git sempre devolve a barra normal.
    """
    limpo = caminho.strip().replace("\\", "/")
    while limpo.startswith("./"):
        limpo = limpo[2:]
    return limpo


def casa_glob(caminho: str, glob: str) -> bool:
    """O caminho inteiro casa com o glob."""
    traduzido = "".join(TRADUCAO_DE_CURINGAS.get(token, re.escape(token)) for token in TOKENS_DE_GLOB.findall(glob))
    return re.fullmatch(traduzido, caminho) is not None


def nos_caminhos_de_colisao(arquivos: Iterable[str], globs: Iterable[str]) -> tuple[str, ...]:
    """Os arquivos que casam com algum dos globs, normalizados e em ordem."""
    padroes = tuple(glob for glob in globs if glob.strip())
    normalizados = {normalizar_caminho(arquivo) for arquivo in arquivos if arquivo.strip()}
    return tuple(sorted(arquivo for arquivo in normalizados if any(casa_glob(arquivo, glob) for glob in padroes)))


def cruzar_colisoes(
    arquivos_da_base: Iterable[str],
    caminhos_do_goal: Iterable[str],
    globs: Iterable[str],
) -> tuple[Colisao, ...]:
    """Cada par que colide, uma vez só e em ordem."""
    padroes = tuple(dict.fromkeys(normalizar_caminho(glob) for glob in globs if glob.strip()))
    base = sorted({normalizar_caminho(arquivo) for arquivo in arquivos_da_base if arquivo.strip()})
    goal = sorted({normalizar_caminho(caminho) for caminho in caminhos_do_goal if caminho.strip()})
    return tuple(sorted({
        Colisao(arquivo, caminho)
        for arquivo in base
        for caminho in goal
        if any(_colide(arquivo, caminho, glob) for glob in padroes)
    }))


def _colide(arquivo: str, caminho: str, glob: str) -> bool:
    """Os dois casam com o glob e dividem o diretório; o mesmo arquivo divide também."""
    mesmo_diretorio = posixpath.dirname(arquivo) == posixpath.dirname(caminho)
    return mesmo_diretorio and casa_glob(arquivo, glob) and casa_glob(caminho, glob)


def separar_remoto(ramo_base: str, remotos: Iterable[str]) -> tuple[str, str]:
    """O remoto e o ramo dentro dele, quando `ramo_base` começa por um remoto; senão, vazio e o próprio ramo.

    `origin/stage` com o remoto `origin` vira (`origin`, `stage`). Um ramo
    local com barra no nome, como `feature/x`, fica local, porque `feature`
    não é remoto.
    """
    remoto, separador, ramo = ramo_base.partition(SEPARADOR_DE_REMOTO)
    if separador and ramo and remoto in set(remotos):
        return remoto, ramo
    return "", ramo_base
