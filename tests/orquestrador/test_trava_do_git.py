"""A trava do git nas sessões de agente: o clone do Goal volta a ser o que era, e o repositório do humano não é tocado."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.git_do_goal import AreaDoGoal, GitDoGoal, preparar_area
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.trava_do_git import fotografar_clone, instalar_trava, regras_que_negam_git, restaurar_o_clone
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

RAMO: str = "graphow/teste"


def _montar(tmp_path: Path) -> tuple[Path, Path, dict[str, str], str]:
    """O repositório do humano (com feature-humano e uma tag), o clone do Goal, o ambiente do agente e o -c que fura o hook."""
    repositorio = criar_repositorio(tmp_path / "repo")
    git(repositorio, "branch", "feature-humano")
    git(repositorio, "tag", "v0-humano")
    area = tmp_path / "areas" / "teste"
    preparar_area(AreaDoGoal(repositorio, area, RAMO, "main"))
    (tmp_path / "vazia").mkdir()
    ambiente = {**os.environ, **instalar_trava(tmp_path / "trava")}
    return repositorio, area, ambiente, f"core.hooksPath={(tmp_path / 'vazia').as_posix()}"


def _agente(area: Path, ambiente: dict[str, str], *argumentos: str) -> subprocess.CompletedProcess[str]:
    """O git como o agente o roda, no clone e com o ambiente da sessão."""
    return subprocess.run(["git", *argumentos], cwd=area, env=ambiente, capture_output=True, text=True, check=False)


def _refs(pasta: Path) -> str:
    """Todas as refs da pasta, com o objeto de cada uma."""
    return git(pasta, "for-each-ref", "--format=%(refname) %(objectname)")


def test_clone_nao_enxerga_ref_remoto_nem_hook_do_humano_nominal(tmp_path: Path) -> None:
    """O clone tem só a branch do Goal e a base: nem a branch e a tag do humano, nem remoto, alternates, reflog ou hook."""
    repositorio, area, _, _ = _montar(tmp_path)

    assert git(area, "for-each-ref", "--format=%(refname)").split() == [f"refs/heads/{RAMO}", "refs/heads/main"]
    assert git(area, "remote").strip() == ""
    assert not (area / ".git" / "objects" / "info" / "alternates").exists()
    assert not (area / ".git" / "logs").exists() and list((area / ".git" / "hooks").iterdir()) == []
    assert git(repositorio, "rev-parse", RAMO).strip() == GitDoGoal(area).head()


def test_o_que_o_agente_faz_no_clone_volta_e_o_humano_nao_muda_nominal(tmp_path: Path) -> None:
    """Por cima do hook, o agente commita, cria tag e branch, move a base, põe remoto, troca a identidade e planta um hook."""
    repositorio, area, ambiente, vazia = _montar(tmp_path)
    do_humano = _refs(repositorio)
    foto = fotografar_clone(area)
    (area / "x.txt").write_text("x\n", encoding="utf-8")
    _agente(area, ambiente, "add", "x.txt")
    for comando in (("commit", "-q", "-m", "do agente"), ("tag", "v-agente"), ("branch", "do-agente"),
                    ("update-ref", "refs/heads/main", "HEAD"), ("remote", "add", "fora", "https://exemplo.invalid/r.git"),
                    ("config", "user.email", "disfarce@exemplo.invalid")):
        assert _agente(area, ambiente, "-c", vazia, *comando).returncode == 0, comando
    (area / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    desfeito = restaurar_o_clone(foto)

    assert {nome: objeto for nome, objeto in (linha.split() for linha in _refs(area).splitlines())} == dict(foto.refs)
    assert GitDoGoal(area).mudancas() == ("A  x.txt",)
    assert (area / ".git" / "config").read_bytes() == foto.configuracao
    assert list((area / ".git" / "hooks").iterdir()) == []
    assert "refs/tags/v-agente" in desfeito and "refs/heads/do-agente" in desfeito and "reset --soft" in desfeito
    assert _refs(repositorio) == do_humano


def test_o_que_o_humano_faz_durante_a_sessao_fica_como_ele_deixou_nominal(tmp_path: Path) -> None:
    """Commit noutra branch sem reflog, tags, configuração, remoto, branch apagada e stash: nada disso é desfeito."""
    repositorio, area, _, _ = _montar(tmp_path)
    git(repositorio, "config", "core.logAllRefUpdates", "false")
    git(repositorio, "branch", "lixo")
    foto = fotografar_clone(area)
    git(repositorio, "checkout", "-q", "feature-humano")
    (repositorio / "h.txt").write_text("do humano\n", encoding="utf-8")
    git(repositorio, "add", "h.txt")
    git(repositorio, "commit", "-q", "-m", "commit do humano")
    git(repositorio, "checkout", "-q", "main")
    for comando in (("tag", "v1-humano"), ("tag", "-a", "v2-humano", "-m", "release"), ("tag", "-f", "v0-humano", "feature-humano"),
                    ("config", "user.name", "Nome Novo"), ("remote", "add", "origem", "https://exemplo.invalid/r.git"),
                    ("branch", "-D", "lixo")):
        git(repositorio, *comando)
    (repositorio / "README.md").write_text("rascunho do humano\n", encoding="utf-8")
    git(repositorio, "stash", "push", "-q", "-m", "meu rascunho")
    depois_do_humano = _refs(repositorio)

    assert restaurar_o_clone(foto) == ""

    assert _refs(repositorio) == depois_do_humano
    assert git(repositorio, "config", "user.name").strip() == "Nome Novo"
    assert git(repositorio, "remote").split() == ["origem"] and "meu rascunho" in git(repositorio, "stash", "list")


def test_push_do_agente_e_recusado_pelo_hook_nominal(tmp_path: Path) -> None:
    """O clone não tem remoto, e o `pre-push` da trava recusa até o push pelo caminho do repositório do humano."""
    repositorio, area, ambiente, _ = _montar(tmp_path)

    feito = _agente(area, ambiente, "push", str(repositorio), f"{RAMO}:refs/heads/do-agente")

    assert feito.returncode != 0
    assert "o agente nao faz push" in feito.stderr
    assert "refs/heads/do-agente" not in _refs(repositorio)


def test_regras_negam_as_opcoes_que_furavam_a_trava_edge_case() -> None:
    """Caso de borda: `git -c`, `git -C`, push, config e remote estão nas regras; leitura não está."""
    regras = regras_que_negam_git(("Bash",))

    assert {"Bash(git -c:*)", "Bash(git -C:*)", "Bash(git push:*)", "Bash(git config:*)", "Bash(git remote:*)"} <= set(regras)
    assert not [regra for regra in regras if any(leitura in regra for leitura in ("status", "diff", "log", "show"))]


def test_executor_disfarcado_que_mexe_nas_refs_nao_alcanca_o_humano_nem_gasta_tentativa_nominal(tmp_path: Path) -> None:
    """No laço: com outra identidade e por cima do hook, o agente cria refs no clone; elas somem, e o humano fica intacto."""
    roteiro = roteiro_farto()
    (tmp_path / "vazia").mkdir()
    vazia = f"core.hooksPath={(tmp_path / 'vazia').as_posix()}"
    script = (
        "import os, subprocess\n"
        "os.environ['GIT_COMMITTER_EMAIL'] = 'qualquer@exemplo.invalid'\n"
        f"subprocess.run(['git', '-c', r'{vazia}', 'update-ref', 'refs/heads/feature-humano', 'HEAD'], check=True)\n"
        f"subprocess.run(['git', '-c', r'{vazia}', 'tag', 'v-agente'], check=True)\n"
    )
    roteiro["executor"] = [executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", script]]), *roteiro["executor"]]
    bancada = montar_bancada(tmp_path / "laco", roteiro)
    git(bancada.repositorio, "branch", "feature-humano")
    do_humano = git(bancada.repositorio, "rev-parse", "feature-humano").strip()

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo"))

    assert parada.fechou, parada.mensagem
    assert bancada.chamadas("executor")[0]["comandos"][0]["codigo"] == 0
    assert git(bancada.repositorio, "rev-parse", "feature-humano").strip() == do_humano
    assert "v-agente" not in git(bancada.repositorio, "tag")
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and (estado.fatias[0].tentativas, estado.fatias[0].falhas) == (1, 0)


class ExecutorComHumano(ExecutorDeSessao):
    """Na sessão de número dado, o humano mexe no repositório dele antes de o agente responder."""

    def __init__(self, base: ExecutorDeSessao, acao: Any, na: int) -> None:
        super().__init__(base._executavel, base._ambiente)
        self._acao: Any = acao
        self._na: int = na
        self._contador: int = 0

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """A sessão roda depois da ação do humano, quando é a sessão marcada."""
        self._contador += 1
        if self._contador == self._na:
            self._acao()
        return super().rodar(pedido)


def test_commit_e_tag_do_humano_durante_a_sessao_sobrevivem_ao_laco_nominal(tmp_path: Path) -> None:
    """Durante a sessão do executor o humano commita noutra branch e cria uma tag; o Goal fecha e os dois ficam."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    repositorio = bancada.repositorio
    git(repositorio, "branch", "feature")
    feito: dict[str, str] = {}

    def humano() -> None:
        git(repositorio, "checkout", "-q", "feature")
        (repositorio / "h.txt").write_text("do humano\n", encoding="utf-8")
        git(repositorio, "add", "h.txt")
        git(repositorio, "commit", "-q", "-m", "commit do humano")
        feito["sha"] = git(repositorio, "rev-parse", "HEAD").strip()
        git(repositorio, "checkout", "-q", "main")
        git(repositorio, "tag", "-a", "v1-humano", "-m", "release do humano")

    executor = ExecutorComHumano(bancada.executor, humano, na=2)
    parada = bancada.orquestrador(executor=executor).iniciar_da_spec(bancada.spec, repositorio, OpcoesDoLaco(modo="autonomo"))

    assert parada.fechou, parada.mensagem
    assert git(repositorio, "rev-parse", "feature").strip() == feito["sha"]
    assert "v1-humano" in git(repositorio, "tag").split()
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [fatia.falhas for fatia in estado.fatias] == [0, 0]
