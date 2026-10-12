"""A trava do git nas sessões de agente: o push recusado e a conferência que desfaz o que escapou das regras."""

import os
from pathlib import Path
import subprocess

from graphow.orquestrador.git_do_goal import AreaDoGoal, GitDoGoal, preparar_area
from graphow.orquestrador.trava_do_git import conferir_o_git, fotografar, instalar_trava, regras_que_negam_git

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import executor_pronto, montar_bancada
from tests.orquestrador.test_retomada import TUDO, roteiro_farto


def _montar(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """O repositório do humano com a branch feature-humano, a área do Goal e o ambiente travado do agente."""
    repositorio = criar_repositorio(tmp_path / "repo")
    git(repositorio, "branch", "feature-humano")
    area = tmp_path / "areas" / "teste"
    preparar_area(AreaDoGoal(repositorio, area, "graphow/teste", "main"))
    (tmp_path / "vazia").mkdir()
    return repositorio, area, {**os.environ, **instalar_trava(tmp_path / "trava")}


def _agente(area: Path, ambiente: dict[str, str], *argumentos: str) -> subprocess.CompletedProcess[str]:
    """O git como o agente o roda, na área e com o ambiente da sessão."""
    return subprocess.run(["git", *argumentos], cwd=area, env=ambiente, capture_output=True, text=True, check=False)


def test_ref_do_humano_apagada_por_cima_da_trava_volta_e_reprova_nominal(tmp_path: Path) -> None:
    """`git -c core.hooksPath=<vazia> branch -D` passa pelo hook; a conferência recria a branch e diz o que houve."""
    repositorio, area, ambiente = _montar(tmp_path)
    antes = GitDoGoal(repositorio).rodar("rev-parse", "feature-humano").strip()
    foto = fotografar(area)

    feito = _agente(area, ambiente, "-c", f"core.hooksPath={(tmp_path / 'vazia').as_posix()}", "branch", "-D", "feature-humano")
    achados = conferir_o_git(foto, guarda=tmp_path / "guarda")

    assert feito.returncode == 0, feito.stderr
    assert len(achados) == 1 and "refs/heads/feature-humano foi apagada" in achados[0]
    assert GitDoGoal(repositorio).rodar("rev-parse", "feature-humano").strip() == antes


def test_commit_do_humano_durante_a_sessao_nao_e_desfeito_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o humano commita na main enquanto o agente trabalha; o reflog diz que foi ele, e nada volta."""
    repositorio, area, _ = _montar(tmp_path)
    foto = fotografar(area)
    (repositorio / "humano.txt").write_text("meu\n", encoding="utf-8")
    git(repositorio, "add", "humano.txt")
    git(repositorio, "commit", "-q", "-m", "Trabalho do humano")
    depois = GitDoGoal(repositorio).head()

    assert conferir_o_git(foto, guarda=tmp_path / "guarda") == ()
    assert GitDoGoal(repositorio).head() == depois


def test_tag_criada_e_remoto_acrescentado_pelo_agente_sao_desfeitos_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a tag nova some, a configuração volta à de antes e a mudada fica guardada."""
    repositorio, area, ambiente = _montar(tmp_path)
    vazia = f"core.hooksPath={(tmp_path / 'vazia').as_posix()}"
    foto = fotografar(area)

    _agente(area, ambiente, "-c", vazia, "tag", "do-agente")
    _agente(area, ambiente, "remote", "add", "fora", "https://exemplo.invalid/repo.git")
    achados = conferir_o_git(foto, guarda=tmp_path / "guarda")

    assert any("refs/tags/do-agente foi criada" in achado for achado in achados)
    assert any("configuracao do repositorio" in achado for achado in achados)
    assert GitDoGoal(repositorio).tentar("rev-parse", "--verify", "--quiet", "refs/tags/do-agente").codigo != 0
    assert GitDoGoal(repositorio).rodar("remote").strip() == ""
    assert "exemplo.invalid" in next((tmp_path / "guarda").iterdir()).read_text(encoding="utf-8")


def test_push_do_agente_e_recusado_pelo_hook_nominal(tmp_path: Path) -> None:
    """O `pre-push` da trava recusa o push, e o remoto não recebe nada."""
    repositorio, area, ambiente = _montar(tmp_path)
    remoto = tmp_path / "remoto.git"
    git(tmp_path, "init", "-q", "--bare", str(remoto))
    git(repositorio, "remote", "add", "origin", str(remoto))

    feito = _agente(area, ambiente, "push", "origin", "graphow/teste")

    assert feito.returncode != 0
    assert "o agente nao faz push" in feito.stderr
    assert git(remoto, "for-each-ref").strip() == ""


def test_regras_negam_as_opcoes_que_furavam_a_trava_edge_case() -> None:
    """Caso de borda: `git -c`, `git -C`, push, config e remote estão nas regras; leitura não está."""
    regras = regras_que_negam_git(("Bash",))

    assert {"Bash(git -c:*)", "Bash(git -C:*)", "Bash(git push:*)", "Bash(git config:*)", "Bash(git remote:*)"} <= set(regras)
    assert not [regra for regra in regras if any(leitura in regra for leitura in ("status", "diff", "log", "show"))]


def test_executor_que_apaga_branch_do_humano_falha_a_tentativa_e_a_branch_volta_nominal(tmp_path: Path) -> None:
    """No laço: a tentativa que furou a trava falha com o que fez, a branch do humano volta e a seguinte fecha a fatia."""
    roteiro = roteiro_farto()
    (tmp_path / "vazia").mkdir()
    vazia = f"core.hooksPath={(tmp_path / 'vazia').as_posix()}"
    roteiro["executor"] = [executor_pronto(dict(TUDO), comandos=[["git", "-c", vazia, "branch", "-D", "feature-humano"]]),
                           *roteiro["executor"]]
    bancada = montar_bancada(tmp_path / "laco", roteiro)
    git(bancada.repositorio, "branch", "feature-humano")
    antes = GitDoGoal(bancada.repositorio).rodar("rev-parse", "feature-humano").strip()

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo"))

    assert parada.fechou, parada.mensagem
    assert bancada.chamadas("executor")[0]["comandos"][0]["codigo"] == 0
    assert GitDoGoal(bancada.repositorio).rodar("rev-parse", "feature-humano").strip() == antes
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    primeira = estado.fatias[0]
    assert (primeira.tentativas, primeira.falhas) == (2, 1)
    assert "refs/heads/feature-humano foi apagada" in primeira.texto("ultimo_erro")
