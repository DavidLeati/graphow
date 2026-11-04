"""T3a5.2 e T3a5.3: a foto do repositório do humano em volta de cada sessão, a camada que não lê o comando."""

from pathlib import Path
import sys

import pytest

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.foto_do_humano import diferencas, foto_antes_da_sessao, fotografar_o_humano
from graphow.orquestrador.suite import shell_dos_agentes

from tests.orquestrador.apoio_git import criar_repositorio, git, git_bytes
from tests.orquestrador.apoio_laco import Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TRABALHO: str = "TRABALHO DO HUMANO, NAO COMMITADO\n"


def _sujo(pasta: Path) -> Path:
    """O repositório do humano com mudança no índice, mudança fora dele e um arquivo não rastreado."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n"})
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text("no indice\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt")
    (repositorio / "rascunho.txt").write_text("solto\n", encoding="utf-8", newline="\n")
    return repositorio


def _estado(repositorio: Path) -> tuple[str, str, str, bytes]:
    """As refs, as entradas do índice, o status e os bytes do arquivo do índice."""
    return (git(repositorio, "for-each-ref"), git(repositorio, "ls-files", "-s"),
            git(repositorio, "--no-optional-locks", "status", "--porcelain=v2", "-uall"), (repositorio / ".git" / "index").read_bytes())


def _notas_do_humano(bancada: Bancada) -> list[NoGrafo]:
    """As Notes de repositório do humano mexido no livro-razão."""
    notas = bancada.kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    return [no for no in notas if no.obter_propriedade("acao") == "repositorio_do_humano_mexido"]


def test_foto_e_salvaguarda_nao_mudam_o_repositorio_do_humano_nominal(tmp_path: Path) -> None:
    """T3a5.3: a foto e o `stash create` deixam refs, índice (entradas e bytes) e status como estavam."""
    repositorio = _sujo(tmp_path / "humano")
    antes = _estado(repositorio)

    foto = foto_antes_da_sessao(repositorio)

    assert foto is not None and foto.salvaguarda
    assert _estado(repositorio) == antes
    assert diferencas(foto, fotografar_o_humano(repositorio)) == ()
    assert foto.itens["status NOTAS.txt"].startswith("1 .M") and foto.itens["status rascunho.txt"].startswith("?")
    assert "indice preparado.txt" in foto.itens and foto.itens["HEAD"].startswith("refs/heads/main ")


def test_foto_acusa_checkout_commit_indice_edicao_e_arquivo_solto_apagado_edge_case(tmp_path: Path) -> None:
    """T3a5.2: o `checkout -- .`, o commit, o `git add`, a nova edição do mudado e o não rastreado apagado mudam a foto."""
    repositorio = _sujo(tmp_path / "humano")
    foto = fotografar_o_humano(repositorio)
    (repositorio / "NOTAS.txt").write_text("outra edicao\n", encoding="utf-8", newline="\n")
    (repositorio / "rascunho.txt").unlink()
    (repositorio / "README.md").write_text("# outro\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "README.md")
    mudancas = diferencas(foto, fotografar_o_humano(repositorio))
    assert [mudanca.split(":")[0].split(" sumiu")[0].split(" apareceu")[0] for mudanca in mudancas] == [
        "indice README.md", "status NOTAS.txt", "status README.md", "status rascunho.txt"]

    git(repositorio, "checkout", "--", ".")
    git(repositorio, "commit", "-q", "-m", "commit no meio da sessao")

    mudancas = "\n".join(diferencas(foto, fotografar_o_humano(repositorio)))
    assert "HEAD:" in mudancas and "ref refs/heads/main:" in mudancas and "indice preparado.txt:" not in mudancas
    assert "status NOTAS.txt sumiu" in mudancas and "status preparado.txt sumiu" in mudancas


def test_salvaguarda_recupera_o_rastreado_e_deixa_o_solto_de_fora_edge_case(tmp_path: Path) -> None:
    """T3a5.2 e o limite: `git stash apply <salvaguarda>` devolve a mudança rastreada; o não rastreado não está nela."""
    repositorio = _sujo(tmp_path / "humano")
    foto = foto_antes_da_sessao(repositorio)
    assert foto is not None
    git(repositorio, "reset", "-q", "--hard")

    git(repositorio, "stash", "apply", "-q", foto.salvaguarda)

    assert (repositorio / "NOTAS.txt").read_text(encoding="utf-8") == TRABALHO
    assert (repositorio / "preparado.txt").read_text(encoding="utf-8") == "no indice\n"
    assert git(repositorio, "rev-list", "--parents", "-1", foto.salvaguarda).split()[1:] == [
        git(repositorio, "rev-parse", "HEAD").strip(), git(repositorio, "rev-parse", f"{foto.salvaguarda}^2").strip()]
    assert "rascunho.txt" not in git(repositorio, "ls-tree", "-r", "--name-only", foto.salvaguarda)
    assert git_bytes(repositorio, "stash", "list") == b"", "a salvaguarda nao vira ref"


def _limpa_o_humano(humano: Path) -> list[list[str]]:
    """O script que o agente grava e roda, por fora do hook: o `checkout -- .` no repositório do humano."""
    return [[sys.executable, "limpa.py"]]


def _pelo_git_bash(humano: Path) -> list[list[str]]:
    """O disfarce da sonda H1 rodado direto no Git Bash, sem o hook, com a trava no ambiente."""
    shell = shell_dos_agentes()
    if shell is None:
        pytest.skip("sem bash na maquina")
    return [[str(shell), "-c", f"gi$()t -C '{humano.as_posix()}' checkout -- ."]]


@pytest.mark.parametrize("comandos", [_limpa_o_humano, _pelo_git_bash])
def test_sessao_que_apaga_o_trabalho_do_humano_para_o_laco_com_a_salvaguarda_edge_case(tmp_path: Path, comandos: object) -> None:
    """T3a5.2: o executor roda `git -C <humano> checkout -- .` por fora do hook; o laço para em FALHA com
    `repositorio_do_humano_mexido` e o hash da salvaguarda, e `git stash apply` com ele devolve a mudança."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    script = f"import subprocess\nsubprocess.run(['git', '-C', r'{bancada.repositorio}', 'checkout', '--', '.'], check=True)\n"
    roteiro["executor"][0] = executor_pronto({**TUDO, "limpa.py": script}, comandos=comandos(bancada.repositorio))  # type: ignore[operator]
    bancada.trocar_roteiro(roteiro)
    (bancada.repositorio / "README.md").write_text(TRABALHO, encoding="utf-8", newline="\n")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert bancada.chamadas("executor")[0]["comandos"][0]["codigo"] == 0
    assert (bancada.repositorio / "README.md").read_text(encoding="utf-8") == "# brinquedo\n", "a sessao apagou o trabalho"
    (nota,) = _notas_do_humano(bancada)
    salvaguarda = str(nota.obter_propriedade("salvaguarda"))
    assert salvaguarda and salvaguarda in parada.mensagem and f"stash apply {salvaguarda}" in parada.mensagem
    assert nota.obter_propriedade("papel") == "executor" and any("status README.md sumiu" in mudanca for mudanca in nota.obter_propriedade("mudancas"))
    git(bancada.repositorio, "stash", "apply", "-q", salvaguarda)
    assert (bancada.repositorio / "README.md").read_text(encoding="utf-8") == TRABALHO


def test_sessoes_que_nao_mexem_no_humano_nao_param_e_o_trabalho_dele_fica_nominal(tmp_path: Path) -> None:
    """T3a5.3: com mudança no índice, fora dele e arquivo solto no repositório do humano, o Goal fecha sem parada."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    (bancada.repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    git(bancada.repositorio, "add", "NOTAS.txt")
    (bancada.repositorio / "rascunho.txt").write_text("solto\n", encoding="utf-8", newline="\n")
    indice = git(bancada.repositorio, "ls-files", "-s", "NOTAS.txt")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert _notas_do_humano(bancada) == []
    assert git(bancada.repositorio, "ls-files", "-s", "NOTAS.txt") == indice
    assert (bancada.repositorio / "rascunho.txt").read_text(encoding="utf-8") == "solto\n"
    assert git(bancada.repositorio, "status", "--porcelain", "-uall").splitlines() == ["A  NOTAS.txt", "?? rascunho.txt"]
