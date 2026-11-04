"""T3a6: a tabela da conferência do repositório do humano, linha a linha; a perda para o laço, o avanço segue."""

from collections.abc import Callable
from pathlib import Path
import re

import pytest

from graphow.orquestrador.conferencia_do_humano import RepositorioDoHumanoMexido, conferir_as_fotos, conferir_o_humano
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao, fotografar_o_humano

from tests.orquestrador.apoio_git import criar_repositorio, git

HASH: re.Pattern[str] = re.compile(r"\b[0-9a-f]{40,64}\b")
VOLTOU: str = "voltou ao conteudo do HEAD ou do indice de antes da sessao"
SUMIU: str = "sumiu da arvore sem ir a um commit"
Acao = Callable[[Path], object]


def _humano(pasta: Path) -> Path:
    """O repositório do humano: NOTAS.txt mudado, INDICE.txt mudado no índice, preparado.txt novo no índice,
    rascunho.txt solto, README.md limpo e a branch `lateral` no HEAD."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n", "INDICE.txt": "v1\n"})
    git(repositorio, "branch", "lateral")
    (repositorio / "NOTAS.txt").write_text("trabalho do humano\n", encoding="utf-8", newline="\n")
    (repositorio / "INDICE.txt").write_text("v2 no indice\n", encoding="utf-8", newline="\n")
    (repositorio / "preparado.txt").write_text("no indice\n", encoding="utf-8", newline="\n")
    git(repositorio, "add", "preparado.txt", "INDICE.txt")
    (repositorio / "rascunho.txt").write_text("solto\n", encoding="utf-8", newline="\n")
    return repositorio


def _escrever(nome: str, texto: str) -> Acao:
    """Grava o arquivo do repositório."""
    return lambda repositorio: (repositorio / nome).write_text(texto, encoding="utf-8", newline="\n")


def _apagar(nome: str) -> Acao:
    """Apaga o arquivo do repositório."""
    return lambda repositorio: (repositorio / nome).unlink()


def _git(*argumentos: str) -> Acao:
    """O git no repositório."""
    return lambda repositorio: git(repositorio, *argumentos)


def _commit_na_lateral(pai: bool) -> Acao:
    """A `lateral` vai a um commit novo: filho do dela (fast-forward) ou sem pai (fora de fast-forward)."""
    def mover(repositorio: Path) -> None:
        novo = git(repositorio, "commit-tree", "lateral^{tree}", *(["-p", "lateral"] if pai else []), "-m", "outro").strip()
        git(repositorio, "update-ref", "refs/heads/lateral", novo)
    return mover


def _varias(*acoes: Acao) -> Acao:
    """As ações, em ordem."""
    return lambda repositorio: [acao(repositorio) for acao in acoes]


PERDAS: list[tuple[str, Acao, list[str]]] = [
    ("checkout_do_mudado", _git("checkout", "--", "."), [f"NOTAS.txt {VOLTOU}"]),
    ("reset_hard", _git("reset", "-q", "--hard"),
     [f"INDICE.txt {VOLTOU}", "indice INDICE.txt: a entrada voltou a do HEAD", f"NOTAS.txt {VOLTOU}", f"preparado.txt {SUMIU}",
      "indice preparado.txt: a entrada saiu"]),
    ("mudado_apagado", _apagar("NOTAS.txt"), [f"NOTAS.txt {SUMIU}"]),
    ("solto_apagado", _apagar("rascunho.txt"), [f"rascunho.txt {SUMIU}"]),
    ("limpo_apagado_sem_commit", _apagar("README.md"), [f"README.md {SUMIU}"]),
    ("indice_que_saiu", _git("rm", "-q", "--cached", "preparado.txt"), ["indice preparado.txt: a entrada saiu"]),
    ("indice_que_voltou", _git("reset", "-q", "--", "INDICE.txt"), ["indice INDICE.txt: a entrada voltou a do HEAD"]),
    ("commit_desfeito", _varias(_git("commit", "-q", "-am", "x"), _git("reset", "-q", "--hard", "HEAD~1")),
     [f"INDICE.txt {VOLTOU}", "indice INDICE.txt: a entrada voltou a do HEAD", f"NOTAS.txt {VOLTOU}", f"preparado.txt {SUMIU}",
      "indice preparado.txt: a entrada saiu"]),
    ("ref_apagada", _git("branch", "-D", "lateral"), ["ref refs/heads/lateral apagada (era #)"]),
    ("ref_fora_de_fast_forward", _commit_na_lateral(False), ["ref refs/heads/lateral andou fora de fast-forward (# -> #)"]),
    ("hooks_path", _git("config", "core.hooksPath", "ganchos"), [".git/config mudou (# -> #)"]),
    ("hook_plantado", _escrever(".git/hooks/pre-commit", "#!/bin/sh\necho agente\n"), [".git/hooks/pre-commit mudou (ausente -> #)"]),
]

AVANCOS: list[tuple[str, Acao, list[str]]] = [
    ("commit_do_sujo", _git("commit", "-q", "-am", "humano"), ["ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> main #"]),
    ("mudado_para_conteudo_novo", _escrever("NOTAS.txt", "mais trabalho\n"), ["NOTAS.txt mudou para um conteudo novo"]),
    ("limpo_para_conteudo_novo", _escrever("README.md", "# outro\n"), ["README.md mudou para um conteudo novo"]),
    ("solto_para_conteudo_novo", _escrever("rascunho.txt", "outro rascunho\n"), ["rascunho.txt mudou para um conteudo novo"]),
    ("arquivo_novo", _escrever("novo.txt", "novo\n"), ["novo.txt apareceu"]),
    ("indice_novo", _varias(_escrever("preparado.txt", "outro\n"), _git("add", "preparado.txt")),
     ["preparado.txt mudou para um conteudo novo", "indice preparado.txt: entrada nova"]),
    ("limpo_apagado_com_commit", _varias(_git("rm", "-q", "README.md"), _git("commit", "-q", "-m", "tira")),
     ["ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> main #"]),
    ("ref_por_fast_forward", _commit_na_lateral(True), ["ref refs/heads/lateral andou por fast-forward (# -> #)"]),
    ("ref_nova", _git("tag", "-a", "v1", "-m", "release"), ["ref refs/tags/v1 nova (#)"]),
    ("troca_de_branch_com_as_mudancas", _git("switch", "-q", "lateral"), ["HEAD: main # -> lateral #"]),
]


def _conferir(tmp_path: Path, acao: Acao) -> tuple[list[str], list[str]]:
    """A perda e o avanço da ação no repositório do humano, sem os hashes."""
    repositorio = _humano(tmp_path / "humano")
    antes = foto_antes_da_sessao(repositorio)
    assert antes is not None
    acao(repositorio)
    mexido = conferir_as_fotos(antes, fotografar_o_humano(repositorio, antes.listados))
    return [HASH.sub("#", texto) for texto in mexido.perdas], [HASH.sub("#", texto) for texto in mexido.avancos]


@pytest.mark.parametrize(("acao", "esperado"), [caso[1:] for caso in PERDAS], ids=[caso[0] for caso in PERDAS])
def test_conferencia_acusa_a_perda_edge_case(tmp_path: Path, acao: Acao, esperado: list[str]) -> None:
    """T3a6, item 1: cada linha de perda da tabela para o laço."""
    perdas, _ = _conferir(tmp_path, acao)

    assert perdas == esperado


@pytest.mark.parametrize(("acao", "esperado"), [caso[1:] for caso in AVANCOS], ids=[caso[0] for caso in AVANCOS])
def test_conferencia_deixa_o_avanco_seguir_nominal(tmp_path: Path, acao: Acao, esperado: list[str]) -> None:
    """T3a6, item 1: cada linha de avanço da tabela segue, sem perda nenhuma."""
    perdas, avancos = _conferir(tmp_path, acao)

    assert (perdas, avancos) == ([], esperado)


def test_avanco_vai_ao_registro_e_a_perda_tambem_para_edge_case(tmp_path: Path) -> None:
    """O avanço vai ao registro e volta; a perda vai ao registro e levanta `RepositorioDoHumanoMexido` com o motivo."""
    repositorio = _humano(tmp_path / "humano")
    registrados: list[tuple[str, str, int, int]] = []

    def registrar(papel: str, fatia: str, mexido: object) -> None:
        registrados.append((papel, fatia, len(getattr(mexido, "perdas")), len(getattr(mexido, "avancos"))))

    antes = foto_antes_da_sessao(repositorio)
    _escrever("novo.txt", "novo\n")(repositorio)
    conferir_o_humano(antes, "executor", "F1", registrar=registrar)
    antes = foto_antes_da_sessao(repositorio)
    git(repositorio, "checkout", "--", "NOTAS.txt")
    with pytest.raises(RepositorioDoHumanoMexido, match="^repositorio_do_humano_mexido: .*NOTAS.txt voltou"):
        conferir_o_humano(antes, "verificador", "", registrar=registrar)

    assert registrados == [("executor", "F1", 0, 1), ("verificador", "", 1, 0)]
