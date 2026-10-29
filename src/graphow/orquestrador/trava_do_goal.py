"""Um orquestrador por Goal: a trava que impede duas execuções de `graphow orquestrar` no mesmo Goal.

Duas chamadas no mesmo Goal usariam juntas o mesmo clone, o mesmo livro-razão e
a mesma branch. A trava é um arquivo na pasta de estado do Goal
(`<pasta do banco>/orquestrar/<goal>/orquestrar.trava`), criado com
`O_CREAT | O_EXCL`, que o sistema de arquivos garante exclusivo entre
processos. Ela guarda quem a tomou: PID, máquina, início, comando e uma ficha
única, que a solta e a liberação conferem para não levar a trava de outro.

A segunda chamada recebe `GoalOcupado`, com quem roda e como liberar. A trava
velha, de um PID que não existe mais nesta máquina, é liberada com um aviso.
A de outra máquina não: daqui não dá para saber se o processo de lá vive, e a
mensagem diz como liberar à mão. A liberação renomeia o arquivo antes de
apagá-lo e confere a ficha, para não apagar a trava nova que outra chamada
tomou no meio; se apanhou a nova, devolve-a.
"""

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import time
import uuid

from graphow.core.exceptions import GraphowError

NOME_DA_TRAVA: str = "orquestrar.trava"
TENTATIVAS: int = 3
PAUSA_ENTRE_TENTATIVAS_S: float = 0.05
# OpenProcess no Windows: o direito mínimo para ler o código de saída, o código de quem ainda roda e o erro de quem existe.
CONSULTA_LIMITADA: int = 0x1000
AINDA_ATIVO: int = 259
ACESSO_NEGADO: int = 5


class GoalOcupado(GraphowError):
    """Outra execução de `graphow orquestrar` conduz o Goal, ou a trava dele não dá para ler ou tomar."""


@dataclass(frozen=True)
class DonoDaTrava:
    """Quem tomou a trava: o processo, a máquina, desde quando, com que comando e a ficha que a distingue."""

    pid: int
    maquina: str
    inicio: str
    comando: str
    ficha: str

    def descrever(self) -> str:
        """O dono como a mensagem o mostra."""
        return f"PID {self.pid} na maquina {self.maquina}, desde {self.inicio} (comando: {self.comando})"


@dataclass(frozen=True)
class TravaDoGoal:
    """A trava tomada: onde ela está, de quem é e o aviso da trava velha que foi liberada para tomá-la."""

    caminho: Path
    dono: DonoDaTrava
    aviso: str = ""


@contextmanager
def conduzindo(pasta: Path, id_goal: str) -> Iterator[TravaDoGoal]:
    """A trava do Goal durante o bloco; ela é solta no fim, inclusive por exceção ou parada."""
    trava = tomar_trava(pasta, id_goal)
    try:
        yield trava
    finally:
        soltar_trava(trava)


def tomar_trava(pasta: Path, id_goal: str) -> TravaDoGoal:
    """Toma a trava do Goal na pasta de estado dele, liberando a velha desta máquina; `GoalOcupado` quando outra vale."""
    caminho = pasta / NOME_DA_TRAVA
    pasta.mkdir(parents=True, exist_ok=True)
    dono = _quem_sou()
    aviso = ""
    for _ in range(TENTATIVAS):
        if _escrever_exclusivo(caminho, json.dumps(asdict(dono), ensure_ascii=False)):
            return TravaDoGoal(caminho, dono, aviso)
        aviso = _liberar_a_velha(caminho, id_goal) or aviso
    raise GoalOcupado(
        f"Nao deu para tomar a trava do Goal {id_goal} em {TENTATIVAS} tentativas: outra chamada a tomou e soltou no meio, "
        f"ou a pasta nao aceita escrita. Rode de novo; se persistir, confira {caminho}.",
        {"trava": str(caminho)},
    )


def soltar_trava(trava: TravaDoGoal) -> None:
    """Solta a trava se ela ainda é desta execução (a ficha confere); no Windows, espera quem a lê fechar o arquivo."""
    for _ in range(TENTATIVAS):
        atual = ler_dono(trava.caminho)
        if atual is None or atual.ficha != trava.dono.ficha:
            return
        try:
            trava.caminho.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(PAUSA_ENTRE_TENTATIVAS_S)


def ler_dono(caminho: Path) -> DonoDaTrava | None:
    """Quem tem a trava; None sem trava, ou com uma que não dá para ler (vazia, corrompida ou de outro formato)."""
    try:
        dono = DonoDaTrava(**json.loads(_ler_texto(caminho)))
    except (ValueError, TypeError):
        return None
    return dono if isinstance(dono.pid, int) else None


def _ler_texto(caminho: Path) -> str:
    """O conteúdo do arquivo; vazio quando ele não existe ou não dá para ler (no Windows, o que está sendo apagado)."""
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError:
        return ""


def processo_vivo(pid: int) -> bool:
    """O processo de PID dado existe nesta máquina (no POSIX, o sinal 0; no Windows, OpenProcess, que não mata nada)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _vivo_no_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _vivo_no_windows(pid: int) -> bool:
    """OpenProcess e o código de saída: sem processo, o erro 87; o que existe e não deixa abrir, o 5; o vivo, 259."""
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    alca = kernel32.OpenProcess(CONSULTA_LIMITADA, False, pid)
    if not alca:
        return bool(ctypes.get_last_error() == ACESSO_NEGADO)
    try:
        codigo = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(alca, ctypes.byref(codigo))) and codigo.value == AINDA_ATIVO
    finally:
        kernel32.CloseHandle(alca)


def _quem_sou() -> DonoDaTrava:
    """Esta execução como dona da trava."""
    inicio = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return DonoDaTrava(os.getpid(), socket.gethostname(), inicio, " ".join(sys.argv), uuid.uuid4().hex)


def _escrever_exclusivo(caminho: Path, conteudo: str) -> bool:
    """Cria o arquivo com o conteúdo só se ele não existe; False quando existe (ou, no Windows, está sendo apagado)."""
    try:
        descritor = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except (FileExistsError, PermissionError):
        return False
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    return True


def _liberar_a_velha(caminho: Path, id_goal: str) -> str:
    """O aviso da trava velha liberada; vazio quando ela sumiu antes. `GoalOcupado` quando ela vale ou não dá para julgar."""
    dono = ler_dono(caminho)
    if dono is None:
        if caminho.exists():
            raise GoalOcupado(_mensagem_da_ilegivel(caminho, id_goal), {"trava": str(caminho)})
        return ""
    if dono.maquina != socket.gethostname():
        raise GoalOcupado(_mensagem_de_outra_maquina(caminho, id_goal, dono), {"trava": str(caminho)})
    if processo_vivo(dono.pid):
        raise GoalOcupado(_mensagem_em_execucao(caminho, id_goal, dono), {"trava": str(caminho)})
    if not _tirar_a_velha(caminho, dono):
        return ""
    return f"Aviso: a trava do Goal {id_goal} era do {dono.descrever()}, que nao existe mais nesta maquina; foi liberada."


def _tirar_a_velha(caminho: Path, velha: DonoDaTrava) -> bool:
    """Tira do caminho a trava velha, e só ela: renomeia, confere a ficha e devolve a que não era a velha."""
    tirada = caminho.with_name(f"{caminho.name}.velha-{uuid.uuid4().hex}")
    try:
        os.replace(caminho, tirada)
    except OSError:
        return False
    dona = ler_dono(tirada)
    if dona is not None and dona.ficha == velha.ficha:
        tirada.unlink(missing_ok=True)
        return True
    _escrever_exclusivo(caminho, _ler_texto(tirada))
    tirada.unlink(missing_ok=True)
    return False


def _mensagem_em_execucao(caminho: Path, id_goal: str, dono: DonoDaTrava) -> str:
    """Quem conduz o Goal agora, nesta máquina, e como liberar."""
    return (
        f"O Goal {id_goal} ja esta sendo conduzido pelo {dono.descrever()}. Espere essa execucao parar "
        f"(`graphow orquestrar --goal {id_goal} --status` le o Goal enquanto isso). Para liberar antes, encerre o "
        f"PID {dono.pid}: a trava de um PID que nao existe mais e liberada na proxima chamada. A trava fica em {caminho}."
    )


def _mensagem_de_outra_maquina(caminho: Path, id_goal: str, dono: DonoDaTrava) -> str:
    """A trava de outra máquina: daqui não dá para saber se o processo vive, e só o humano a libera."""
    return (
        f"O Goal {id_goal} esta travado pelo {dono.descrever()}, e daqui ({socket.gethostname()}) nao da para saber "
        f"se esse processo ainda roda. Confira naquela maquina; se ele parou, libere a mao apagando {caminho} "
        f"e rode de novo."
    )


def _mensagem_da_ilegivel(caminho: Path, id_goal: str) -> str:
    """A trava que não dá para ler: pode ser outra chamada tomando-a agora."""
    return (
        f"A trava do Goal {id_goal} em {caminho} nao da para ler (vazia ou corrompida): outra chamada pode estar "
        f"tomando-a agora. Se nenhuma `graphow orquestrar` roda este Goal, libere a mao apagando o arquivo e rode de novo."
    )
