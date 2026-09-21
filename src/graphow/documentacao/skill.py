"""Instalação da skill do agente no diretório de skills do ambiente.

A skill `graphow-mcp` vive no repositório, em `.agents/skills/`, e só vale para
o agente que a encontra. As cópias feitas à mão por projeto envelhecem: a de um
projeto real dizia 19 ferramentas e não sabia que Aprendizado existia. O
instalador copia a skill do repositório em que o pacote foi instalado para o
diretório de skills do usuário, onde todo projeto a vê, e rodar de novo
atualiza a cópia.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil

from graphow.core.exceptions import GraphowError

NOME_DA_SKILL: str = "graphow-mcp"
CAMINHO_DA_SKILL_NO_REPOSITORIO: Path = Path(".agents") / "skills" / NOME_DA_SKILL
DIRETORIO_DE_SKILLS_PADRAO: str = "~/.claude/skills"
ARQUIVO_PRINCIPAL: str = "SKILL.md"
PASTAS_IGNORADAS: frozenset[str] = frozenset({"__pycache__"})


class SkillNaoEncontrada(GraphowError):
    """A origem não tem a skill: o pacote foi instalado fora de um checkout do repositório."""


@dataclass(frozen=True)
class ResultadoDaInstalacao:
    """Onde a skill ficou e o que foi copiado, em caminhos relativos à skill."""

    destino: Path
    arquivos_copiados: tuple[str, ...]


class InstaladorDeSkill:
    """Copia a skill inteira (SKILL.md, referências e scripts) para o diretório de skills."""

    def __init__(self, origem: Path, destino: Path) -> None:
        self._origem: Path = origem
        self._destino: Path = destino

    def instalar(self) -> ResultadoDaInstalacao:
        """Copia arquivo por arquivo, sobrescrevendo a cópia anterior; devolve o que copiou."""
        if not (self._origem / ARQUIVO_PRINCIPAL).is_file():
            raise SkillNaoEncontrada(
                f"Skill '{NOME_DA_SKILL}' nao encontrada em {self._origem}: "
                "rode de um checkout do graphow ou passe --origem",
                {"origem": str(self._origem)},
            )
        alvo = self._destino / NOME_DA_SKILL
        copiados = [self._copiar(arquivo, alvo) for arquivo in self._listar_arquivos()]
        return ResultadoDaInstalacao(destino=alvo, arquivos_copiados=tuple(copiados))

    def _listar_arquivos(self) -> tuple[Path, ...]:
        """Os arquivos da skill, em ordem estável em qualquer sistema, sem os caches do interpretador."""
        arquivos = (
            caminho
            for caminho in self._origem.rglob("*")
            if caminho.is_file() and not PASTAS_IGNORADAS.intersection(caminho.relative_to(self._origem).parts)
        )
        return tuple(sorted(arquivos, key=lambda caminho: caminho.relative_to(self._origem).as_posix()))

    def _copiar(self, arquivo: Path, alvo: Path) -> str:
        """Copia um arquivo preservando o caminho relativo dentro da skill."""
        relativo = arquivo.relative_to(self._origem)
        destino = alvo / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arquivo, destino)
        return relativo.as_posix()
