"""A árvore de processos de uma sessão: o que nasceu dela morre com ela, no tempo esgotado e no fim normal.

O agente deixa processos vivos depois que a sessão acaba: o servidor que subiu
com `&`, o `nohup`, o filho do `.cmd`. Um deles podia reescrever o settings do
hook da trava ou o `.claude/` do clone depois da conferência da sessão
(orquestrador/sessoes_de_papel.py), e a culpa caía na sessão seguinte. Por
isso, ao fim de toda sessão, antes da conferência, a árvore dela morre:

- no Windows, o processo nasce suspenso, entra num Job Object e só então
  roda: todo descendente nasce dentro do job, inclusive o que fica órfão
  quando o pai sai (o `taskkill /T` não acha o órfão, porque segue o PID do
  pai, que já morreu). No fim, `TerminateJobObject` mata o job inteiro. O
  job leva `KILL_ON_JOB_CLOSE`: se o orquestrador morre antes do fim, o
  Windows fecha a alça dele, e a árvore morre junto. Sem o job (o Windows
  não o criou), vale o `taskkill /PID <pid> /T /F`. O processo que o WMI
  cria (`Win32_Process.Create`) nasce fora do job e escapa: limite conhecido;
- no POSIX, a sessão nasce num grupo de processos só dela, e o grupo morre
  inteiro (`killpg`), o órfão inclusive; quem chama `setsid` sai do grupo.

Nunca por nome (`taskkill /IM`, `pkill`): isso mataria os processos de outros
trabalhos da máquina.
"""

import ctypes
from dataclasses import dataclass
import os
import signal
import subprocess
import time
from typing import Any

NO_WINDOWS: bool = os.name == "nt"
TEMPO_DO_TASKKILL_S: float = 30.0
TEMPO_PARA_O_JOB_ESVAZIAR_S: float = 5.0
# No Windows, o processo nasce suspenso (CREATE_SUSPENDED), para entrar no job antes de abrir qualquer filho.
CRIACAO_DA_SESSAO: int = 0x00000004 if NO_WINDOWS else 0
# PROCESS_SET_QUOTA e PROCESS_TERMINATE (entrar no job) e PROCESS_SUSPEND_RESUME (soltar o processo).
ACESSO_AO_PROCESSO: int = 0x0100 | 0x0001 | 0x0800
# JobObjectBasicAccountingInformation: quantos processos do job seguem ativos.
CONTABILIDADE_DO_JOB: int = 1
# JobObjectExtendedLimitInformation e JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: a árvore morre quando a alça do job fecha.
LIMITES_DO_JOB: int = 9
MATAR_AO_FECHAR_O_JOB: int = 0x2000
CODIGO_DA_ARVORE_MORTA: int = 1


class _ContabilidadeDoJob(ctypes.Structure):
    """JOBOBJECT_BASIC_ACCOUNTING_INFORMATION: os quatro tempos e as contagens de processos do job."""

    _fields_ = (("tempos", ctypes.c_int64 * 4), ("faltas_de_pagina", ctypes.c_uint32), ("total", ctypes.c_uint32),
                ("ativos", ctypes.c_uint32), ("terminados", ctypes.c_uint32))


class _LimitesDoJob(ctypes.Structure):
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION: os limites básicos (as flags entre eles), a E/S e a memória do job."""

    _fields_ = (("tempos", ctypes.c_int64 * 2), ("flags", ctypes.c_uint32), ("conjunto", ctypes.c_size_t * 2),
                ("processos", ctypes.c_uint32), ("afinidade", ctypes.c_size_t), ("prioridade", ctypes.c_uint32),
                ("escalonamento", ctypes.c_uint32), ("entrada_e_saida", ctypes.c_uint64 * 6),
                ("memoria", ctypes.c_size_t * 4))


@dataclass(frozen=True)
class ArvoreDaSessao:
    """O PID da sessão e, no Windows, a alça do Job Object em que ela e os descendentes dela nascem."""

    pid: int
    job: int | None = None


def prender_a_arvore(processo: subprocess.Popen[bytes]) -> ArvoreDaSessao:
    """No Windows, põe o processo (nascido suspenso) num Job Object e o solta; no POSIX, o grupo dele já é a árvore."""
    if not NO_WINDOWS:
        return ArvoreDaSessao(processo.pid)
    kernel32 = _kernel32()
    alca = kernel32.OpenProcess(ACESSO_AO_PROCESSO, False, processo.pid)
    job = _job_com(kernel32, alca)
    solto = bool(alca) and _ntdll().NtResumeProcess(alca) == 0
    if alca:
        kernel32.CloseHandle(alca)
    if not solto:
        matar_a_arvore(processo, ArvoreDaSessao(processo.pid, job))
        raise OSError(f"o processo da sessao nasceu suspenso e nao foi solto (erro {ctypes.get_last_error()})")
    return ArvoreDaSessao(processo.pid, job)


def matar_a_arvore(processo: subprocess.Popen[bytes], arvore: ArvoreDaSessao) -> None:
    """A sessão e tudo o que nasceu dela, vivo ou órfão; no Windows, espera o job esvaziar."""
    if arvore.job is None:
        matar_arvore(processo)
        return
    kernel32 = _kernel32()
    kernel32.TerminateJobObject(arvore.job, CODIGO_DA_ARVORE_MORTA)
    _esperar_o_job_esvaziar(kernel32, arvore.job)
    kernel32.CloseHandle(arvore.job)
    processo.kill()


def matar_arvore(processo: subprocess.Popen[bytes]) -> None:
    """O processo e os descendentes dele, a partir do PID; o próprio processo morre de qualquer jeito."""
    if NO_WINDOWS:
        _matar_arvore_no_windows(processo.pid)
    else:
        _matar_grupo(processo.pid)
    processo.kill()


def _job_com(kernel32: Any, alca: int | None) -> int | None:
    """Um Job Object que mata a árvore ao fechar, com o processo dentro; None quando o Windows não o cria ou não
    aceita o processo."""
    job = kernel32.CreateJobObjectW(None, None) if alca else None
    if job:
        _matar_ao_fechar(kernel32, job)
    if job and kernel32.AssignProcessToJobObject(job, alca):
        return int(job)
    if job:
        kernel32.CloseHandle(job)
    return None


def _matar_ao_fechar(kernel32: Any, job: int) -> bool:
    """Liga no job o `KILL_ON_JOB_CLOSE`: quando a última alça fecha, até na morte do orquestrador, a árvore morre.

    Sem ele (o Windows recusou), o job ainda mata a árvore no fim da sessão;
    só a queda do orquestrador escapa.
    """
    limites = _LimitesDoJob(flags=MATAR_AO_FECHAR_O_JOB)
    return bool(kernel32.SetInformationJobObject(job, LIMITES_DO_JOB, ctypes.byref(limites), ctypes.sizeof(limites)))


def _esperar_o_job_esvaziar(kernel32: Any, job: int) -> None:
    """Até nenhum processo do job seguir ativo, ou o prazo acabar: a morte pelo job não é instantânea."""
    contabilidade = _ContabilidadeDoJob()
    limite = time.monotonic() + TEMPO_PARA_O_JOB_ESVAZIAR_S
    while time.monotonic() < limite:
        lida = kernel32.QueryInformationJobObject(job, CONTABILIDADE_DO_JOB, ctypes.byref(contabilidade),
                                                  ctypes.sizeof(contabilidade), None)
        if not lida or contabilidade.ativos == 0:
            return
        time.sleep(0.05)


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


def _kernel32() -> Any:
    """O kernel32 do Windows com os protótipos do job e do processo."""
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                                   wintypes.LPVOID)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return kernel32


def _ntdll() -> Any:
    """O ntdll do Windows com o `NtResumeProcess`, que solta todas as threads do processo nascido suspenso."""
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return ntdll
