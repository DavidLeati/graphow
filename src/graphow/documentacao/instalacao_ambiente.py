"""Instalação das skills do graphow no diretório do Claude Code, e a limpeza do que ficou obsoleto.

O orquestrador em código (`graphow orquestrar`) não precisa de nada instalado:
os prompts de papel moram no pacote e vão para cada sessão pela linha de
comando. O que se instala são as skills da sessão do humano, a `graphow-mcp`
e a `graphow-gerente`, como um plano de cópias que o setup grava e que a
conferência compara com o disco.

As versões anteriores instalavam também a skill `graphow-orquestracao` e sete
subagentes (condutor, árbitro, explorador, executores e revisores), cópias que
envelheciam em `~/.claude` e divergiam do kernel em silêncio. Eles saíram do
repositório, e o instalador remove as cópias deles quando roda: só esses
nomes, um a um, nada além.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil

from graphow.core.exceptions import GraphowError
from graphow.documentacao.skill import ARQUIVO_PRINCIPAL, listar_arquivos_da_skill

SKILLS_DO_REPOSITORIO: tuple[str, ...] = ("graphow-mcp", "graphow-gerente")
SKILLS_OBSOLETAS: tuple[str, ...] = ("graphow-orquestracao",)
AGENTES_OBSOLETOS: tuple[str, ...] = (
    "graphow-arbitro.md",
    "graphow-condutor.md",
    "graphow-executor.md",
    "graphow-executor-opus.md",
    "graphow-explorador.md",
    "graphow-revisor.md",
    "graphow-revisor-sonnet.md",
)
PASTA_DAS_SKILLS: Path = Path(".agents") / "skills"
DIRETORIO_CLAUDE_PADRAO: str = "~/.claude"


class RepositorioSemAmbiente(GraphowError):
    """A origem não tem as skills: o pacote não veio de um checkout do graphow."""


@dataclass(frozen=True)
class CopiaPlanejada:
    """Um arquivo do ambiente: onde ele vai morar e o conteúdo que deve ter."""

    destino: Path
    conteudo: bytes

    def em_dia(self) -> bool:
        """Verdadeiro quando o disco já tem exatamente este conteúdo."""
        return self.destino.is_file() and self.destino.read_bytes() == self.conteudo


@dataclass(frozen=True)
class ResultadoDoAmbiente:
    """O que a instalação gravou, por skill, e as cópias obsoletas que ela removeu."""

    arquivos_por_skill: tuple[tuple[str, int], ...]
    removidos: tuple[Path, ...] = ()


class InstaladorDoAmbiente:
    """Copia as skills do repositório e remove as cópias dos componentes que saíram dele."""

    def __init__(self, repositorio: Path, diretorio_claude: Path) -> None:
        self._repositorio: Path = repositorio
        self._diretorio_claude: Path = diretorio_claude

    def instalar(self) -> ResultadoDoAmbiente:
        """Grava o plano inteiro, sobrescrevendo as cópias anteriores, e remove as obsoletas."""
        for copia in self.planejar():
            copia.destino.parent.mkdir(parents=True, exist_ok=True)
            copia.destino.write_bytes(copia.conteudo)
        removidos = self.obsoletos()
        for caminho in removidos:
            _remover(caminho)
        contagem = tuple((nome, len(self._planejar_skill(nome))) for nome in SKILLS_DO_REPOSITORIO)
        return ResultadoDoAmbiente(arquivos_por_skill=contagem, removidos=removidos)

    def desatualizados(self) -> tuple[Path, ...]:
        """Os arquivos que faltam ou diferem do repositório, e as cópias obsoletas que ainda estão lá."""
        return tuple(copia.destino for copia in self.planejar() if not copia.em_dia()) + self.obsoletos()

    def obsoletos(self) -> tuple[Path, ...]:
        """As cópias, no diretório do Claude Code, dos componentes que saíram do repositório."""
        candidatos = (
            *(self._diretorio_claude / "skills" / nome for nome in SKILLS_OBSOLETAS),
            *(self._diretorio_claude / "agents" / nome for nome in AGENTES_OBSOLETOS),
        )
        return tuple(caminho for caminho in candidatos if caminho.exists())

    def planejar(self) -> tuple[CopiaPlanejada, ...]:
        """Todas as cópias, skill a skill."""
        self._exigir_origem()
        return tuple(copia for nome in SKILLS_DO_REPOSITORIO for copia in self._planejar_skill(nome))

    def _exigir_origem(self) -> None:
        """Recusa a origem que não é um checkout do graphow, dizendo onde procurou."""
        faltando = [nome for nome in SKILLS_DO_REPOSITORIO if not (self._origem_da_skill(nome) / ARQUIVO_PRINCIPAL).is_file()]
        if not faltando:
            return
        raise RepositorioSemAmbiente(
            f"Skills do graphow nao encontradas em {self._repositorio}: "
            "rode de um checkout do graphow instalado com 'pip install -e .' ou passe --origem",
            {"origem": str(self._repositorio), "skills_faltando": ", ".join(faltando)},
        )

    def _origem_da_skill(self, nome: str) -> Path:
        """A pasta da skill no repositório."""
        return self._repositorio / PASTA_DAS_SKILLS / nome

    def _planejar_skill(self, nome: str) -> tuple[CopiaPlanejada, ...]:
        """Cada arquivo da skill, no mesmo caminho relativo dentro de skills/<nome>."""
        origem = self._origem_da_skill(nome)
        alvo = self._diretorio_claude / "skills" / nome
        return tuple(
            CopiaPlanejada(destino=alvo / arquivo.relative_to(origem), conteudo=arquivo.read_bytes())
            for arquivo in listar_arquivos_da_skill(origem)
        )


def _remover(caminho: Path) -> None:
    """A pasta da skill obsoleta inteira, ou o arquivo do subagente obsoleto."""
    if caminho.is_dir():
        shutil.rmtree(caminho)
        return
    caminho.unlink()
