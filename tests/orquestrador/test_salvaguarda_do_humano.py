"""T3a7, item 3: a salvaguarda fica fora do repositório do humano e a recuperação sobrevive ao `git gc --prune=now`."""

import base64
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from graphow.orquestrador.conferencia_do_humano import conferir_o_humano
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao
from graphow.orquestrador.suite import shell_dos_agentes

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada
from tests.orquestrador.test_foto_do_humano import _notas_do_humano
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TRABALHO: str = "TRABALHO DO HUMANO, NAO COMMITADO\n"
PREPARADO: str = "no indice, pelo git add\n"
RASCUNHO: bytes = b"rascunho solto\r\ncom CRLF\r\n"
COMANDO_IMPRESSO: re.Pattern[str] = re.compile(r"`(git -C [^`]+)`")
# A sessão que apaga o trabalho do humano e poda os objetos soltos dele: `reset --hard`, o não rastreado e o `gc`, com o
# git sem a trava do ambiente (o hook dela recusaria o `pack-refs` do `gc`).
SESSAO_QUE_PODA: str = (
    "import os, subprocess\nh = {h!r}\n"
    "sem_trava = {{nome: valor for nome, valor in os.environ.items() if not nome.startswith('GIT_CONFIG')}}\n"
    "subprocess.run(['git', '-C', h, 'reset', '-q', '--hard'], check=True, env=sem_trava)\n"
    "os.remove(os.path.join(h, 'rascunho.txt'))\n"
    "subprocess.run(['git', '-C', h, 'gc', '-q', '--prune=now'], check=True, env=sem_trava)\n"
)


def _no_git_bash(comando: str) -> None:
    """O comando colado no Git Bash."""
    shell = shell_dos_agentes()
    if shell is None:
        pytest.skip("sem bash na maquina")
    subprocess.run([str(shell), "-c", comando], check=True, capture_output=True)


def _no_powershell(comando: str) -> None:
    """O comando colado no PowerShell, tal como está (o `-EncodedCommand` não passa pelas aspas da linha de comando)."""
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("sem PowerShell na maquina")
    codificado = base64.b64encode(comando.encode("utf-16-le")).decode("ascii")
    subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado], check=True, capture_output=True)


@pytest.mark.parametrize("colar", [_no_git_bash, _no_powershell], ids=["git_bash", "powershell"])
def test_comando_impresso_recupera_os_tres_depois_do_gc_edge_case(tmp_path: Path, colar: object) -> None:
    """T3a7.2 (F9): com uma mudança no índice, outra só na árvore e um não rastreado, a sessão faz `reset --hard`, apaga o
    não rastreado e roda `gc --prune=now`, que poda o blob do `git add`. O laço para, a pasta da salvaguarda fica, e os
    comandos que a parada imprime, colados no shell, devolvem os três."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    h = bancada.repositorio
    (h / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (h / "preparado.txt").write_text(PREPARADO, encoding="utf-8", newline="\n")
    git(h, "add", "preparado.txt")
    (h / "rascunho.txt").write_bytes(RASCUNHO)
    blob_do_add = git(h, "rev-parse", ":preparado.txt").strip()
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", SESSAO_QUE_PODA.format(h=str(h))]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, h, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert bancada.chamadas("executor")[0]["comandos"][0]["codigo"] == 0, "a sessao rodou o reset, o rm e o gc"
    assert subprocess.run(["git", "-C", str(h), "cat-file", "-e", blob_do_add], capture_output=True, check=False).returncode != 0
    (nota,) = _notas_do_humano(bancada)
    pasta = Path(str(nota.obter_propriedade("guardada_em")))
    assert pasta.is_dir() and pasta.parent.parent == bancada.raiz / "estado" and pasta.name == "salvaguarda-do-humano", pasta
    assert not pasta.is_relative_to(h) and (pasta.parent / "area").is_dir(), "ao lado do clone, fora dele e do humano"
    comandos = COMANDO_IMPRESSO.findall(parada.mensagem)
    assert [comando.split(" ")[3] for comando in comandos] == ["fetch", "stash", "restore"], comandos
    for comando in comandos:
        colar(comando)  # type: ignore[operator]
    assert (h / "README.md").read_text(encoding="utf-8") == TRABALHO
    assert (h / "preparado.txt").read_text(encoding="utf-8") == PREPARADO
    assert (h / "rascunho.txt").read_bytes() == RASCUNHO


def _listagem(pasta: Path) -> dict[str, tuple[int, int]]:
    """Cada arquivo e pasta debaixo da pasta, com o tamanho e o mtime em nanossegundos."""
    return {item.relative_to(pasta).as_posix(): (os.stat(item).st_size if item.is_file() else 0, os.stat(item).st_mtime_ns)
            for item in pasta.rglob("*")}


def test_foto_de_um_repositorio_sujo_nao_cria_nem_muda_arquivo_no_git_do_humano_nominal(tmp_path: Path) -> None:
    """T3a7.4: a foto de antes (com a salvaguarda dos rastreados, dos não rastreados e do não rastreado igual a um objeto do
    humano) e a de depois não criam nem mudam arquivo nenhum no `.git` do humano: nem objeto, nem índice, nem data."""
    repositorio = criar_repositorio(tmp_path / "humano", {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n", "docs/a.txt": "a\n"})
    git(repositorio, "gc", "-q")
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text(PREPARADO, encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt")
    (repositorio / "rascunho.txt").write_bytes(RASCUNHO)
    shutil.copyfile(repositorio / "README.md", repositorio / "copia.txt")
    antes = _listagem(repositorio / ".git")

    foto = foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda")
    conferir_o_humano(foto, "executor", "")

    assert foto is not None and foto.salvaguarda.stash and foto.salvaguarda.soltos
    assert _listagem(repositorio / ".git") == antes
    assert list((tmp_path / "salvaguarda" / "objects" / "pack").glob("*.pack")), "o pack do que o stash alcanca e o HEAD nao"
