"""T3a5 e T3a6: a foto do repositório do humano em volta de cada sessão; a perda para o laço, o avanço segue."""

from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pytest

from graphow.core.models import NoGrafo
from graphow.core.types import TipoNo
from graphow.orquestrador.conferencia_do_humano import conferir_as_fotos, conferir_o_humano
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao, fotografar_o_humano
from graphow.orquestrador.refs_do_humano import integrar_por_fast_forward
from graphow.orquestrador.suite import shell_dos_agentes

from tests.orquestrador.apoio_git import criar_repositorio, git, git_bytes
from tests.orquestrador.apoio_laco import Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_retomada import TUDO, roteiro_farto
from tests.orquestrador.test_trava_do_git import ExecutorComHumano

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TRABALHO: str = "TRABALHO DO HUMANO, NAO COMMITADO\n"
RASCUNHO: bytes = b"rascunho solto\r\ncom CRLF\r\n"
HASH: re.Pattern[str] = re.compile(r"\b[0-9a-f]{40,64}\b")


def _sujo(pasta: Path) -> Path:
    """O repositório do humano com mudança no índice, mudança fora dele e um arquivo não rastreado."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n"})
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text("no indice\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt")
    (repositorio / "rascunho.txt").write_bytes(RASCUNHO)
    return repositorio


def _estado(repositorio: Path) -> tuple[str, str, str, bytes]:
    """As refs, as entradas do índice, o status e os bytes do arquivo do índice."""
    return (git(repositorio, "for-each-ref"), git(repositorio, "ls-files", "-s"),
            git(repositorio, "--no-optional-locks", "status", "--porcelain=v2", "-uall"), (repositorio / ".git" / "index").read_bytes())


def _notas_do_humano(bancada: Bancada, acao: str = "repositorio_do_humano_mexido") -> list[NoGrafo]:
    """As Notes do repositório do humano (o que perdeu trabalho, por padrão) no livro-razão."""
    notas = bancada.kernel.obter_view().listar_nos_por_tipo(TipoNo.NOTE)
    return [no for no in notas if no.obter_propriedade("acao") == acao]


def _rodar(comando: str) -> None:
    """Um comando de recuperação da parada, como o humano o cola num shell."""
    subprocess.run(comando, shell=True, check=True, capture_output=True)


def test_foto_e_salvaguarda_nao_mudam_o_repositorio_do_humano_nominal(tmp_path: Path) -> None:
    """T3a5.3: a foto, o `stash create` e a árvore dos não rastreados deixam refs, índice (entradas e bytes) e status."""
    repositorio = _sujo(tmp_path / "humano")
    antes = _estado(repositorio)

    foto = foto_antes_da_sessao(repositorio)

    assert foto is not None and foto.salvaguarda.stash and foto.salvaguarda.soltos
    assert _estado(repositorio) == antes
    mexido = conferir_as_fotos(foto, fotografar_o_humano(repositorio, foto.listados))
    assert (mexido.perdas, mexido.avancos) == ((), ())
    assert foto.listados["NOTAS.txt"].xy == ".M" and foto.listados["rascunho.txt"].tipo == "?"
    assert "preparado.txt" in foto.indice and foto.cabeca.startswith("main ") and ".git/config" in foto.do_git


def test_foto_do_repositorio_limpo_roda_seis_processos_do_git_por_sessao_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3a6, item 3: sem mudança, a foto de antes e a de depois são o `status --branch`, as refs e o índice, sem salvaguarda."""
    repositorio = criar_repositorio(tmp_path / "humano")
    original = subprocess.run
    chamados: list[list[str]] = []

    def contar(comando: list[str], *args: Any, **kwargs: Any) -> Any:
        chamados.append(list(comando))
        return original(comando, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", contar)
    conferir_o_humano(foto_antes_da_sessao(repositorio), "executor", "")

    assert [comando[4] for comando in chamados] == ["status", "for-each-ref", "ls-files"] * 2, chamados


def test_salvaguarda_recupera_o_rastreado_e_o_nao_rastreado_edge_case(tmp_path: Path) -> None:
    """T3a6, item 2: depois do `reset --hard` e do não rastreado apagado, os comandos de recuperação devolvem os dois."""
    repositorio = _sujo(tmp_path / "humano")
    foto = foto_antes_da_sessao(repositorio)
    assert foto is not None
    git(repositorio, "reset", "-q", "--hard")
    (repositorio / "rascunho.txt").unlink()
    mexido = conferir_as_fotos(foto, fotografar_o_humano(repositorio, foto.listados))
    assert mexido.soltos_perdidos == ("rascunho.txt",) and len(mexido.recuperar) == 2

    for comando in mexido.recuperar:
        _rodar(comando)

    assert (repositorio / "NOTAS.txt").read_text(encoding="utf-8") == TRABALHO
    assert (repositorio / "preparado.txt").read_text(encoding="utf-8") == "no indice\n"
    assert (repositorio / "rascunho.txt").read_bytes() == RASCUNHO, "os bytes do nao rastreado, CRLF inclusive"
    assert "?? rascunho.txt" in git(repositorio, "status", "--porcelain").splitlines(), "volta solto, fora do indice"
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
    """T3a5.2 e T3a6.3: o executor roda `git -C <humano> checkout -- .` por fora do hook; o laço para em FALHA com
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
    assert nota.obter_propriedade("papel") == "executor"
    assert nota.obter_propriedade("perdas") == ["README.md voltou ao conteudo do HEAD ou do indice de antes da sessao"]
    git(bancada.repositorio, "stash", "apply", "-q", salvaguarda)
    assert (bancada.repositorio / "README.md").read_text(encoding="utf-8") == TRABALHO


def test_sessao_que_apaga_um_nao_rastreado_do_humano_para_e_o_blob_o_recupera_edge_case(tmp_path: Path) -> None:
    """T3a6.4: o executor apaga um não rastreado do humano por um script; o laço para, e o comando de recuperação da
    parada devolve o arquivo da árvore de blobs da salvaguarda, com os mesmos bytes."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    rascunho = bancada.repositorio / "rascunho.txt"
    rascunho.write_bytes(RASCUNHO)
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", f"import os; os.remove(r'{rascunho}')"]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert "rascunho.txt sumiu da arvore sem ir a um commit" in parada.mensagem and not rascunho.exists()
    (nota,) = _notas_do_humano(bancada)
    arvore = str(nota.obter_propriedade("soltos"))
    assert arvore and nota.obter_propriedade("salvaguarda") == "", "nao havia mudanca rastreada: sem stash"
    (recuperar,) = nota.obter_propriedade("recuperar")
    assert f"restore --source={arvore} -- \"rascunho.txt\"" in recuperar and f"`{recuperar}`" in parada.mensagem
    _rodar(recuperar)
    assert rascunho.read_bytes() == RASCUNHO


def test_sessao_que_poe_hooks_path_na_configuracao_do_humano_para_o_laco_edge_case(tmp_path: Path) -> None:
    """T3a6.5: o executor põe `core.hooksPath` no `.git/config` do humano, que rodaria código dele no próximo commit; o
    laço para."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    script = f"import subprocess\nsubprocess.run(['git', '-C', r'{bancada.repositorio}', 'config', 'core.hooksPath', 'ganchos'], check=True)\n"
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", script]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert ".git/config mudou" in parada.mensagem and "sessao do executor" in parada.mensagem
    assert git(bancada.repositorio, "config", "core.hooksPath").strip() == "ganchos", "a conferencia nao desfaz"
    (nota,) = _notas_do_humano(bancada)
    assert [perda.split(" (")[0] for perda in nota.obter_propriedade("perdas")] == [".git/config mudou"]


def test_humano_que_muda_e_commita_um_arquivo_durante_a_sessao_e_avanco_e_o_laco_fecha_nominal(tmp_path: Path) -> None:
    """T3a6.1: com o claude falso, o humano muda o arquivo sujo dele e o commita na main durante a sessão do executor;
    o laço segue e fecha (com o rebase sobre a base que andou), e a sessão deixa a Note do avanço."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    repositorio = bancada.repositorio
    (repositorio / "NOTAS.txt").write_text("notas\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "NOTAS.txt")
    git(repositorio, "commit", "-q", "-m", "Notas do humano")
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")

    commitado: list[str] = []

    def humano() -> None:
        (repositorio / "NOTAS.txt").write_text(TRABALHO + "mais uma linha\n", encoding="utf-8", newline="\n")
        git(repositorio, "commit", "-q", "-am", "Humano commita as notas")
        commitado.append(git(repositorio, "rev-parse", "HEAD").strip())

    parada = bancada.orquestrador(executor=ExecutorComHumano(bancada.executor, humano, na=3)).iniciar_da_spec(
        bancada.spec, repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(repositorio, "show", "main:NOTAS.txt") == TRABALHO + "mais uma linha\n"
    assert git(repositorio, "merge-base", "--is-ancestor", commitado[0], "main") == "", "o commit do humano esta na base"
    assert _notas_do_humano(bancada) == []
    (avanco,) = _notas_do_humano(bancada, "repositorio_do_humano_avancou")
    avancos = [HASH.sub("#", item) for item in avanco.obter_propriedade("avancos")]
    assert avancos == ["ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> main #",
                       "NOTAS.txt mudou para um conteudo novo"], avancos
    assert avanco.obter_propriedade("perdas") == []


def test_outro_goal_que_integra_na_base_durante_a_sessao_nao_para_o_laco_nominal(tmp_path: Path) -> None:
    """T3a6.2: durante a sessão do executor, outro "Goal" integra a branch dele na main por fast-forward
    (`integrar_por_fast_forward`); a base andou, e o laço segue e fecha."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    repositorio = bancada.repositorio
    integrado: list[str] = []

    def outro_goal() -> None:
        (repositorio / "OUTRO.txt").write_text("do outro Goal\n", encoding="utf-8", newline="\n")
        git(repositorio, "add", "OUTRO.txt")
        arvore = git(repositorio, "write-tree").strip()
        git(repositorio, "rm", "-q", "--cached", "OUTRO.txt")
        (repositorio / "OUTRO.txt").unlink()
        git(repositorio, "branch", "graphow/outro", git(repositorio, "commit-tree", arvore, "-p", "main", "-m", "Outro Goal").strip())
        integrado.append(integrar_por_fast_forward(repositorio, "graphow/outro", "main"))

    parada = bancada.orquestrador(executor=ExecutorComHumano(bancada.executor, outro_goal, na=3)).iniciar_da_spec(
        bancada.spec, repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert git(repositorio, "merge-base", "--is-ancestor", integrado[0], "main") == ""
    assert git(repositorio, "show", "main:OUTRO.txt") == "do outro Goal\n"
    (avanco,) = _notas_do_humano(bancada, "repositorio_do_humano_avancou")
    assert [HASH.sub("#", item) for item in avanco.obter_propriedade("avancos")] == [
        "ref refs/heads/graphow/outro nova (#)", "ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> main #"]


def test_sessoes_que_nao_mexem_no_humano_nao_param_e_o_trabalho_dele_fica_nominal(tmp_path: Path) -> None:
    """T3a5.3: com mudança no índice, fora dele e arquivo solto no repositório do humano, o Goal fecha sem parada nem Note."""
    bancada = montar_bancada(tmp_path, roteiro_farto())
    (bancada.repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    git(bancada.repositorio, "add", "NOTAS.txt")
    (bancada.repositorio / "rascunho.txt").write_text("solto\n", encoding="utf-8", newline="\n")
    indice = git(bancada.repositorio, "ls-files", "-s", "NOTAS.txt")

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert _notas_do_humano(bancada) == [] and _notas_do_humano(bancada, "repositorio_do_humano_avancou") == []
    assert git(bancada.repositorio, "ls-files", "-s", "NOTAS.txt") == indice
    assert (bancada.repositorio / "rascunho.txt").read_text(encoding="utf-8") == "solto\n"
    assert git(bancada.repositorio, "status", "--porcelain", "-uall").splitlines() == ["A  NOTAS.txt", "?? rascunho.txt"]
