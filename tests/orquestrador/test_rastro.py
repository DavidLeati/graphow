"""O `graphow orquestrar --goal X --rastro`: por critério, os testes, as fatias, a verificação que o atestou e os achados."""

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from graphow.orquestrador.conferencia_na_leitura import LeituraPorGoal
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_RETIRAR_CRITERIO, NovoPedido
from graphow.orquestrador.rastro import formatar_rastro, ler_rastro

from tests.api.test_cli_orquestrar import _executavel, _rodar
from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import COMANDO_ACEITE, Bancada, montar_bancada, roteiro_completo, verificacao


def _blocos(linhas: Sequence[str], codigo: str) -> list[str]:
    """As linhas do critério no rastro: a do critério e as quatro dele, indentadas."""
    inicio = next(n for n, linha in enumerate(linhas) if linha.startswith(f"{codigo}: "))
    fim = next((n for n in range(inicio + 1, len(linhas)) if not linhas[n].startswith(" ")), len(linhas))
    return list(linhas[inicio:fim])


def _goal_fechado_pela_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Bancada, Callable[[], tuple[int, list[str]]]]:
    """O Goal da spec fechado pela CLI com o claude falso, num banco SQLite, e o `--rastro` dele, para rodar quando quiser."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    monkeypatch.setenv("GRAPHOW_CLAUDE", str(_executavel(tmp_path / "bin")))
    monkeypatch.setenv("GRAPHOW_TESTE_ROTEIRO", str(bancada.roteiro))
    monkeypatch.setenv("GRAPHOW_TESTE_REGISTRO", str(bancada.registro))
    banco, dados = tmp_path / "dados" / "graphow.db", tmp_path / "dados"
    corrida = ["--db", str(banco), "orquestrar", "--spec", str(bancada.spec), "--repo", str(bancada.repositorio), "--modo", "autonomo"]
    assert _rodar(corrida, dados)[0] == 0
    return bancada, lambda: _rodar(["--db", str(banco), "orquestrar", "--goal", "goal-soma", "--rastro"], dados)


def test_rastro_traz_os_quatro_blocos_de_cada_criterio_do_goal_fechado_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3f.1: dois critérios e uma correção; cada critério traz testes com o commit do aceite, fatias, verificação e achados.

    C1 é provado pelo teste de aceite e coberto por F1; C2, pela checagem, e
    coberto por F2 e pela correção que nasceu do bloqueante da primeira
    verificação. A conferência, que julgou os dois, está vigente na ponta; a
    caçada, que a correção desatualizou, não é a que atesta.
    """
    bancada, rastro = _goal_fechado_pela_cli(tmp_path, monkeypatch)

    codigo, linhas = rastro()

    assert codigo == 0, linhas
    assert linhas[1] == "Rastro do Goal goal-soma: Soma de dois numeros [fechado]"
    aceite = git(bancada.repositorio, "log", "-1", "--format=%h", "--abbrev=12", "--grep=^Escreve os testes de aceite", "graphow/soma").strip()
    commits = dict(linha.split("|") for linha in git(bancada.repositorio, "log", "--format=%s|%h", "--abbrev=12", "graphow/soma").splitlines())
    f1, f2, correcao = (next(c for assunto, c in commits.items() if trecho in assunto) for trecho in ("Funcao somar", "Uso no README", "README sem exemplo"))
    conferencia = f"  Verificacao: ver-goal-soma-2 (conferencia, M1): atende em {correcao} [vigente]"
    c1, c2 = _blocos(linhas, "C1"), _blocos(linhas, "C2")
    assert c1 == ["C1: somar(2, 3) devolve 5",
                  f"  Testes (aceite em {aceite}): aceite/aceite_c1.py::test_c1_soma `{COMANDO_ACEITE}`",
                  f"  Fatias: F1 em {f1} (concluido)", conferencia, "  Achados: nenhum"], linhas
    assert c2 == ["C2: o README explica como usar somar",
                  f"  Testes (aceite em {aceite}): checagem: abrir o README.md e achar um exemplo de somar com o resultado",
                  f"  Fatias: F2 em {f2} (concluido), M1.K1.1 em {correcao} (concluido, corrige ver-goal-soma-1)", conferencia,
                  "  Achados: achado-goal-soma-v1-1 README sem exemplo (bloqueante, resolvido)"], linhas


def test_criterio_retirado_aparece_como_retirado_com_o_motivo_e_mantem_o_rastro_edge_case(tmp_path: Path) -> None:
    """Caso de borda: C2 reprovado e retirado pelo humano sai `retirado pelo humano`, com a Decision, quem e o motivo."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("nao_atende")]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    parada = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo", ciclos_de_correcao=0))
    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RETIRAR_CRITERIO, "o README fica para o proximo Goal", "david", alvo="C2"))
    assert orquestrador.rodar("goal-soma", OpcoesDoLaco(modo="autonomo")).fechou

    view = bancada.kernel.obter_view()
    estado = ler_estado(view, "goal-soma")
    assert estado is not None
    linhas = formatar_rastro(ler_rastro(view, estado, LeituraPorGoal(view)))

    c2 = _blocos(linhas, "C2")
    assert c2[0] == "C2: o README explica como usar somar [retirado pelo humano (pedido-goal-soma-1, por david): o README fica para o proximo Goal]"
    assert c2[2].startswith("  Fatias: F2 em ") and c2[3].startswith("  Verificacao: ver-goal-soma-1 (caca, M1): nao_atende em "), c2
    assert "retirado" not in _blocos(linhas, "C1")[0]


def test_rastro_diz_por_que_a_verificacao_ficou_sem_ancora_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3f2.1: a marca da verificação sem âncora leva o motivo, com o texto da vista.

    A branch do Goal e a main reescritas (um commit novo, com a árvore da
    ponta) e o commit antigo coletado: a verificação sai sem âncora, e o
    motivo diz por quê.
    """
    bancada, rastro = _goal_fechado_pela_cli(tmp_path, monkeypatch)
    repositorio = bancada.repositorio
    verificado = git(repositorio, "log", "-1", "--format=%h", "--abbrev=12", "--grep=README sem exemplo", "graphow/soma").strip()
    reescrita = git(repositorio, "commit-tree", "graphow/soma^{tree}", "-m", "Reescreve a branch do Goal").strip()
    git(repositorio, "update-ref", "refs/heads/graphow/soma", reescrita)
    git(repositorio, "update-ref", "refs/heads/main", reescrita)
    git(repositorio, "reflog", "expire", "--expire=now", "--all")
    git(repositorio, "gc", "-q", "--prune=now")
    sem = _blocos(rastro()[1], "C1")[3]

    atestado = f"  Verificacao: ver-goal-soma-2 (conferencia, M1): atende em {verificado}"
    assert sem == (f"{atestado} [sem ancora: o commit {verificado} nao existe mais no repositorio: a historia foi reescrita ou o "
                   "clone e outro]"), sem
