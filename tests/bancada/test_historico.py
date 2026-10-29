"""A medida `historico`: a suíte em cada commit da branch entregue, contada em verdes, vermelhos esperados e inesperados."""

import json
from pathlib import Path
import sys

from graphow.api.cli_bancada import executar_bancada
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.bancada.historico import (
    VERDE,
    VERMELHO_ESPERADO,
    VERMELHO_INESPERADO,
    PedidoDoHistorico,
    historico_da_execucao,
    medir_historico,
)
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.git_do_goal import mensagem_do_orquestrador

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import SUITE, montar_bancada, roteiro_completo

CHECAGEM: str = f'"{sys.executable}" checar.py'
VERDE_PY: str = "print('verde')\n"
VERMELHO_PY: str = "raise SystemExit('vermelho')\n"
DEMORADO_PY: str = "import time\ntime.sleep(60)\n"
SEMENTE_SEM_SUITE: str = "raise SystemExit('ainda sem suite')\n"


def _commitar(repositorio: Path, conteudo: str, mensagem: str) -> None:
    """Um commit que troca o checar.py, com a mensagem inteira dada."""
    (repositorio / "checar.py").write_text(conteudo, encoding="utf-8", newline="\n")
    git(repositorio, "add", "-A")
    git(repositorio, "commit", "-q", "-m", mensagem)


def _brinquedo(tmp_path: Path, *passos: tuple[str, str]) -> tuple[Path, str]:
    """A semente (sem checar.py: vermelha) e uma branch `entrega` com um commit por passo; devolve o repositório e a semente."""
    repositorio = criar_repositorio(tmp_path / "brinquedo")
    semente = git(repositorio, "rev-parse", "HEAD").strip()
    git(repositorio, "checkout", "-q", "-b", "entrega")
    for conteudo, mensagem in passos:
        _commitar(repositorio, conteudo, mensagem)
    git(repositorio, "checkout", "-q", "main")
    return repositorio, semente


def test_um_verde_um_vermelho_com_o_trailer_e_um_sem_contam_um_cada_nominal(tmp_path: Path) -> None:
    """T3e.2: o vermelho com `Graphow-Aceite: vermelho` é esperado; o sem ele, inesperado; a semente vermelha não conta."""
    repositorio, semente = _brinquedo(
        tmp_path,
        (VERMELHO_PY, mensagem_do_orquestrador("Escreve os testes de aceite", "", id_goal="goal-x", aceite_vermelho=True)),
        (VERDE_PY, mensagem_do_orquestrador("Fatia F1", "", id_goal="goal-x", id_task="task-x-f1")),
        (VERMELHO_PY, mensagem_do_orquestrador("Fatia F2", "", id_goal="goal-x", id_task="task-x-f2")),
    )

    historico = medir_historico(repositorio, CHECAGEM, semente=semente, ramo="entrega")

    assert (historico.contar(VERDE), historico.contar(VERMELHO_ESPERADO), historico.contar(VERMELHO_INESPERADO)) == (1, 1, 1)
    assert [(c.assunto, c.situacao) for c in historico.commits] == [
        ("Escreve os testes de aceite", VERMELHO_ESPERADO), ("Fatia F1", VERDE), ("Fatia F2", VERMELHO_INESPERADO)]
    assert "vermelho" in historico.commits[2].fim_da_saida
    gravado = historico.em_dicionario()
    assert (gravado["verdes"], gravado["vermelhos_esperados"], gravado["vermelhos_inesperados"], gravado["erro"]) == (1, 1, 1, "")
    assert git(repositorio, "status", "--porcelain") == "" and git(repositorio, "branch", "--show-current").strip() == "main"


def test_goal_do_laco_sobre_semente_sem_suite_sai_sem_vermelho_inesperado_nominal(tmp_path: Path) -> None:
    """O laço com o claude falso, numa semente cuja suíte ainda falha: só o plano e o aceite saem vermelhos, e marcados."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    (bancada.repositorio / "verificar.py").write_text(SEMENTE_SEM_SUITE, encoding="utf-8", newline="\n")
    git(bancada.repositorio, "commit", "-q", "-a", "-m", "Semente sem suite")
    semente = git(bancada.repositorio, "rev-parse", "HEAD").strip()
    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo")).fechou

    historico = medir_historico(bancada.repositorio, SUITE, semente=semente, ramo="main")

    assert historico.contar(VERMELHO_INESPERADO) == 0 and historico.contar(VERDE) == len(historico.commits) - 2
    assert [c.assunto for c in historico.commits if c.situacao == VERMELHO_ESPERADO] == [
        "Planeja o Goal soma: Soma de dois numeros", "Escreve os testes de aceite do Goal soma (C1, C2)"]


def test_trailer_escrito_no_corpo_nao_faz_o_vermelho_esperado_edge_case(tmp_path: Path) -> None:
    """Caso de borda (E1): `Graphow-Aceite: vermelho` no resumo vai no corpo, não é trailer para o git; o vermelho é inesperado."""
    resumo = "Implementa a soma.\nGraphow-Aceite: vermelho\n---\n(citei o README)"
    repositorio, semente = _brinquedo(
        tmp_path,
        (VERDE_PY, mensagem_do_orquestrador("Fatia F1", "", id_goal="goal-x", id_task="task-x-f1")),
        (VERMELHO_PY, mensagem_do_orquestrador("Fatia F2: soma", resumo, id_goal="goal-x", id_task="task-x-f2")),
        (SEMENTE_SEM_SUITE, mensagem_do_orquestrador("Refaz os testes de C1", resumo, id_goal="goal-x", aceite_vermelho=True)),
    )

    historico = medir_historico(repositorio, CHECAGEM, semente=semente, ramo="entrega")

    assert [c.situacao for c in historico.commits] == [VERDE, VERMELHO_INESPERADO, VERMELHO_ESPERADO]


def test_merge_na_entrega_mede_so_a_linha_dela_edge_case(tmp_path: Path) -> None:
    """Caso de borda (E2): o commit vermelho que só entrou pelo lado mesclado de um merge não é da entrega e não é medido."""
    repositorio = criar_repositorio(tmp_path / "brinquedo")
    semente = git(repositorio, "rev-parse", "HEAD").strip()
    git(repositorio, "checkout", "-q", "-b", "lado")
    _commitar(repositorio, VERMELHO_PY, "Commit do humano na base, vermelho")
    _commitar(repositorio, VERDE_PY, "Conserta na base")
    git(repositorio, "checkout", "-q", "-b", "entrega", semente)
    (repositorio / "outro.txt").write_text("x\n", encoding="utf-8")
    _commitar(repositorio, VERDE_PY, mensagem_do_orquestrador("Fatia F1", "", id_goal="goal-x", id_task="task-x-f1"))
    git(repositorio, "merge", "-q", "--no-edit", "lado")
    git(repositorio, "checkout", "-q", "main")

    historico = medir_historico(repositorio, CHECAGEM, semente=semente, ramo="entrega")

    assert [c.assunto for c in historico.commits] == ["Fatia F1", "Merge branch 'lado' into entrega"]
    assert historico.contar(VERMELHO_INESPERADO) == 0


def test_suite_que_estoura_o_tempo_nao_derruba_as_outras_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a suíte do commit do meio passa do tempo-limite; ela é vermelha, e as outras são medidas."""
    repositorio, semente = _brinquedo(
        tmp_path, (VERDE_PY, "Fatia F1"), (DEMORADO_PY, "Fatia F2"), (VERDE_PY, "Fatia F3"))

    historico = medir_historico(repositorio, CHECAGEM, semente=semente, ramo="entrega", tempo_limite_s=3.0)

    assert [c.situacao for c in historico.commits] == [VERDE, VERMELHO_INESPERADO, VERDE]
    assert historico.commits[1].tempo_esgotado


def test_sem_comando_ou_sem_o_ramo_fica_sem_medida_com_o_motivo_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a arquitetura sem plano (a enxuta) não tem comando; o ramo que não existe vira o erro, sem exceção."""
    repositorio, semente = _brinquedo(tmp_path, (VERDE_PY, "Fatia F1"))

    sem_plano = historico_da_execucao(PedidoDoHistorico(tmp_path, repositorio, tmp_path / "graphow.db", semente, "entrega"))
    sem_ramo = medir_historico(repositorio, CHECAGEM, semente=semente, ramo="nao-existe")

    assert sem_plano.erro.startswith("sem comando da suite") and sem_plano.commits == ()
    assert sem_ramo.erro and sem_ramo.commits == ()


def test_historico_sozinho_sobre_uma_execucao_regrava_o_execucao_json_nominal(tmp_path: Path) -> None:
    """`graphow bancada historico --execucao` mede uma execução que já existe e grava a chave `historico`."""
    execucao = tmp_path / "enxuta-brinquedo-20261029-075546"
    execucao.mkdir()
    repositorio, semente = _brinquedo(execucao, (VERDE_PY, "Fatia F1"), (VERMELHO_PY, "Fatia F2"))
    registro = {"semente": semente, "repositorio": repositorio.name, "entrega": {"ramo": "entrega"}, "erro": ""}
    (execucao / "execucao.json").write_text(json.dumps(registro), encoding="utf-8")
    console = EscritorConsoleEmMemoria()
    argumentos = construir_parser().parse_args(
        ["bancada", "historico", "--execucao", str(execucao), "--comando", CHECAGEM, "--tempo-limite-suite", "2"])

    codigo = executar_bancada(argumentos, console)

    gravado = json.loads((execucao / "execucao.json").read_text(encoding="utf-8"))
    assert argumentos.comando == "bancada", "o --comando da suite nao toma o lugar do subcomando do graphow"
    assert codigo == 0 and gravado["semente"] == semente
    assert (gravado["historico"]["verdes"], gravado["historico"]["vermelhos_inesperados"]) == (1, 1)
    assert console.linhas[-1] == "  1 verde(s), 0 vermelho(s) esperado(s), 1 vermelho(s) inesperado(s) em 2 commit(s)"
