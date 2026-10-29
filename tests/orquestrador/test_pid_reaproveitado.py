"""A trava do Goal com PID reaproveitado: o dono vive se o PID vive com a mesma hora de criação.

Depois de um boot, o PID da trava pode ser de outro processo vivo (sonda T1 da
revisão da T3b): a chamada parava e mandava encerrar o PID, que era de outro.
O processo vivo aqui é um que o próprio teste cria, e só ele é encerrado no fim.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from graphow.orquestrador.trava_do_goal import NOME_DA_TRAVA, GoalOcupado, conduzindo, hora_de_criacao, ler_dono, tomar_trava

INICIO_ANTES_DO_BOOT: str = "2026-10-28T23:59:00-03:00"


@contextmanager
def _processo_vivo() -> Iterator[subprocess.Popen[bytes]]:
    """Um processo deste teste, vivo durante o bloco e encerrado no fim (só ele)."""
    outro = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        yield outro
    finally:
        outro.kill()
        outro.wait()


def _trava_de(pasta: Path, pid: int, *, criacao: float | None, inicio: str = INICIO_ANTES_DO_BOOT) -> None:
    """A trava de outra execução desta máquina, com o PID, a hora de criação e o início dados."""
    pasta.mkdir(parents=True, exist_ok=True)
    dono = {"pid": pid, "maquina": socket.gethostname(), "inicio": inicio, "comando": "graphow orquestrar --goal goal-x",
            "ficha": "antes-do-boot", **({} if criacao is None else {"criacao": criacao})}
    (pasta / NOME_DA_TRAVA).write_text(json.dumps(dono), encoding="utf-8")


def test_trava_de_pid_vivo_com_outra_hora_de_criacao_e_liberada_como_velha_edge_case(tmp_path: Path) -> None:
    """T3a2.4: o PID da trava é de um processo vivo, criado em outra hora: a trava é liberada com aviso, e ele segue vivo."""
    with _processo_vivo() as outro:
        criacao = hora_de_criacao(outro.pid)
        assert criacao is not None
        _trava_de(tmp_path / "goal-x", outro.pid, criacao=criacao - 3600)

        with conduzindo(tmp_path / "goal-x", "goal-x") as trava:
            assert trava.aviso.startswith(f"Aviso: a trava do Goal goal-x era do PID {outro.pid} ")
            assert "cujo PID hoje e de outro processo" in trava.aviso
            assert ler_dono(trava.caminho) == trava.dono
        assert outro.poll() is None


def test_trava_do_mesmo_processo_com_a_mesma_hora_segue_valendo_nominal(tmp_path: Path) -> None:
    """T3a2.4, contraprova: o PID vivo com a mesma hora de criação é o dono, e a chamada para dizendo quem encerrar."""
    with _processo_vivo() as outro:
        _trava_de(tmp_path / "goal-x", outro.pid, criacao=hora_de_criacao(outro.pid))

        with pytest.raises(GoalOcupado, match=f"encerre o PID {outro.pid}"):
            tomar_trava(tmp_path / "goal-x", "goal-x")


def test_trava_sem_hora_de_processo_criado_depois_dela_e_liberada_edge_case(tmp_path: Path) -> None:
    """A trava de antes da hora (só PID e início): o processo do PID criado depois do início não é o dono (sonda T1)."""
    with _processo_vivo() as outro:
        _trava_de(tmp_path / "goal-x", outro.pid, criacao=None)
        with conduzindo(tmp_path / "goal-x", "goal-x") as trava:
            assert "cujo PID hoje e de outro processo" in trava.aviso

    agora = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    _trava_de(tmp_path / "goal-y", os.getpid(), criacao=None, inicio=agora)
    with pytest.raises(GoalOcupado, match=f"encerre o PID {os.getpid()}"):
        tomar_trava(tmp_path / "goal-y", "goal-y")


def test_trava_tomada_guarda_a_hora_de_criacao_do_processo_nominal(tmp_path: Path) -> None:
    """A trava nova leva a hora de criação deste processo, a mesma que o sistema dá para o PID dele."""
    with conduzindo(tmp_path / "goal-x", "goal-x") as trava:
        gravada = json.loads(trava.caminho.read_text(encoding="utf-8"))
    criacao = hora_de_criacao(os.getpid())
    assert criacao is not None and gravada["criacao"] == pytest.approx(criacao, abs=0.01)
    assert criacao <= datetime.now(timezone.utc).timestamp()
