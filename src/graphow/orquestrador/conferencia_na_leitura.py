"""A conferência da Evidence na hora da leitura: o briefing e o `--status` perguntam aqui.

A conferência em si mora em orquestrador/conferencia_da_evidencia.py. Aqui
fica o que cada leitor precisa em volta dela:

- a Evidence que não é sobre código e não tem âncora (a fonte, o log de teste,
  o veredito do revisor do MCP) não leva marca: não afirma nada do código;
- a sobre código sem âncora, a antiga gravada antes da regra, sai `sem_ancora`,
  sem precisar de git;
- a ancorada é conferida no git da leitura; sem repositório à mão, sai
  `nao_conferida`, e o leitor não adivinha.

O `--status` confere no repositório do humano, na branch do Goal, que a
configuração gravada no Goal diz (a branch existe enquanto o Goal vive e
depois do fecho, quando a área já foi removida).

Cada leitura tem o seu cache (`GitDaLeitura`): cada consulta ao git, o
`diff --name-only` por par de commits inclusive, roda uma vez por leitura.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graphow.core.types import PapelAutor
from graphow.kernel.ancora_da_evidencia import ancora_da_evidencia, sobre_codigo
from graphow.orquestrador.conferencia_da_evidencia import (
    DESATUALIZADA,
    SEM_ANCORA,
    VIGENTE,
    ConferenciaDaEvidencia,
    conferir_evidencia,
    sem_ancora,
)
from graphow.orquestrador.git_do_goal import GitDoGoal, SaidaDoGit

NAO_CONFERIDA: str = "nao_conferida"
PAPEL_DO_ORQUESTRADOR: str = PapelAutor.ORQUESTRADOR.value
MAXIMO_DE_ARQUIVOS_NO_ROTULO: int = 8
ROTULOS: dict[str, str] = {VIGENTE: "vigente", SEM_ANCORA: "sem ancora", NAO_CONFERIDA: "nao conferida"}


@dataclass(frozen=True)
class GitDaLeitura(GitDoGoal):
    """O git de uma leitura: cada consulta roda uma vez e fica guardada até a leitura acabar."""

    memoria: dict[tuple[str, ...], SaidaDoGit] = field(default_factory=dict, compare=False, repr=False)

    def tentar(self, *argumentos: str) -> SaidaDoGit:
        """A consulta, do cache quando a leitura já a fez."""
        if argumentos not in self.memoria:
            self.memoria[argumentos] = super().tentar(*argumentos)
        return self.memoria[argumentos]


class LeituraDaConferencia:
    """Uma leitura: o git em que a Evidence ancorada confere (ou nenhum) e a ponta."""

    def __init__(self, git: GitDoGoal | None, ponta: str = "HEAD") -> None:
        self._git: GitDaLeitura | None = None if git is None else GitDaLeitura(git.pasta)
        self._ponta: str = ponta

    def conferir(self, papel: str, propriedades: Mapping[str, Any]) -> ConferenciaDaEvidencia | None:
        """A conferência da Evidence gravada pelo papel; None quando ela não é sobre código nem tem âncora."""
        if ancora_da_evidencia(propriedades) is None:
            return sem_ancora(propriedades) if sobre_codigo(papel, propriedades) else None
        if self._git is None:
            return ConferenciaDaEvidencia(NAO_CONFERIDA, motivo="sem repositorio git a mao nesta leitura")
        return conferir_evidencia(propriedades, self._git, self._ponta)


def leitura_do_repositorio(repositorio: object, ramo: object) -> LeituraDaConferencia:
    """A leitura no repositório, na ponta da branch; sem git quando a pasta não é repositório ou a branch não existe."""
    pasta, ponta = Path(str(repositorio or "")), str(ramo or "")
    if not str(repositorio or "") or not ponta or not pasta.is_dir():
        return LeituraDaConferencia(None)
    git = GitDoGoal(pasta)
    existe = git.tentar("rev-parse", "--verify", "--quiet", f"refs/heads/{ponta}^{{commit}}").codigo == 0
    return LeituraDaConferencia(git if existe else None, ponta)


def rotulo_da_conferencia(conferencia: ConferenciaDaEvidencia) -> str:
    """O rótulo curto: `vigente`, `desatualizada (mudaram: ...)`, `sem ancora` ou `nao conferida`."""
    if conferencia.estado != DESATUALIZADA:
        return ROTULOS.get(conferencia.estado, conferencia.estado)
    arquivos = list(conferencia.arquivos[:MAXIMO_DE_ARQUIVOS_NO_ROTULO])
    resto = len(conferencia.arquivos) - len(arquivos)
    return "desatualizada (mudaram: " + ", ".join(arquivos) + (f" e mais {resto}" if resto > 0 else "") + ")"


def aviso_de_historico(conferencia: ConferenciaDaEvidencia) -> str:
    """O aviso do briefing para a Evidence que não vale na ponta: o estado em maiúsculas e os arquivos, ou o motivo."""
    if conferencia.estado == DESATUALIZADA:
        return f"DESATUALIZADA: {', '.join(conferencia.arquivos)} mudaram desde o commit dela"
    estado = rotulo_da_conferencia(conferencia).upper()
    return f"{estado} ({conferencia.motivo})" if conferencia.motivo else estado
