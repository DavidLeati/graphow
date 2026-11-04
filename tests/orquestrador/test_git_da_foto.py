"""T3a7, item 2: o git da foto e da salvaguarda não roda o fsmonitor nem os hooks do repositório do humano."""

from pathlib import Path
import subprocess
from typing import Any

import pytest

from graphow.orquestrador.conferencia_do_humano import conferir_o_humano
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao

from tests.orquestrador.apoio_git import criar_repositorio, git


def _sujo(pasta: Path) -> Path:
    """O repositório com mudança no índice, mudança fora dele e um não rastreado: a salvaguarda roda inteira."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n"})
    (repositorio / "NOTAS.txt").write_text("trabalho\n", encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text("no indice\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt")
    (repositorio / "rascunho.txt").write_text("solto\n", encoding="utf-8", newline="\n")
    return repositorio


def _script_que_marca(pasta: Path, marca: Path) -> Path:
    """Um script de shell que acrescenta uma linha ao marcador e sai com erro (o fsmonitor sem resposta)."""
    script = pasta / "marca.sh"
    script.write_text(f"#!/bin/sh\necho rodou >> '{marca.as_posix()}'\nexit 1\n", encoding="utf-8", newline="\n")
    return script


def test_foto_nao_roda_o_fsmonitor_nem_o_hook_que_o_humano_ja_tem_edge_case(tmp_path: Path) -> None:
    """O `core.fsmonitor` e o hook `post-index-change` do humano, que o `status` e a cópia do índice da salvaguarda
    rodariam, ficam parados na foto de antes e na de depois; o mesmo git sem o `-c` os roda."""
    repositorio = _sujo(tmp_path / "humano")
    marca_do_fsmonitor, marca_do_hook = tmp_path / "fsmonitor.txt", tmp_path / "hook.txt"
    git(repositorio, "config", "core.fsmonitor", f"sh '{_script_que_marca(tmp_path, marca_do_fsmonitor).as_posix()}'")
    hook = repositorio / ".git" / "hooks" / "post-index-change"
    hook.write_text(f"#!/bin/sh\necho rodou >> '{marca_do_hook.as_posix()}'\n", encoding="utf-8", newline="\n")

    foto = foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda")
    conferir_o_humano(foto, "executor", "")

    assert foto is not None and foto.salvaguarda.stash and foto.salvaguarda.soltos
    assert not marca_do_fsmonitor.exists() and not marca_do_hook.exists()
    git(repositorio, "--no-optional-locks", "status")
    git(repositorio, "update-index", "-q", "--refresh")
    assert marca_do_fsmonitor.exists() and marca_do_hook.exists(), "contraprova: sem o -c, os dois rodam"


def test_o_menos_c_da_foto_chega_ao_git_do_submodulo_edge_case(tmp_path: Path) -> None:
    """O `status` da foto roda um git dentro do submódulo sujo; o `core.fsmonitor` plantado na configuração do submódulo,
    que a foto não lê, fica parado, porque o `-c` chega a esse git. O `status` sem o `-c` o roda."""
    sub = criar_repositorio(tmp_path / "sub", {"lib.txt": "lib\n"})
    repositorio = criar_repositorio(tmp_path / "humano")
    git(repositorio, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "sub")
    git(repositorio, "commit", "-q", "-m", "Submodulo")
    (repositorio / "sub" / "lib.txt").write_text("trabalho no submodulo\n", encoding="utf-8", newline="\n")
    marca = tmp_path / "fsmonitor.txt"
    git(repositorio / "sub", "config", "core.fsmonitor", f"sh '{_script_que_marca(tmp_path, marca).as_posix()}'")

    foto = foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda")
    conferir_o_humano(foto, "executor", "")

    assert foto is not None and "sub" in foto.listados, "o status olhou dentro do submodulo"
    assert not marca.exists()
    git(repositorio, "--no-optional-locks", "status")
    assert marca.exists(), "contraprova: o status sem o -c roda o fsmonitor do submodulo"


def test_todo_git_da_foto_e_da_salvaguarda_vai_sem_fsmonitor_e_com_hooks_numa_pasta_vazia_nominal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada processo do git da foto e da salvaguarda leva `-c core.fsmonitor=false`, `-c core.hooksPath=` com uma pasta
    vazia na hora e `--no-optional-locks`."""
    repositorio = _sujo(tmp_path / "humano")
    original = subprocess.run
    chamados: list[list[str]] = []
    vazias: list[bool] = []

    def conferir(comando: list[str], *args: Any, **kwargs: Any) -> Any:
        chamados.append(list(comando))
        ganchos = [parte.split("=", 1)[1] for parte in comando if parte.startswith("core.hooksPath=")]
        vazias.append(len(ganchos) == 1 and Path(ganchos[0]).is_dir() and not any(Path(ganchos[0]).iterdir()))
        return original(comando, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", conferir)
    conferir_o_humano(foto_antes_da_sessao(repositorio, salvaguarda=tmp_path / "salvaguarda"), "executor", "")

    assert len(chamados) >= 12 and all(vazias), chamados
    assert all(comando[3:6:2] == ["-c", "-c"] and comando[4] == "core.fsmonitor=false" and "--no-optional-locks" in comando
               for comando in chamados), chamados
