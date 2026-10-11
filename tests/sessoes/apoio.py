"""Apoio dos testes que rodam sessões: o `claude -p` falso e o que ele registrou."""

import ctypes
import json
import os
from pathlib import Path
import stat
import sys
import time

CLAUDE_FALSO: Path = Path(__file__).parent / "claude_falso.py"
SINCRONIZAR_E_CONSULTAR: int = 0x00100000 | 0x1000
ESPERA_ESGOTADA: int = 0x102
STREAM_DA_ENXUTA: Path = Path(__file__).parent / "dados" / "stream_enxuta.jsonl"


def comando_do_falso() -> tuple[str, ...]:
    """O executável falso como prefixo de comando: o interpretador e o script."""
    return (sys.executable, str(CLAUDE_FALSO))


def criar_executavel_falso(pasta: Path) -> Path:
    """Um arquivo executável que roda o falso, para apontar `GRAPHOW_CLAUDE` para ele.

    No Windows é um `.cmd`; no resto, um script de shell com permissão de execução.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        caminho = pasta / "claude.cmd"
        caminho.write_text(f'@"{sys.executable}" "{CLAUDE_FALSO}" %*\r\n', encoding="utf-8")
        return caminho
    caminho = pasta / "claude"
    caminho.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{CLAUDE_FALSO}" "$@"\n', encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)
    return caminho


def ambiente_de_teste(registro: Path, **extras: str) -> dict[str, str]:
    """O ambiente da máquina com a pasta de registro do falso e uma variável da sessão mãe."""
    registro.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "GRAPHOW_TESTE_REGISTRO": str(registro), "CLAUDE_CODE_ENTRYPOINT": "teste", **extras}


def chamadas_registradas(registro: Path) -> list[dict[str, object]]:
    """O que o falso recebeu em cada chamada, na ordem em que os arquivos foram gravados."""
    arquivos = sorted(registro.glob("*.json"), key=lambda caminho: caminho.stat().st_mtime_ns)
    return [json.loads(arquivo.read_text(encoding="utf-8")) for arquivo in arquivos]


def processo_vivo(pid: int) -> bool:
    """O processo existe e não terminou; no Windows, pelo handle do processo, sem sinal nenhum."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SINCRONIZAR_E_CONSULTAR, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == ESPERA_ESGOTADA
    finally:
        kernel32.CloseHandle(handle)


def esperar_fim(pid: int, segundos: float = 5.0) -> bool:
    """Se o processo terminou dentro do prazo: a morte da árvore não é instantânea."""
    limite = time.monotonic() + segundos
    while processo_vivo(pid) and time.monotonic() < limite:
        time.sleep(0.1)
    return not processo_vivo(pid)
