"""T3a11.1: a troca para um commit antigo, que já estava na história de antes da sessão, apaga o sujo e para o laço; a regra
gasta um processo do git a mais, e só quando o HEAD vai a outro commit."""

from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from graphow.orquestrador.conferencia_do_humano import SOBRESCRITO, conferir_as_fotos
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao, fotografar_o_humano

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import Bancada, executor_pronto, montar_bancada
from tests.orquestrador.test_conferencia_do_humano import Acao, _com_historia, _escrever, _git, _varias
from tests.orquestrador.test_foto_do_humano import TRABALHO, _notas_do_humano, _rodar
from tests.orquestrador.test_retomada import TUDO, roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
TROCAS: list[list[str]] = [["checkout", "-q", "-f", "--detach", "HEAD~1"], ["switch", "-q", "--detach", "--discard-changes", "HEAD~1"]]
NOMES_DAS_TROCAS: list[str] = ["checkout_f_detach", "switch_discard_changes"]
# O código do agente que troca o HEAD do humano com o git sem a trava do ambiente (o hook dela recusaria mover o HEAD).
TROCA_SEM_A_TRAVA: str = (
    "import os, subprocess\n"
    "sem_trava = {{nome: valor for nome, valor in os.environ.items() if not nome.startswith('GIT_CONFIG')}}\n"
    "subprocess.run(['git', '-C', {h!r}, *{troca!r}], check=True, env=sem_trava)\n"
)


def _notas_em_dois_commits(bancada: Bancada) -> str:
    """NOTAS.txt em dois commits da main e, por cima, mudado; devolve o commit da main."""
    repositorio = bancada.repositorio
    for texto in ("notas\n", "notas v2\n"):
        (repositorio / "NOTAS.txt").write_text(texto, encoding="utf-8", newline="\n")
        git(repositorio, "add", "NOTAS.txt")
        git(repositorio, "commit", "-q", "-m", f"Notas: {texto.strip()}")
    (repositorio / "NOTAS.txt").write_text(TRABALHO, encoding="utf-8", newline="\n")
    return git(repositorio, "rev-parse", "main").strip()


@pytest.mark.parametrize("troca", TROCAS, ids=NOMES_DAS_TROCAS)
def test_troca_para_um_commit_antigo_durante_a_sessao_para_o_laco_edge_case(tmp_path: Path, troca: list[str]) -> None:
    """T3a11.1 (S1): o código do agente, por fora do hook e sem a trava do ambiente, leva o humano a HEAD~1, e a troca põe
    na árvore o NOTAS.txt de lá. O laço para em FALHA, a Note diz o arquivo e a mensagem, o HEAD de antes; de volta a ele,
    os comandos da Note devolvem o trabalho."""
    roteiro = roteiro_farto()
    bancada = montar_bancada(tmp_path, roteiro)
    repositorio = bancada.repositorio
    main = _notas_em_dois_commits(bancada)
    script = TROCA_SEM_A_TRAVA.format(h=str(repositorio), troca=troca)
    roteiro["executor"][0] = executor_pronto(dict(TUDO), comandos=[[sys.executable, "-c", script]])
    bancada.trocar_roteiro(roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA and "repositorio_do_humano_mexido" in parada.mensagem, parada.mensagem
    assert git(repositorio, "rev-parse", "HEAD") == git(repositorio, "rev-parse", "main~1")
    assert (repositorio / "NOTAS.txt").read_text(encoding="utf-8") == "notas\n"
    (nota,) = _notas_do_humano(bancada)
    assert nota.obter_propriedade("perdas") == [f"NOTAS.txt {SOBRESCRITO}"]
    assert f"o `stash apply` vale sobre o HEAD de antes (main {main}), com a arvore e o indice iguais a ele" in parada.mensagem
    git(repositorio, "switch", "-q", "--discard-changes", "main")
    for comando in nota.obter_propriedade("recuperar"):
        _rodar(comando)
    assert (repositorio / "NOTAS.txt").read_text(encoding="utf-8") == TRABALHO


PROCESSOS: list[tuple[str, Acao, list[str]]] = [
    ("nada", lambda repositorio: None, []),
    ("checkout_sem_trocar_o_head", _git("checkout", "--", "."), ["cat-file"]),
    ("head_destacado_no_mesmo_commit", _git("checkout", "-q", "-f", "--detach"), ["cat-file"]),
    ("head_num_commit_antigo", _git(*TROCAS[0]), ["rev-list", "cat-file"]),
    ("head_num_commit_novo", _varias(_escrever("NOTAS.txt", "mais\n"), _git("commit", "-q", "-am", "humano")),
     ["rev-list", "cat-file", "merge-base"]),
]


@pytest.mark.parametrize(("acao", "esperados"), [caso[1:] for caso in PROCESSOS], ids=[caso[0] for caso in PROCESSOS])
def test_regra_do_head_novo_gasta_um_processo_so_quando_o_head_vai_a_outro_commit_nominal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acao: Acao, esperados: list[str]) -> None:
    """T3a11, item 1: a conferência das fotos roda o `cat-file` dos objetos quando um arquivo vai a um conteúdo que o git
    sabe, e o `rev-list` que diz se o HEAD novo já existia só quando ele está num commit que não é o de antes (a ref que
    andou tem o `merge-base` dela, como antes)."""
    repositorio = _com_historia(tmp_path / "humano")
    antes = foto_antes_da_sessao(repositorio)
    assert antes is not None
    acao(repositorio)
    depois = fotografar_o_humano(repositorio, antes.listados)
    original = subprocess.run
    chamados: list[list[str]] = []

    def contar(comando: list[str], *args: Any, **kwargs: Any) -> Any:
        chamados.append(list(comando))
        return original(comando, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", contar)
    conferir_as_fotos(antes, depois)

    assert [comando[comando.index("--no-optional-locks") + 1] for comando in chamados] == esperados, chamados
