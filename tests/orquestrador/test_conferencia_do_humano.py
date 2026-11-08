"""T3a6, T3a8 e T3a11: a tabela da conferência do repositório do humano, linha a linha; a perda para o laço, o avanço segue."""

from collections.abc import Callable
from pathlib import Path
import re

import pytest

from graphow.orquestrador.conferencia_do_humano import (
    RamoDeOutroGoal,
    RepositorioDoHumanoMexido,
    conferir_as_fotos,
    conferir_o_humano,
)
from graphow.orquestrador.foto_do_humano import foto_antes_da_sessao, fotografar_o_humano

from tests.orquestrador.apoio_git import criar_repositorio, git

HASH: re.Pattern[str] = re.compile(r"\b[0-9a-f]{40,64}\b")
VOLTOU: str = "voltou ao conteudo do HEAD ou do indice de antes da sessao"
SUMIU: str = "sumiu da arvore sem ir a um commit"
SOBRESCRITO: str = "foi sobrescrito por um conteudo que o git ja tinha, e o de antes nao ficou em commit nem no indice"
TROCADA: str = "indice INDICE.txt: a entrada foi trocada por um conteudo que o git ja tinha"
GOAL_B: str = "goal-outro"
RAMO_B: str = "refs/heads/graphow/outro"
DO_GOAL_B: str = f"Graphow-Goal: {GOAL_B}"
Acao = Callable[[Path], object]
# A sessão que mexe na branch do outro Goal: recebe o repositório, a base nova e a ponta da branch, e devolve os rebases
# (antes, depois) que o grafo registra dele.
Sessao = Callable[[Path, str, str], tuple[tuple[str, str], ...]]


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
    ("indice_que_saiu_com_o_conteudo_na_arvore", _git("rm", "-q", "--cached", "preparado.txt"),
     ["indice preparado.txt: a entrada saiu, e o conteudo preparado esta na arvore"]),
    ("indice_que_voltou_com_o_conteudo_na_arvore", _git("reset", "-q", "--", "INDICE.txt"),
     ["indice INDICE.txt: a entrada mudou, e o conteudo preparado esta na arvore"]),
    ("mudado_editado_e_preparado", _varias(_escrever("NOTAS.txt", "mais trabalho\n"), _git("add", "NOTAS.txt")),
     ["NOTAS.txt mudou para um conteudo novo"]),
    ("mudado_editado_e_commitado", _varias(_escrever("NOTAS.txt", "mais trabalho\n"), _git("commit", "-q", "-am", "humano")),
     ["ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> main #", "NOTAS.txt mudou para um conteudo novo"]),
]


def _conferir(tmp_path: Path, acao: Acao, montar: Callable[[Path], Path] = _humano) -> tuple[list[str], list[str]]:
    """A perda e o avanço da ação no repositório do humano, sem os hashes."""
    repositorio = montar(tmp_path / "humano")
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


def _com_lateral(pasta: Path) -> Path:
    """T3a8: NOTAS.txt mudado, INDICE.txt mudado no índice, rascunho.txt solto e a branch `lateral`, um commit à frente da
    main, em que NOTAS.txt e INDICE.txt têm outro conteúdo."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n", "INDICE.txt": "v1\n"})
    git(repositorio, "switch", "-q", "-c", "lateral")
    _varias(_escrever("NOTAS.txt", "notas da lateral\n"), _escrever("INDICE.txt", "v1 da lateral\n"))(repositorio)
    git(repositorio, "commit", "-q", "-am", "lateral")
    git(repositorio, "switch", "-q", "main")
    _varias(_escrever("NOTAS.txt", "trabalho do humano\n"), _escrever("INDICE.txt", "v2 no indice\n"))(repositorio)
    git(repositorio, "add", "INDICE.txt")
    _escrever("rascunho.txt", "solto\n")(repositorio)
    return repositorio


DESCARTADOS: list[str] = [f"INDICE.txt {SOBRESCRITO}", TROCADA, f"NOTAS.txt {SOBRESCRITO}"]
TROCAS_QUE_DESCARTAM: list[tuple[str, Acao, list[str]]] = [
    ("f2_checkout_forcado", _git("checkout", "-q", "-f", "lateral"), DESCARTADOS),
    ("switch_discard_changes", _git("switch", "-q", "--discard-changes", "lateral"), DESCARTADOS),
    ("f2b_reset_hard_para_o_descendente", _git("reset", "-q", "--hard", "lateral"), DESCARTADOS),
    ("checkout_do_arquivo_de_outra_branch", _git("checkout", "lateral", "--", "NOTAS.txt"), [f"NOTAS.txt {SOBRESCRITO}"]),
]


@pytest.mark.parametrize(("acao", "esperado"), [caso[1:] for caso in TROCAS_QUE_DESCARTAM], ids=[caso[0] for caso in TROCAS_QUE_DESCARTAM])
def test_troca_que_descarta_o_sujo_e_perda_edge_case(tmp_path: Path, acao: Acao, esperado: list[str]) -> None:
    """T3a8.1 (F2 e F2b): a troca de HEAD que põe na árvore o conteúdo de outro commit apaga o mudado, e o de antes não fica
    em lugar nenhum; para o laço, mesmo com a main andando por fast-forward."""
    perdas, _ = _conferir(tmp_path, acao, _com_lateral)

    assert perdas == esperado


def test_humano_que_commita_o_sujo_e_troca_de_branch_avanca_nominal(tmp_path: Path) -> None:
    """T3a8.1, contraprova: o humano commita tudo (o mudado, o preparado e o solto) e troca de branch; o conteúdo de antes
    está na ponta que andou, e nada para."""
    acao = _varias(_git("add", "-A"), _git("commit", "-q", "-m", "salva"), _git("switch", "-q", "lateral"))

    perdas, avancos = _conferir(tmp_path, acao, _com_lateral)

    na_main = "esta em refs/heads/main"
    assert (perdas, avancos) == ([], [
        "ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> lateral #",
        f"INDICE.txt mudou, e o conteudo de antes {na_main}", f"indice INDICE.txt: a entrada mudou, e o conteudo preparado {na_main}",
        f"NOTAS.txt mudou, e o conteudo de antes {na_main}", f"rascunho.txt sumiu, e o conteudo de antes {na_main}"])


def _com_historia(pasta: Path) -> Path:
    """T3a11: a main com dois commits, NOTAS.txt e INDICE.txt mudando de um para o outro, e por cima NOTAS.txt mudado,
    INDICE.txt mudado no índice e rascunho.txt solto."""
    repositorio = criar_repositorio(pasta, {"README.md": "# brinquedo\n", "NOTAS.txt": "notas\n", "INDICE.txt": "v1\n"})
    _varias(_escrever("NOTAS.txt", "notas v2\n"), _escrever("INDICE.txt", "v1 de novo\n"), _git("commit", "-q", "-am", "v2"),
            _escrever("NOTAS.txt", "trabalho do humano\n"), _escrever("INDICE.txt", "v2 no indice\n"), _git("add", "INDICE.txt"),
            _escrever("rascunho.txt", "solto\n"))(repositorio)
    return repositorio


@pytest.mark.parametrize("troca", [["checkout", "-q", "-f", "--detach", "HEAD~1"], ["switch", "-q", "--detach", "--discard-changes", "HEAD~1"]],
                         ids=["checkout_f_detach", "switch_discard_changes"])
def test_troca_para_um_commit_antigo_que_descarta_o_sujo_e_perda_edge_case(tmp_path: Path, troca: list[str]) -> None:
    """T3a11.1 (S1): a troca para um commit que não é ponta, mas já estava na história (HEAD~1), põe na árvore e no índice o
    conteúdo dele; o HEAD novo conta como o que o git já tinha, e o de antes não fica em lugar nenhum."""
    perdas, avancos = _conferir(tmp_path, _git(*troca), _com_historia)

    assert (perdas, avancos) == (DESCARTADOS, ["HEAD: main # -> (detached) #"])


def test_humano_que_commita_o_sujo_e_volta_a_um_commit_antigo_avanca_nominal(tmp_path: Path) -> None:
    """T3a11.1, contraprova: o humano commita tudo e vai a um commit antigo; o conteúdo de antes está na ponta que andou."""
    acao = _varias(_git("add", "-A"), _git("commit", "-q", "-m", "salva"), _git("checkout", "-q", "--detach", "HEAD~2"))

    perdas, avancos = _conferir(tmp_path, acao, _com_historia)

    na_main = "esta em refs/heads/main"
    assert (perdas, avancos) == ([], [
        "ref refs/heads/main andou por fast-forward (# -> #)", "HEAD: main # -> (detached) #",
        f"INDICE.txt mudou, e o conteudo de antes {na_main}", f"indice INDICE.txt: a entrada mudou, e o conteudo preparado {na_main}",
        f"NOTAS.txt mudou, e o conteudo de antes {na_main}", f"rascunho.txt sumiu, e o conteudo de antes {na_main}"])


def _commit(repositorio: Path, pai: str, *paragrafos: str) -> str:
    """Um commit novo sobre o pai, com a árvore dele; cada parágrafo vai num `-m`."""
    return git(repositorio, "commit-tree", f"{pai}^{{tree}}", "-p", pai, *(f"-m{paragrafo}" for paragrafo in paragrafos)).strip()


def _outro_goal(pasta: Path, *paragrafos: str) -> tuple[Path, str, str]:
    """A branch do outro Goal com um commit dele (os parágrafos dados, o trailer dele por padrão) sobre a base de antes, e a
    base que andou; devolve o repositório, a base nova e a ponta da branch."""
    repositorio = criar_repositorio(pasta)
    inicial = git(repositorio, "rev-parse", "HEAD").strip()
    git(repositorio, "commit", "-q", "--allow-empty", "-m", "A base andou")
    ponta = _commit(repositorio, inicial, "Plano do outro Goal", *(paragrafos or (DO_GOAL_B,)))
    git(repositorio, "update-ref", RAMO_B, ponta)
    return repositorio, git(repositorio, "rev-parse", "HEAD").strip(), ponta


def _reaplicar(repositorio: Path, base: str, ponta: str) -> str:
    """O rebase: cada commit da ponta que a base não tem, refeito sobre ela com a mesma mensagem."""
    novo = base
    for commit in git(repositorio, "rev-list", "--reverse", ponta, "--not", base).split():
        mensagem = git(repositorio, "log", "-1", "--format=%B", commit).strip()
        novo = git(repositorio, "commit-tree", f"{commit}^{{tree}}", "-p", novo, f"-m{mensagem}").strip()
    return novo


def _rebase(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O outro Goal refaz a branch sobre a base nova e registra o par."""
    novo = _reaplicar(repositorio, base, ponta)
    git(repositorio, "update-ref", RAMO_B, novo, ponta)
    return ((ponta, novo),)


def _commit_depois_do_rebase(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase e, depois, uma fatia do outro Goal por cima."""
    rebases = _rebase(repositorio, base, ponta)
    git(repositorio, "update-ref", RAMO_B, _commit(repositorio, rebases[0][1], "Fatia", DO_GOAL_B))
    return rebases


def _commit_antes_do_rebase(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """Uma fatia do outro Goal e, depois, o rebase dela."""
    fatia = _commit(repositorio, ponta, "Fatia", DO_GOAL_B)
    git(repositorio, "update-ref", RAMO_B, fatia)
    return _rebase(repositorio, base, fatia)


def _dois_rebases(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase e, com a base andando de novo, outro rebase da ponta nova."""
    ((_, primeiro),) = _rebase(repositorio, base, ponta)
    segundo = _reaplicar(repositorio, _commit(repositorio, base, "A base andou de novo"), primeiro)
    git(repositorio, "update-ref", RAMO_B, segundo, primeiro)
    return ((ponta, primeiro), (primeiro, segundo))


def _so_fast_forward(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """Uma fatia do outro Goal, sem rebase."""
    git(repositorio, "update-ref", RAMO_B, _commit(repositorio, ponta, "Fatia", DO_GOAL_B))
    return ()


def _conferir_o_rebase(repositorio: Path, sessao: Sessao, *, base: str, ponta: str, com_leitor: bool = True) -> tuple[list[str], int]:
    """As mudanças da sessão (sem os hashes), com o leitor dos outros Goals do grafo (este e um terceiro), e quantas vezes ele
    foi lido."""
    antes = foto_antes_da_sessao(repositorio)
    assert antes is not None
    rebases = sessao(repositorio, base, ponta)
    lidos: list[Path] = []

    def leitor(alvo: Path) -> list[RamoDeOutroGoal]:
        lidos.append(alvo)
        return [RamoDeOutroGoal(GOAL_B, RAMO_B, rebases), RamoDeOutroGoal("goal-terceiro", "refs/heads/graphow/terceiro")]

    mexido = conferir_as_fotos(antes, fotografar_o_humano(repositorio, antes.listados), leitor if com_leitor else None)
    assert set(lidos) <= {repositorio}
    return [("perda: " if texto in mexido.perdas else "") + HASH.sub("#", texto) for texto in (*mexido.perdas, *mexido.avancos)], len(lidos)


REFEITA: str = f"ref {RAMO_B} refeita pelo rebase do Goal {GOAL_B} (# -> #)"
FORA: str = f"perda: ref {RAMO_B} andou fora de fast-forward (# -> #)"
SEM_REBASE: str = f"{FORA}; e a branch do Goal {GOAL_B}, mas nenhum rebase registrado dele a leva ate ali"
SEM_TRAILER: str = f"{FORA}; e a branch do Goal {GOAL_B}, mas saiu da historia commit sem {DO_GOAL_B} (#)"
REBASES_QUE_SEGUEM: list[tuple[str, Sessao, list[str], int]] = [
    ("rebase", _rebase, [REFEITA], 1),
    ("fatia_depois_do_rebase", _commit_depois_do_rebase, [REFEITA], 1),
    ("fatia_antes_do_rebase", _commit_antes_do_rebase, [REFEITA], 1),
    ("dois_rebases", _dois_rebases, [REFEITA], 1),
    ("so_fast_forward", _so_fast_forward, [f"ref {RAMO_B} andou por fast-forward (# -> #)"], 0),
]


@pytest.mark.parametrize(("sessao", "esperado", "lidos"), [caso[1:] for caso in REBASES_QUE_SEGUEM],
                         ids=[caso[0] for caso in REBASES_QUE_SEGUEM])
def test_rebase_de_outro_goal_com_a_evidence_dele_segue_nominal(tmp_path: Path, sessao: Sessao, esperado: list[str], lidos: int) -> None:
    """T3a8.2: o outro Goal refaz a branch dele sobre a base nova (e commita antes ou depois), com o par registrado; não é
    perda. O grafo só é lido quando uma ref anda fora de fast-forward, e uma vez."""
    repositorio, base, ponta = _outro_goal(tmp_path / "humano")

    assert _conferir_o_rebase(repositorio, sessao, base=base, ponta=ponta) == (esperado, lidos)


def _rebase_sem_registro(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase da branch, sem a Evidence dele no grafo."""
    _rebase(repositorio, base, ponta)
    return ()


def _rebase_com_o_par_de_outro(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase da branch, com a Evidence de outro par: ela chega à ponta nova, mas parte de um commit que não é o de antes
    nem vem depois dele."""
    (_, novo), = _rebase(repositorio, base, ponta)
    return ((base, novo),)


def _rebase_e_branch_apagada(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase registrado e a branch apagada no repositório do humano."""
    novo = _reaplicar(repositorio, base, ponta)
    git(repositorio, "update-ref", "-d", RAMO_B)
    return ((ponta, novo),)


def _rebase_da_parecida(repositorio: Path, base: str, ponta: str) -> tuple[tuple[str, str], ...]:
    """O rebase de `graphow/outra`, que não é a branch de Goal nenhum, com o par registrado na branch do outro Goal."""
    novo = _reaplicar(repositorio, base, ponta)
    git(repositorio, "update-ref", "refs/heads/graphow/outra", novo, ponta)
    return ((ponta, novo),)


def test_rebase_de_outro_goal_sem_o_que_o_justifica_para_edge_case(tmp_path: Path) -> None:
    """T3a8.2, contraprova: a branch do outro Goal fora de fast-forward para sem o leitor do grafo, sem o rebase registrado,
    com o par de outro rebase, e com um commit sem o trailer dele (do humano, no corpo da mensagem ou de outro Goal) que sai."""
    repositorio, base, ponta = _outro_goal(tmp_path / "sem-leitor")
    assert _conferir_o_rebase(repositorio, _rebase, base=base, ponta=ponta, com_leitor=False) == ([FORA], 0)
    for nome, sessao in (("sem-rebase", _rebase_sem_registro), ("outro-par", _rebase_com_o_par_de_outro)):
        repositorio, base, ponta = _outro_goal(tmp_path / nome)
        assert _conferir_o_rebase(repositorio, sessao, base=base, ponta=ponta) == ([SEM_REBASE], 1), nome
    for nome, paragrafos in (("no-corpo", (DO_GOAL_B, "Um paragrafo depois")), ("de-outro-goal", ("Graphow-Goal: goal-terceiro",))):
        repositorio, base, ponta = _outro_goal(tmp_path / nome, *paragrafos)
        assert _conferir_o_rebase(repositorio, _rebase, base=base, ponta=ponta) == ([SEM_TRAILER], 1), nome
    repositorio, base, ponta = _outro_goal(tmp_path / "do-humano")
    do_humano = _commit(repositorio, ponta, "Commit do humano na branch do outro Goal")
    git(repositorio, "update-ref", RAMO_B, do_humano)
    assert _conferir_o_rebase(repositorio, _rebase, base=base, ponta=do_humano) == ([SEM_TRAILER], 1), "so o do humano"


def test_ref_parecida_e_branch_apagada_do_outro_goal_sao_perda_edge_case(tmp_path: Path) -> None:
    """T3a8.2: a ref com o prefixo `graphow/` que não é a branch de um Goal é perda, mesmo com o par igual ao de um rebase
    registrado; e a branch apagada do outro Goal também."""
    repositorio, base, ponta = _outro_goal(tmp_path / "parecida")
    git(repositorio, "update-ref", "refs/heads/graphow/outra", ponta)
    assert _conferir_o_rebase(repositorio, _rebase_da_parecida, base=base, ponta=ponta) == (
        ["perda: ref refs/heads/graphow/outra andou fora de fast-forward (# -> #)"], 1)
    repositorio, base, ponta = _outro_goal(tmp_path / "apagada")
    assert _conferir_o_rebase(repositorio, _rebase_e_branch_apagada, base=base, ponta=ponta) == ([f"perda: ref {RAMO_B} apagada (era #)"], 0)
