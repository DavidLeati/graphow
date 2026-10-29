"""O pedido do humano atendido depois de a fatia cair no meio da sessão do executor (sondas 2 e 3 da revisão da T2i+T2g).

O commit do pedido fazia `git add -A`: o trabalho pela metade da fatia, com
um conftest.py que tem `pytest_pyfunc_call`, entrava na branch do Goal, e a
tentativa seguinte, comparando com o próprio HEAD, não o recusava. Agora o
pedido commita só o que escreveu, e o que a fatia deixou vai ao .patch dela.
"""

from pathlib import Path

import pytest

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_REFAZER_ACEITE, PEDIDO_RETIRAR_CRITERIO, NovoPedido

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import SOMA_CERTA, VERIFICAR, Bancada, ExecutorQueCai, Queda, executor_pronto, montar_bancada
from tests.orquestrador.test_diferenca_de_configuracao import FINGE_QUE_PASSA
from tests.orquestrador.test_o_que_chega_a_correcao import _mantido
from tests.orquestrador.test_retomada import roteiro_farto

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
PELA_METADE: dict[str, str] = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR, "conftest.py": FINGE_QUE_PASSA,
                               "metade.txt": "trabalho pela metade\n"}


def _cai_no_executor(tmp_path: Path, *, de_novo_com_o_conftest: bool = False) -> Bancada:
    """O Goal planejado, com o aceite, e a fatia F1 caída no meio da sessão do executor, com o trabalho pela metade na área."""
    roteiro = roteiro_farto()
    roteiro["executor"][0] = executor_pronto(dict(PELA_METADE))
    if de_novo_com_o_conftest:
        roteiro["executor"][1] = executor_pronto(dict(PELA_METADE))
    roteiro["aceite"].insert(1, _mantido())
    bancada = montar_bancada(tmp_path, roteiro)
    with pytest.raises(Queda):
        bancada.orquestrador(executor=ExecutorQueCai(bancada.executor, 3)).iniciar_da_spec(
            bancada.spec, bancada.repositorio, AUTONOMO)
    assert [c["papel"] for c in bancada.chamadas()] == ["planejador", "aceite", "executor"]
    return bancada


def _ramo(bancada: Bancada) -> str:
    """A branch do Goal."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.configuracao is not None
    return estado.configuracao.ramo


def _commit_com(bancada: Bancada, assunto: str) -> list[str]:
    """Os arquivos do commit da branch do Goal com o assunto dado."""
    log = git(bancada.repositorio, "log", "--format=%H %s", _ramo(bancada)).splitlines()
    commit = next(linha.split(" ", 1)[0] for linha in log if assunto in linha)
    return git(bancada.repositorio, "show", "--name-only", "--format=", commit).split()


def test_retirada_depois_da_queda_commita_so_o_documento_e_a_tentativa_seguinte_recusa_o_conftest_edge_case(
        tmp_path: Path) -> None:
    """T2l.1: o commit da retirada leva só o documento; a metade fica no .patch da fatia, e o conftest de novo é recusado."""
    bancada = _cai_no_executor(tmp_path, de_novo_com_o_conftest=True)
    orquestrador = bancada.orquestrador()
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RETIRAR_CRITERIO, "C2 fica para outro Goal", "david", alvo="C2"))

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert _commit_com(bancada, "Registra os criterios retirados") == ["docs/goals/soma.md"]
    patch = next((bancada.raiz / "estado").rglob("*-t1-interrompida.patch")).read_text(encoding="utf-8")
    assert "conftest.py" in patch and "metade.txt" in patch and "pytest_pyfunc_call" in patch
    na_branch = git(bancada.repositorio, "ls-tree", "-r", "--name-only", _ramo(bancada)).split()
    assert "conftest.py" not in na_branch and "metade.txt" not in na_branch
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    f1 = next(fatia for fatia in estado.fatias if fatia.codigo == "F1")
    assert parada.motivo == MotivoDaParada.PENDENCIA and f1.falhas == 2
    assert "conftest.py com hook do pytest que decide o resultado" in f1.texto(m.CAMPO_ULTIMO_ERRO)


def test_refazer_depois_da_queda_nao_culpa_o_autor_de_aceite_pelos_arquivos_do_executor_edge_case(tmp_path: Path) -> None:
    """T2l.2: antes do refazer, a metade da fatia vai ao .patch dela; o autor mantém C1 na primeira volta, e o Goal fecha."""
    bancada = _cai_no_executor(tmp_path)
    orquestrador = bancada.orquestrador()
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste de C1 me parece errado", "david", alvo="C1"))

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    patches = [caminho.name for caminho in (bancada.raiz / "estado").rglob("*.patch")]
    assert not [nome for nome in patches if nome.startswith("aceite-refeito")], patches
    metade = next((bancada.raiz / "estado").rglob("*-t1-interrompida.patch")).read_text(encoding="utf-8")
    assert "metade.txt" in metade and "conftest.py" in metade
    assert len(bancada.chamadas("aceite")) == 2
    refeito = _commit_com(bancada, "os testes de aceite de C1")
    assert all(caminho.startswith("aceite/") for caminho in refeito), refeito
    na_branch = git(bancada.repositorio, "ls-tree", "-r", "--name-only", _ramo(bancada)).split()
    assert "conftest.py" not in na_branch and "metade.txt" not in na_branch
