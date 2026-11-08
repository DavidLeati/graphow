"""T3a10, item 1: o git do orquestrador, no clone e no humano, não roda o programa que uma configuração plantada aponta."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from graphow.orquestrador import git_do_goal
from graphow.orquestrador.contexto_do_laco import MotivoDaParada
from graphow.orquestrador.git_do_goal import SEM_CODIGO_PLANTADO, GitDoGoal, commitar

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada
from tests.orquestrador.test_arquivos_do_git import AUTONOMO, _parou_no_arquivo, _script_que_marca
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

# O script da sessão que planta, no clone (a pasta dela), um hook `reference-transaction` que grava o marcador, e cria
# uma ref que o orquestrador apaga depois da sessão (o `update-ref -d` roda o hook). argv: marcador e pasta dos hooks.
PLANTA_NO_CLONE: str = r'''
import pathlib, subprocess, sys
marca, pasta = sys.argv[1], pathlib.Path(sys.argv[2])
git = pathlib.Path(".git")
pasta.mkdir(parents=True, exist_ok=True)
hook = pasta / "reference-transaction"
hook.write_bytes(("#!/bin/sh\necho \"$PWD $1\" >> '" + marca + "'\n").encode())
hook.chmod(0o755)
if pasta.resolve() != (git / "hooks").resolve():
    with (git / "config").open("ab") as config:
        config.write(("[core]\n\thooksPath = " + pasta.as_posix() + "\n").encode())
alvo = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
(git / "refs" / "heads" / "intrusa").write_text(alvo + "\n")
'''
# O script da sessão que acrescenta à global (argv 1) o `core.fsmonitor` que roda o script dado (argv 2).
PLANTA_NA_GLOBAL: str = ("import pathlib, sys\np = pathlib.Path(sys.argv[1])\n"
                         "p.write_bytes(p.read_bytes() + (\"[core]\\n\\tfsmonitor = sh '\" + sys.argv[2] + \"'\\n\").encode())\n")


def _casa_falsa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A casa, o XDG e a global do git numa pasta do teste: o `~/.gitconfig` real nunca é lido nem escrito."""
    casa = tmp_path / "casa"
    (casa / "xdg").mkdir(parents=True)
    global_ = casa / "global.gitconfig"
    global_.write_bytes(f"[user]\n\tname = Teste\n\temail = teste@exemplo.invalid\n[graphow]\n\tcasa = {tmp_path.name}\n".encode())
    for nome, valor in {"HOME": casa, "USERPROFILE": casa, "XDG_CONFIG_HOME": casa / "xdg", "GIT_CONFIG_GLOBAL": global_}.items():
        monkeypatch.setenv(nome, str(valor))
    assert all(Path(os.environ[nome]).is_relative_to(tmp_path) for nome in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "GIT_CONFIG_GLOBAL"))
    assert git(tmp_path, "config", "--global", "--get", "graphow.casa").strip() == tmp_path.name, "a global e a do teste"
    return global_


def test_fsmonitor_plantado_na_global_para_o_laco_sem_rodar_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3a10.1 (S5): a sessão planta `core.fsmonitor` na global; o script devolve a global ao original, e em 8023db1 rodava
    duas vezes no git do orquestrador no clone, antes da conferência, e o Goal fechava. Agora o git do orquestrador não o
    roda (o marcador não existe), e a conferência para o laço pela global. Contraprova: o `git status` comum o roda."""
    global_ = _casa_falsa(tmp_path, monkeypatch)
    marca, original = tmp_path / "marca.txt", tmp_path / "original.gitconfig"
    original.write_bytes(global_.read_bytes())
    script = tmp_path / "fsmonitor.sh"
    script.write_bytes(f"#!/bin/sh\necho rodou >> '{marca.as_posix()}'\ncp '{original.as_posix()}' '{global_.as_posix()}'\nexit 1\n".encode())
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path / "b", roteiro)
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", PLANTA_NA_GLOBAL, str(global_), script.as_posix()]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert [c["codigo"] for c in bancada.chamadas("executor")[0]["comandos"]] == [0]
    _parou_no_arquivo(bancada, parada, Path(os.path.abspath(global_)).as_posix())
    assert not marca.exists(), "o fsmonitor plantado na global rodou pelo git do orquestrador"
    git(bancada.repositorio, "status")
    assert marca.exists(), "contraprova: o status comum roda o fsmonitor da global"


@pytest.mark.parametrize("onde", ["config_do_clone", "hooks_do_clone"])
def test_hook_plantado_no_clone_nao_roda_no_git_do_orquestrador_edge_case(tmp_path: Path, onde: str) -> None:
    """T3a10.1, a variante do clone: a sessão aponta o `core.hooksPath` do `.git/config` do clone (ou escreve em
    `.git/hooks`) para um `reference-transaction` e cria uma ref. Em 8023db1, o `update-ref -d` que a apaga rodava o hook,
    fora do job; agora não, e a restauração do clone segue (o Goal fecha)."""
    marca = tmp_path / "marca.txt"
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path / "b", roteiro)
    planta = tmp_path / "planta.py"
    planta.write_text(PLANTA_NO_CLONE, encoding="utf-8")
    pasta = str(tmp_path / "ganchos") if onde == "config_do_clone" else ".git/hooks"
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, str(planta), marca.as_posix(), pasta]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    (chamada,) = [c for c in bancada.chamadas("executor") if c["comandos"]]
    assert chamada["comandos"][0]["codigo"] == 0, chamada["comandos"]
    assert parada.motivo == MotivoDaParada.FECHADO, parada.mensagem
    assert not marca.exists(), marca.read_text(encoding="utf-8")


def test_todo_git_do_orquestrador_vai_sem_codigo_plantado_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada processo do `GitDoGoal` leva os `-c` (sem fsmonitor, sem assinatura) e o `core.hooksPath` numa pasta vazia na
    hora. O humano com `commit.gpgSign` e um `gpg.program` que marca: o commit sai sem assinatura e o programa não roda."""
    repositorio = criar_repositorio(tmp_path / "humano")
    marca = tmp_path / "marca.txt"
    git(repositorio, "config", "commit.gpgSign", "true")
    _script_que_marca(tmp_path, marca)
    git(repositorio, "config", "gpg.program", (tmp_path / "fsmonitor.sh").as_posix())
    original = subprocess.run
    chamados: list[tuple[list[str], list[bool]]] = []

    def conferir(comando: list[str], *args: Any, **kwargs: Any) -> Any:
        ganchos = [Path(parte.split("=", 1)[1]) for parte in comando if parte.startswith("core.hooksPath=")]
        chamados.append((comando[3:3 + len(SEM_CODIGO_PLANTADO)], [g.is_dir() and not any(g.iterdir()) for g in ganchos]))
        return original(comando, *args, **kwargs)

    monkeypatch.setattr(git_do_goal.subprocess, "run", conferir)
    (repositorio / "novo.txt").write_text("novo\n", encoding="utf-8")
    commitar(repositorio, "Commit do orquestrador")
    monkeypatch.undo()

    assert len(chamados) >= 3 and all(c == list(SEM_CODIGO_PLANTADO) and v == [True] for c, v in chamados), chamados
    assert not marca.exists() and "gpgsig" not in git(repositorio, "cat-file", "-p", "HEAD")
    feito = subprocess.run(["git", "-C", str(repositorio), "commit", "-q", "--allow-empty", "-m", "x"], capture_output=True, check=False)
    assert feito.returncode != 0 and marca.exists(), "contraprova: o commit comum roda o gpg.program"


def test_merge_ff_only_no_checkout_do_humano_nao_roda_o_hook_dele_nominal(tmp_path: Path) -> None:
    """O que muda para o humano: o `merge --ff-only` que integra o Goal no checkout dele não roda o `post-merge` dele."""
    repositorio = criar_repositorio(tmp_path / "humano")
    marca = tmp_path / "marca.txt"
    hook = repositorio / ".git" / "hooks" / "post-merge"
    hook.write_bytes(f"#!/bin/sh\necho rodou >> '{marca.as_posix()}'\n".encode())
    hook.chmod(0o755)
    git(repositorio, "switch", "-q", "-c", "goal")
    git(repositorio, "commit", "-q", "--allow-empty", "-m", "do Goal")
    git(repositorio, "switch", "-q", "main")

    GitDoGoal(repositorio).rodar("merge", "--ff-only", "goal")

    assert git(repositorio, "rev-parse", "main") == git(repositorio, "rev-parse", "goal") and not marca.exists()
    git(repositorio, "reset", "-q", "--hard", "HEAD~1")
    git(repositorio, "merge", "-q", "--ff-only", "goal")
    assert marca.exists(), "contraprova: o merge comum roda o post-merge"
