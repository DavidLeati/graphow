"""A suíte do projeto, rodada pelo orquestrador na área do Goal antes de cada commit.

O executor diz que a suíte passou; o orquestrador confere rodando ela mesma.
O comando é o que o planejador declarou, rodado pelo shell da máquina na raiz
da área. No tempo esgotado a suíte morre com a árvore dela, pelo PID, como as
sessões: nunca por nome. O `GRAPHOW_DB` aponta para um banco descartável do
Goal, para que um projeto que use o graphow nos testes não escreva no banco do
usuário.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from graphow.sessoes.pedido import VARIAVEL_DO_BANCO
from graphow.sessoes.sessao_claude import NO_WINDOWS, matar_arvore

TEMPO_LIMITE_DA_SUITE_S: float = 1800.0
LIMITE_DA_SAIDA: int = 20000


@dataclass(frozen=True)
class ResultadoDaSuite:
    """Como a suíte terminou e o fim do que ela imprimiu."""

    comando: str
    codigo: int | None
    saida: str
    tempo_esgotado: bool = False

    @property
    def passou(self) -> bool:
        """Saiu com zero dentro do tempo."""
        return self.codigo == 0 and not self.tempo_esgotado

    def descrever(self) -> str:
        """O resultado para o briefing da nova tentativa."""
        situacao = "tempo esgotado" if self.tempo_esgotado else f"codigo {self.codigo}"
        return f"A suite `{self.comando}` falhou ({situacao}). Fim da saida:\n{self.saida[-LIMITE_DA_SAIDA:]}"


def rodar_suite(area: Path, comando: str, banco_descartavel: Path, *, tempo_limite_s: float = TEMPO_LIMITE_DA_SUITE_S) -> ResultadoDaSuite:
    """Roda o comando na área e devolve o resultado."""
    ambiente = {**os.environ, VARIAVEL_DO_BANCO: str(banco_descartavel)}
    try:
        processo = subprocess.Popen(
            comando, shell=True, cwd=area, env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=not NO_WINDOWS,
        )
    except OSError as erro:
        return ResultadoDaSuite(comando, None, f"a suite nao abriu: {erro}")
    try:
        saida, _ = processo.communicate(timeout=tempo_limite_s)
    except subprocess.TimeoutExpired:
        matar_arvore(processo)
        saida, _ = processo.communicate()
        return ResultadoDaSuite(comando, processo.returncode, _texto(saida), tempo_esgotado=True)
    return ResultadoDaSuite(comando, processo.returncode, _texto(saida))


def _texto(saida: bytes | None) -> str:
    """A saída como texto, tolerando o que não é UTF-8."""
    return (saida or b"").decode("utf-8", errors="replace")[-LIMITE_DA_SAIDA:]
