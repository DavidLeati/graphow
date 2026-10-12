"""A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit.

O executor diz que a suíte passou; o orquestrador confere rodando ela mesma.
O comando é o que o planejador declarou, rodado na raiz da área pelo mesmo
shell em que a ferramenta Bash dos agentes roda: o bash (no Windows, o Git
Bash, como o Claude Code faz; nunca o bash do WSL), para que o comando que o
executor rodou na sessão seja o mesmo que o orquestrador roda. `GRAPHOW_SHELL`
escolhe outro; sem bash nenhum, vale o shell da máquina. No tempo esgotado a
suíte morre com a árvore dela, pelo PID, como as sessões: nunca por nome. O
`GRAPHOW_DB` aponta para um banco descartável do Goal, para que um projeto que
use o graphow nos testes não escreva no banco do usuário.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from graphow.sessoes.pedido import VARIAVEL_DO_BANCO
from graphow.sessoes.sessao_claude import NO_WINDOWS, matar_arvore

VARIAVEL_DO_SHELL: str = "GRAPHOW_SHELL"
# A variável com que o Claude Code acha o Git Bash no Windows: o orquestrador acha o mesmo.
VARIAVEL_DO_GIT_BASH: str = "CLAUDE_CODE_GIT_BASH_PATH"
SHELL_DA_MAQUINA: str = "o shell da maquina (cmd no Windows, /bin/sh fora dele)"
TEMPO_LIMITE_DA_SUITE_S: float = 1800.0
LIMITE_DA_SAIDA: int = 20000
# O fim da saída que vai para a Evidence da verificação e para o bloqueante da suíte vermelha.
LIMITE_DO_TRECHO: int = 2000


@dataclass(frozen=True)
class ResultadoDaSuite:
    """Como a suíte terminou e o fim do que ela imprimiu."""

    comando: str
    codigo: int | None
    saida: str
    tempo_esgotado: bool = False
    shell: str = ""

    @property
    def passou(self) -> bool:
        """Saiu com zero dentro do tempo."""
        return self.codigo == 0 and not self.tempo_esgotado

    def descrever(self) -> str:
        """O resultado para o briefing da nova tentativa."""
        situacao = "tempo esgotado" if self.tempo_esgotado else f"codigo {self.codigo}"
        onde = f" em {self.shell}" if self.shell else ""
        return f"A suite `{self.comando}`{onde} falhou ({situacao}). Fim da saida:\n{self.saida[-LIMITE_DA_SAIDA:]}"


def shell_dos_agentes() -> Path | None:
    """O bash em que a ferramenta Bash das sessões roda; None quando a máquina não tem um."""
    explicito = os.environ.get(VARIAVEL_DO_SHELL, "").strip()
    if explicito:
        return Path(explicito)
    return _git_bash() if NO_WINDOWS else _bash_do_path()


def descrever_shell(shell: Path | None) -> str:
    """O shell da suíte em palavras, para o briefing e para o resultado."""
    return f"bash ({shell.as_posix()})" if shell is not None else SHELL_DA_MAQUINA


def _git_bash() -> Path | None:
    """O bash.exe do Git for Windows: o que o Claude Code usa; o do WSL (System32) nunca."""
    candidatos = [os.environ.get(VARIAVEL_DO_GIT_BASH, "")]
    git = shutil.which("git")
    if git:
        raiz = Path(git).resolve().parent.parent
        candidatos += [str(raiz / "bin" / "bash.exe"), str(raiz.parent / "bin" / "bash.exe")]
    return next((Path(c) for c in candidatos if c and Path(c).is_file() and "system32" not in c.lower()), None)


def _bash_do_path() -> Path | None:
    """O bash do PATH, fora do Windows."""
    bash = shutil.which("bash")
    return Path(bash) if bash else None


def rodar_suite(area: Path, comando: str, banco_descartavel: Path, *, tempo_limite_s: float = TEMPO_LIMITE_DA_SUITE_S) -> ResultadoDaSuite:
    """Roda o comando na área, no shell dos agentes, e devolve o resultado."""
    ambiente = {**os.environ, VARIAVEL_DO_BANCO: str(banco_descartavel)}
    shell = shell_dos_agentes()
    argumentos: str | list[str] = [str(shell), "-c", comando] if shell is not None else comando
    descricao = descrever_shell(shell)
    try:
        processo = subprocess.Popen(
            argumentos, shell=shell is None, cwd=area, env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=not NO_WINDOWS,
        )
    except OSError as erro:
        return ResultadoDaSuite(comando, None, f"a suite nao abriu: {erro}", shell=descricao)
    try:
        saida, _ = processo.communicate(timeout=tempo_limite_s)
    except subprocess.TimeoutExpired:
        matar_arvore(processo)
        saida, _ = processo.communicate()
        return ResultadoDaSuite(comando, processo.returncode, _texto(saida), tempo_esgotado=True, shell=descricao)
    return ResultadoDaSuite(comando, processo.returncode, _texto(saida), shell=descricao)


def _texto(saida: bytes | None) -> str:
    """A saída como texto, tolerando o que não é UTF-8."""
    return (saida or b"").decode("utf-8", errors="replace")[-LIMITE_DA_SAIDA:]
