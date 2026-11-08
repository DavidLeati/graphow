"""T3a10, item 3: o comando com código do agente que o orquestrador roda (a suíte, o aceite) nasce na árvore das sessões, e
a árvore morre quando ele acaba, antes da conferência da janela."""

from pathlib import Path
import subprocess
import sys
import time

import pytest

from graphow.orquestrador.janela_do_humano import ConfiguracaoDaJanela, JanelaDoHumano
from graphow.orquestrador.suite import rodar_suite, shell_dos_agentes

from tests.orquestrador.apoio_git import criar_repositorio

pytestmark = pytest.mark.skipif(shell_dos_agentes() is None, reason="a maquina nao tem bash")

TRABALHO: str = "trabalho do humano\n"
# O filho que o código do agente deixa solto: avisa que nasceu, espera 4 s e desfaz o humano. argv: humano, nasceu, agiu.
FILHO: str = r'''
import pathlib, subprocess, sys, time
pathlib.Path(sys.argv[2]).write_text("nasceu")
time.sleep(4)
pathlib.Path(sys.argv[3]).write_text("agiu")
subprocess.run(["git", "-C", sys.argv[1], "checkout", "--", "."])
'''
# O comando da suíte: solta o filho (no Windows, DETACHED_PROCESS e CREATE_NEW_PROCESS_GROUP), espera ele nascer e sai.
LANCA: str = r'''
import os, pathlib, subprocess, sys, time
soltura = {"creationflags": 0x8 | 0x200} if os.name == "nt" else {}
subprocess.Popen([sys.executable, *sys.argv[1:]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True, **soltura)
limite = time.monotonic() + 20
while not pathlib.Path(sys.argv[3]).exists() and time.monotonic() < limite:
    time.sleep(0.05)
'''


def _esperar_por(arquivo: Path, segundos: float) -> bool:
    """O arquivo apareceu dentro do prazo."""
    limite = time.monotonic() + segundos
    while not arquivo.exists() and time.monotonic() < limite:
        time.sleep(0.1)
    return arquivo.exists()


def test_filho_solto_da_suite_morre_antes_da_conferencia_edge_case(tmp_path: Path) -> None:
    """T3a10.2 (S4): a suíte solta um filho que, 4 s depois, faz `git -C <humano> checkout -- .`. Em 8023db1 a janela
    fechava sem perda e o trabalho sumia depois dela. Agora o filho morre com a árvore da suíte, antes da conferência:
    ele nasceu, não agiu, e o trabalho fica. Contraprova: o mesmo comando fora da suíte age."""
    repositorio = criar_repositorio(tmp_path / "humano", {"NOTAS.txt": "v1\n"})
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (tmp_path / "area").mkdir()
    (tmp_path / "filho.py").write_text(FILHO, encoding="utf-8")
    (tmp_path / "lanca.py").write_text(LANCA, encoding="utf-8")
    nasceu, agiu = tmp_path / "nasceu", tmp_path / "agiu"
    argumentos = [Path(sys.executable).as_posix(), *(p.as_posix() for p in (tmp_path / "lanca.py", tmp_path / "filho.py", repositorio))]
    janela = JanelaDoHumano(ConfiguracaoDaJanela(repositorio, tmp_path / "salvaguarda"))

    with janela.trecho("a suite que o orquestrador rodou"):
        suite = rodar_suite(tmp_path / "area", " ".join(f"'{a}'" for a in (*argumentos, nasceu.as_posix(), agiu.as_posix())),
                            tmp_path / "descartavel.db")

    assert suite.passou and nasceu.exists(), suite.descrever()
    assert not _esperar_por(agiu, 8.0), "o filho solto da suite sobreviveu a ela"
    assert (repositorio / "NOTAS.txt").read_text(encoding="utf-8") == TRABALHO
    subprocess.run([*argumentos, (tmp_path / "nasceu2").as_posix(), (tmp_path / "agiu2").as_posix()], check=True)
    assert _esperar_por(tmp_path / "agiu2", 15.0), "contraprova: fora da suite, o filho solto age"
