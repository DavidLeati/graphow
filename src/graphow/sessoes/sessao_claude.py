"""Roda uma sessão `claude -p` com tempo limite e devolve o resultado tipado.

O stream vai direto para um arquivo, e não para a memória: uma sessão de vinte
minutos escreve megabytes, e o arquivo é o registro que a medição relê depois,
inclusive quando o processo morre no meio. A saída de erro vai para outro
arquivo ao lado.

No tempo esgotado, a sessão morre com a árvore dela, a partir do PID: no
Windows, `taskkill /PID <pid> /T /F`, porque o executável costuma ser um `.cmd`
que abre o claude de verdade como filho, e matar só o PID do `.cmd` deixava o
claude rodando; no POSIX, o grupo de processos, porque a sessão nasce num
grupo só dela. Os filhos que o agente subiu (um servidor, por exemplo) morrem
junto. Nunca por nome (`taskkill /IM`, `pkill`): isso mataria os processos de
outros trabalhos da máquina.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
from typing import Any

from graphow.core.exceptions import GraphowError
from graphow.sessoes.executavel import descobrir_executavel
from graphow.sessoes.leitura_stream import LeituraDoStream, UsoDeTokens, ler_stream
from graphow.sessoes.pedido import PedidoDeSessao, limpar_ambiente, montar_comando

NO_WINDOWS: bool = os.name == "nt"
TEMPO_DO_TASKKILL_S: float = 30.0


class FalhaAoAbrirSessao(GraphowError):
    """O processo da sessão não chegou a rodar."""


@dataclass(frozen=True)
class ResultadoDeSessao:
    """O que a sessão fez, lido do stream, e como o processo terminou.

    `is_error` junta as três formas de dar errado: o `result` com erro, o
    processo que saiu com código diferente de zero e o que não chegou ao fim.
    """

    comando: tuple[str, ...]
    arquivo_stream: Path
    inicio: datetime
    fim: datetime
    codigo_saida: int | None
    tempo_esgotado: bool
    leitura: LeituraDoStream

    @property
    def session_id(self) -> str:
        """A sessão que o stream abriu; vazio quando ele não chegou a abrir."""
        return self.leitura.session_id

    @property
    def texto_final(self) -> str:
        """A resposta final da sessão."""
        return self.leitura.resultado.texto if self.leitura.resultado else ""

    @property
    def is_error(self) -> bool:
        """Erro no resultado, no processo ou no tempo."""
        resultado = self.leitura.resultado
        return self.tempo_esgotado or self.codigo_saida != 0 or resultado is None or resultado.is_error

    @property
    def custo_usd(self) -> float:
        """O custo que o resultado declarou; acumulado da sessão, se ela foi retomada."""
        return self.leitura.resultado.custo_usd if self.leitura.resultado else 0.0

    @property
    def tokens(self) -> UsoDeTokens:
        """O `modelUsage` do resultado: sessão e subagentes, acumulado como o custo."""
        return self.leitura.resultado.tokens if self.leitura.resultado else UsoDeTokens()

    @property
    def turnos(self) -> int:
        """Os turnos que o resultado declarou."""
        return self.leitura.resultado.turnos if self.leitura.resultado else 0

    @property
    def duracao_s(self) -> float:
        """O tempo de parede, do lançamento do processo ao fim dele."""
        return (self.fim - self.inicio).total_seconds()

    def em_dicionario(self) -> dict[str, Any]:
        """O resumo da sessão, para gravar em JSON ao lado do stream."""
        return {
            "session_id": self.session_id,
            "comando": list(self.comando),
            "arquivo_stream": self.arquivo_stream.name,
            "inicio": em_iso(self.inicio),
            "fim": em_iso(self.fim),
            "codigo_saida": self.codigo_saida,
            "tempo_esgotado": self.tempo_esgotado,
            "is_error": self.is_error,
            "custo_usd": self.custo_usd,
            "turnos": self.turnos,
            "tokens_model_usage": self.tokens.em_dicionario(),
        }


class ExecutorDeSessao:
    """Lança o `claude -p` de cada pedido e espera por ele até o tempo limite."""

    def __init__(
        self,
        executavel: Sequence[str] | None = None,
        ambiente: Mapping[str, str] | None = None,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self._ambiente: Mapping[str, str] = dict(os.environ) if ambiente is None else ambiente
        self._executavel: tuple[str, ...] = tuple(executavel or (str(descobrir_executavel(self._ambiente)),))
        self._relogio: Callable[[], datetime] = relogio or _agora

    def comando_de(self, pedido: PedidoDeSessao) -> tuple[str, ...]:
        """A linha de comando que o pedido gera, sem rodar nada."""
        return montar_comando(self._executavel, pedido)

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """Roda a sessão, grava o stream e devolve o resultado lido dele."""
        comando = self.comando_de(pedido)
        pedido.arquivo_stream.parent.mkdir(parents=True, exist_ok=True)
        inicio = self._relogio()
        codigo, esgotado = self._lancar(comando, pedido)
        fim = self._relogio()
        with pedido.arquivo_stream.open(encoding="utf-8", errors="replace") as stream:
            leitura = ler_stream(stream)
        return ResultadoDeSessao(
            comando=comando,
            arquivo_stream=pedido.arquivo_stream,
            inicio=inicio,
            fim=fim,
            codigo_saida=codigo,
            tempo_esgotado=esgotado,
            leitura=leitura,
        )

    def _lancar(self, comando: tuple[str, ...], pedido: PedidoDeSessao) -> tuple[int | None, bool]:
        """O código de saída e se o tempo esgotou; o prompt vai pela entrada padrão."""
        with pedido.arquivo_stream.open("wb") as saida, pedido.arquivo_erro.open("wb") as erros:
            processo = self._abrir(comando, pedido, (saida, erros))
            try:
                processo.communicate(pedido.prompt.encode("utf-8"), timeout=pedido.tempo_limite_s)
            except subprocess.TimeoutExpired:
                matar_arvore(processo)
                processo.communicate()
                return processo.returncode, True
        return processo.returncode, False

    def _abrir(self, comando: tuple[str, ...], pedido: PedidoDeSessao, destinos: tuple[Any, Any]) -> subprocess.Popen[bytes]:
        """O processo da sessão, na pasta do pedido, com o ambiente limpo e, no POSIX, num grupo próprio."""
        try:
            return subprocess.Popen(
                comando,
                stdin=subprocess.PIPE,
                stdout=destinos[0],
                stderr=destinos[1],
                cwd=pedido.pasta,
                env=limpar_ambiente(self._ambiente, pedido),
                start_new_session=not NO_WINDOWS,
            )
        except OSError as erro:
            raise FalhaAoAbrirSessao("a sessao claude -p nao abriu", {"comando": comando[0], "erro": str(erro)}) from erro


def matar_arvore(processo: subprocess.Popen[bytes]) -> None:
    """O processo e os descendentes dele, a partir do PID; o próprio processo morre de qualquer jeito."""
    if NO_WINDOWS:
        _matar_arvore_no_windows(processo.pid)
    else:
        _matar_grupo(processo.pid)
    processo.kill()


def _matar_arvore_no_windows(pid: int) -> None:
    """`taskkill /PID <pid> /T /F`: a árvore que nasceu do PID, e só ela."""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False, timeout=TEMPO_DO_TASKKILL_S
        )
    except (OSError, subprocess.SubprocessError):
        return


def _matar_grupo(pid: int) -> None:
    """O grupo de processos que a sessão abriu ao nascer, cujo id é o PID dela."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def em_iso(instante: datetime) -> str:
    """O instante em ISO 8601 com fuso, em segundos."""
    return instante.isoformat(timespec="seconds")


def _agora() -> datetime:
    """O relógio da máquina, com fuso."""
    return datetime.now(timezone.utc).astimezone()
