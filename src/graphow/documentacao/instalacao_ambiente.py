"""Instalação das skills e dos subagentes do graphow no diretório do Claude Code.

O `skill-instalar` copiava só a `graphow-mcp`. A `graphow-orquestracao` e os
sete subagentes se copiavam à mão, e a cópia envelhecia sem ninguém notar: com
um subagente de versão anterior, o servidor recusava `--autor-por-conexao` e
não subia. Aqui a instalação inteira vira um plano de cópias, que o setup
grava e que a conferência compara com o que está no disco.
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.documentacao.ambiente import fixar_executavel_no_agente
from graphow.documentacao.skill import ARQUIVO_PRINCIPAL, listar_arquivos_da_skill

SKILLS_DO_REPOSITORIO: tuple[str, ...] = ("graphow-mcp", "graphow-orquestracao", "graphow-gerente")
PASTA_DAS_SKILLS: Path = Path(".agents") / "skills"
PASTA_DOS_AGENTES: Path = Path(".agents") / "agents"
PADRAO_DOS_AGENTES: str = "graphow-*.md"
DIRETORIO_CLAUDE_PADRAO: str = "~/.claude"


class RepositorioSemAmbiente(GraphowError):
    """A origem não tem as skills e os subagentes: o pacote não veio de um checkout do graphow."""


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
    """O que a instalação gravou: arquivos por skill e os subagentes."""

    arquivos_por_skill: tuple[tuple[str, int], ...]
    agentes: tuple[Path, ...]


class InstaladorDoAmbiente:
    """Copia as skills e os subagentes, com o servidor MCP de cada um no executável dado."""

    def __init__(self, repositorio: Path, diretorio_claude: Path, executavel: str) -> None:
        self._repositorio: Path = repositorio
        self._diretorio_claude: Path = diretorio_claude
        self._executavel: str = executavel

    def instalar(self) -> ResultadoDoAmbiente:
        """Grava o plano inteiro, sobrescrevendo as cópias anteriores."""
        for copia in self.planejar():
            copia.destino.parent.mkdir(parents=True, exist_ok=True)
            copia.destino.write_bytes(copia.conteudo)
        contagem = tuple((nome, len(self._planejar_skill(nome))) for nome in SKILLS_DO_REPOSITORIO)
        return ResultadoDoAmbiente(arquivos_por_skill=contagem, agentes=tuple(c.destino for c in self._planejar_agentes()))

    def desatualizados(self) -> tuple[Path, ...]:
        """Os arquivos do ambiente que faltam ou diferem do repositório."""
        return tuple(copia.destino for copia in self.planejar() if not copia.em_dia())

    def planejar(self) -> tuple[CopiaPlanejada, ...]:
        """Todas as cópias, skills primeiro e subagentes depois."""
        self._exigir_origem()
        skills = tuple(copia for nome in SKILLS_DO_REPOSITORIO for copia in self._planejar_skill(nome))
        return skills + self._planejar_agentes()

    def _exigir_origem(self) -> None:
        """Recusa a origem que não é um checkout do graphow, dizendo onde procurou."""
        faltando = [nome for nome in SKILLS_DO_REPOSITORIO if not (self._origem_da_skill(nome) / ARQUIVO_PRINCIPAL).is_file()]
        if not faltando and self._listar_agentes():
            return
        raise RepositorioSemAmbiente(
            f"Skills e subagentes do graphow nao encontrados em {self._repositorio}: "
            "rode de um checkout do graphow instalado com 'pip install -e .' ou passe --origem",
            {"origem": str(self._repositorio), "skills_faltando": faltando},
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

    def _listar_agentes(self) -> tuple[Path, ...]:
        """As definições dos subagentes no repositório, em ordem estável."""
        return tuple(sorted((self._repositorio / PASTA_DOS_AGENTES).glob(PADRAO_DOS_AGENTES)))

    def _planejar_agentes(self) -> tuple[CopiaPlanejada, ...]:
        """Cada subagente com o `command` do servidor MCP trocado pelo executável."""
        alvo = self._diretorio_claude / "agents"
        return tuple(
            CopiaPlanejada(
                destino=alvo / agente.name,
                conteudo=fixar_executavel_no_agente(agente.read_bytes().decode("utf-8"), self._executavel).encode("utf-8"),
            )
            for agente in self._listar_agentes()
        )
