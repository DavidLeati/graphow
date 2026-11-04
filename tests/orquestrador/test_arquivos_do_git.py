"""T3a7, item 1: a conferência lê os arquivos que mudam o git antes de qualquer git, e a mudança neles para o laço."""

from collections.abc import Callable
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from graphow.orquestrador.conferencia_do_humano import RepositorioDoHumanoMexido, conferir_o_humano
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco, Parada
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_foto_do_humano import _notas_do_humano
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
SEM_CONFERIR: str = "a arvore e o indice nao foram conferidos"
# O que o humano já tinha antes do Goal.
Preparo = Callable[[Path], None]


def _git_na_sessao(*argumentos: str) -> str:
    """A linha do script da sessão que roda o git no repositório do humano (`h`)."""
    return f"subprocess.run(['git', '-C', str(h), *{list(argumentos)!r}], check=True)"


def _acrescenta(caminho: str, texto: str) -> str:
    """A linha do script da sessão que acrescenta o texto ao arquivo do humano, sem git."""
    return f"with (h / {caminho!r}).open('a', encoding='utf-8', newline='') as arquivo: arquivo.write({texto!r})"


def _rodar_a_sessao(tmp_path: Path, preparar: Preparo, acao: str) -> tuple[Bancada, Parada]:
    """O laço autônomo com o executor que roda a ação por um script Python, fora do hook; `h` é o repositório do humano."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    preparar(bancada.repositorio)
    script = f"import pathlib, subprocess\nh = pathlib.Path(r'{bancada.repositorio}')\n{acao}\n"
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", script]])
    bancada.trocar_roteiro(roteiro)
    return bancada, bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)


def _parou_no_arquivo(bancada: Bancada, parada: Parada, nome: str) -> None:
    """O laço parou em FALHA pelo arquivo do git, dizendo qual, sem conferir a árvore; a Note tem só ele como perda."""
    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert f"{nome} mudou" in parada.mensagem and SEM_CONFERIR in parada.mensagem, parada.mensagem
    (nota,) = _notas_do_humano(bancada)
    assert [perda.split(" (")[0] for perda in nota.obter_propriedade("perdas")] == [f"{nome} mudou"]


def _script_que_marca(pasta: Path, marca: Path) -> str:
    """O `core.fsmonitor` de F1: grava o marcador e sai com erro (sem resposta, o git segue sem ele)."""
    script = pasta / "fsmonitor.sh"
    script.write_text(f"#!/bin/sh\necho rodou >> '{marca.as_posix()}'\nexit 1\n", encoding="utf-8", newline="\n")
    return f"sh '{script.as_posix()}'"


def _nada(repositorio: Path) -> None:
    """O humano sem nada além do repositório da bancada."""


def _worktree_config(repositorio: Path) -> None:
    """O humano com `extensions.worktreeConfig` (o que o sparse-checkout liga)."""
    git(repositorio, "config", "extensions.worktreeConfig", "true")


@pytest.mark.parametrize(("preparar", "escopo", "nome"), [(_nada, [], ".git/config"),
                                                          (_worktree_config, ["--worktree"], ".git/config.worktree")],
                         ids=["config", "config_worktree"])
def test_fsmonitor_plantado_para_o_laco_sem_rodar_edge_case(tmp_path: Path, preparar: Preparo, escopo: list[str], nome: str) -> None:
    """T3a7.1 (F1): a sessão planta `core.fsmonitor` na configuração do humano, que o `git status` da foto de depois
    rodaria; o laço para pelo arquivo, e o script não roda: o marcador não existe. O `status` comum o roda."""
    marca = tmp_path / "marca.txt"
    fsmonitor = _script_que_marca(tmp_path, marca)
    bancada, parada = _rodar_a_sessao(tmp_path, preparar, _git_na_sessao("config", *escopo, "core.fsmonitor", fsmonitor))

    _parou_no_arquivo(bancada, parada, nome)
    assert not marca.exists(), "o fsmonitor plantado nao rodou"
    git(bancada.repositorio, "--no-optional-locks", "status")
    assert marca.exists(), "contraprova: o git status do humano o roda"


def _hooks_do_time(repositorio: Path) -> None:
    """O humano usa `core.hooksPath` numa pasta da árvore, commitada (husky, `.githooks/`)."""
    (repositorio / ".githooks").mkdir()
    (repositorio / ".githooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", ".githooks")
    git(repositorio, "commit", "-q", "-m", "Hooks do time")
    git(repositorio, "config", "core.hooksPath", ".githooks")


def _rascunho_solto(repositorio: Path) -> None:
    """O humano tem um não rastreado."""
    (repositorio / "rascunho.txt").write_text("solto do humano\n", encoding="utf-8", newline="\n")


def _dois_stashes(repositorio: Path) -> None:
    """O humano tem duas entradas no stash."""
    for texto in ("primeiro trabalho\n", "segundo trabalho\n"):
        (repositorio / "README.md").write_text(texto, encoding="utf-8", newline="\n")
        git(repositorio, "stash", "-q")


CASOS: list[tuple[str, Preparo, str, str]] = [
    ("f6_hook_do_hooks_path_da_arvore", _hooks_do_time, _acrescenta(".githooks/pre-commit", "echo agente > PWNED\n"),
     ".githooks/pre-commit"),
    ("f7_hooks_path_no_config_worktree", _worktree_config, _git_na_sessao("config", "--worktree", "core.hooksPath", "ganchos"),
     ".git/config.worktree"),
    ("f8_exclude_que_esconde_o_solto", _rascunho_solto, _acrescenta(".git/info/exclude", "rascunho.txt\n"), ".git/info/exclude"),
    ("f10_stash_drop_de_entrada_antiga", _dois_stashes, _git_na_sessao("stash", "drop", "-q", "stash@{1}"), ".git/logs/refs/stash"),
]


@pytest.mark.parametrize(("preparar", "acao", "nome"), [caso[1:] for caso in CASOS], ids=[caso[0] for caso in CASOS])
def test_arquivo_que_muda_o_git_para_o_laco_edge_case(tmp_path: Path, preparar: Preparo, acao: str, nome: str) -> None:
    """T3a7.3: o hook da pasta do `core.hooksPath` que o humano usa (F6), o `core.hooksPath` no `config.worktree` (F7),
    o `.git/info/exclude` que esconderia o solto da sessão seguinte (F8) e o reflog do stash sem a entrada antiga (F10):
    cada um para o laço, pelo nome do arquivo."""
    bancada, parada = _rodar_a_sessao(tmp_path, preparar, acao)

    _parou_no_arquivo(bancada, parada, nome)


def test_include_que_ainda_nao_existe_tambem_e_vigiado_e_a_parada_nao_roda_git_edge_case(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `include.path` e o `includeIf` relativos (ao arquivo que os inclui) que ainda não existem estão na lista da foto
    de antes; a sessão que cria um deles para a conferência, que não roda processo nenhum depois de achar a mudança."""
    repositorio = criar_repositorio(tmp_path / "humano")
    git(repositorio, "config", "include.path", "extra.cfg")
    git(repositorio, "config", f"includeIf.gitdir:{repositorio.as_posix()}/.path", "../condicional.cfg")
    foto = foto_antes_da_sessao(repositorio)
    assert foto is not None
    assert {".git/extra.cfg", "condicional.cfg"} <= set(foto.do_git) and foto.do_git[".git/extra.cfg"] == "ausente"
    (repositorio / "condicional.cfg").write_text("[core]\n\tfsmonitor = sh plantado.sh\n", encoding="utf-8", newline="\n")
    original = subprocess.run
    chamados: list[list[str]] = []

    def contar(comando: list[str], *args: Any, **kwargs: Any) -> Any:
        chamados.append(list(comando))
        return original(comando, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", contar)
    with pytest.raises(RepositorioDoHumanoMexido, match="condicional.cfg mudou"):
        conferir_o_humano(foto, "executor", "")

    assert chamados == []
