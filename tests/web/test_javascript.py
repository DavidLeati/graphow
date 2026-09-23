"""Roda os testes JavaScript do canvas pela suíte do pytest.

O canvas não tinha teste nenhum: os testes de `tests/web` exercitam o servidor,
e uma sessão de mil nós saía do arranjo com y na casa de 7e12 sem que nada
quebrasse. Os testes ficam em `tests/web/js` e usam só o `node:test` da
biblioteca padrão do Node; sem Node no PATH, este teste é pulado.
"""

from pathlib import Path
import shutil
import subprocess

import pytest

PASTA_DOS_TESTES_JS: Path = Path(__file__).parent / "js"
SEGUNDOS_ATE_DESISTIR: int = 120


def test_testes_javascript_do_canvas_passam() -> None:
    """`node --test` sobre cada arquivo `.test.mjs` da pasta termina sem falha."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js ausente no PATH")
    arquivos = sorted(str(caminho) for caminho in PASTA_DOS_TESTES_JS.glob("*.test.mjs"))
    assert arquivos, "nenhum teste JavaScript encontrado"

    execucao = subprocess.run(
        [node, "--test", *arquivos], capture_output=True, text=True, timeout=SEGUNDOS_ATE_DESISTIR, check=False
    )

    assert execucao.returncode == 0, execucao.stdout + execucao.stderr
