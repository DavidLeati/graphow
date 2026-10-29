"""O que a suíte escreve não entra em commit do laço (T2m.2, T2m.3).

Na revisão da T2k+T2l, as recusas por código olhavam a área antes da suíte, e
o commit depois dela fazia `git add -A`. Um `verificar.py` que gerava um
conftest.py com `pytest_pyfunc_call` o levava à base no commit da fatia e no
"Registra as pendencias" (L2). A suíte que reescrevia um arquivo a cada
rodada o punha em cada commit: o arquivo passava a contar como de critério, a
borda antiga do README voltava a ser regressão confirmada, e o commit das
pendências contava como código (K4).
"""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco, Parada
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.saida_do_verificador import MARCA_DA_REGRESSAO
from graphow.orquestrador.suite_sem_rastro import sem_o_que_a_suite_escreve

from tests.orquestrador.apoio_git import criar_repositorio, git
from tests.orquestrador.apoio_laco import (
    ACOMPANHAMENTO,
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    SOMA_CERTA,
    SOMA_COM_DOCSTRING,
    Bancada,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)
from tests.orquestrador.test_diferenca_de_configuracao import FINGE_QUE_PASSA
from tests.orquestrador.test_regra_da_conferencia import EXEMPLO_ERRADO, NEGATIVOS_QUEBRADOS

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
VERIFICAR_COM_REGISTRO: str = (
    "from pathlib import Path\nfrom soma import somar\nassert somar(2, 3) == 5, 'C1'\n"
    "p = Path('ultima_rodada.txt')\nn = int(p.read_text()) + 1 if p.exists() else 1\np.write_text(str(n))\nprint('ok')\n"
)


def _rodar(tmp_path: Path, roteiro: dict[str, list[dict[str, Any]]]) -> tuple[Bancada, Parada, EstadoDoGoal]:
    """O laço autônomo da spec com o roteiro dado: a bancada, a parada e o estado do Goal."""
    bancada = montar_bancada(tmp_path, roteiro)
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return bancada, parada, estado


def _arquivos(bancada: Bancada, commit: str) -> list[str]:
    """Os arquivos que o commit mudou."""
    return git(bancada.repositorio, "show", "--name-only", "--format=", commit).split()


def _commits_com(bancada: Bancada, caminho: str) -> list[str]:
    """O assunto de cada commit da base que mudou o caminho dado."""
    log = git(bancada.repositorio, "log", "--format=%H %s", "main").splitlines()
    return [linha[41:] for linha in log if caminho in _arquivos(bancada, linha[:40])]


def _verificar_que_gera_o_conftest(contador: Path, a_partir_da_rodada: int) -> str:
    """Um verificar.py que conta as rodadas fora da área e, a partir da dada, escreve um conftest.py que dá verde a tudo."""
    return (
        "from pathlib import Path\nfrom soma import somar\nassert somar(2, 3) == 5, 'C1'\n"
        f"p = Path({contador.as_posix()!r})\nn = int(p.read_text()) + 1 if p.exists() else 1\np.write_text(str(n))\n"
        f"if n >= {a_partir_da_rodada}:\n    Path('conftest.py').write_text({FINGE_QUE_PASSA!r})\nprint('ok')\n"
    )


@pytest.mark.parametrize(("rodada", "rastro", "assunto"), [
    (1, "-t1-suite.patch", "Fatia F1"), (3, "suite-1.patch", "Registra as pendencias da verificacao 1")],
    ids=["fatia", "pendencias"])
def test_conftest_que_a_suite_escreve_nao_chega_a_base_nominal(tmp_path: Path, rodada: int, rastro: str, assunto: str) -> None:
    """T2m.2 (L2): a suíte escreve o conftest.py com o hook; ele vai ao .patch dela e não entra no commit da fatia nem no das pendências."""
    roteiro = roteiro_completo()
    verificar = _verificar_que_gera_o_conftest(tmp_path / "rodadas.txt", rodada)
    roteiro["executor"][0] = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": verificar})
    roteiro["verificador"] = [verificacao("atende", [ACOMPANHAMENTO]), verificacao("atende"), verificacao("atende")]

    bancada, parada, _ = _rodar(tmp_path, roteiro)

    assert parada.fechou, parada.mensagem
    assert _commits_com(bancada, "conftest.py") == []
    assert "conftest.py" not in git(bancada.repositorio, "ls-tree", "-r", "--name-only", "main").split()
    guardado = next(p for p in (bancada.raiz / "estado").rglob("*.patch") if p.name.endswith(rastro))
    assert "pytest_pyfunc_call" in guardado.read_text(encoding="utf-8")
    commit = next(linha[:40] for linha in git(bancada.repositorio, "log", "--format=%H %s", "main").splitlines() if assunto in linha)
    assert "conftest.py" not in _arquivos(bancada, commit)


def test_a_area_volta_a_arvore_conferida_sem_tocar_nos_ignorados_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o que a suíte cria, muda ou apaga volta à árvore de antes dela; a entrega fica fora do índice, e o ignorado fica."""
    area = criar_repositorio(tmp_path / "area", {".gitignore": "cache/\n", "soma.py": SOMA_CERTA, "README.md": "# x\n"})
    (area / "cache").mkdir()
    (area / "cache" / "velho.bin").write_text("antes", encoding="utf-8")
    (area / "novo.py").write_text("x = 1\n", encoding="utf-8")
    (area / "README.md").write_text("# mudado pelo executor\n", encoding="utf-8")

    with sem_o_que_a_suite_escreve(area, tmp_path / "suite.patch"):
        (area / "conftest.py").write_text(FINGE_QUE_PASSA, encoding="utf-8")
        (area / "soma.py").write_text("quebrado\n", encoding="utf-8")
        (area / "novo.py").unlink()
        (area / "cache" / "velho.bin").write_text("a suite mexeu", encoding="utf-8")
        (area / "cache" / "novo.bin").write_text("cache novo", encoding="utf-8")

    assert not (area / "conftest.py").exists()
    assert (area / "soma.py").read_text(encoding="utf-8") == SOMA_CERTA
    assert (area / "novo.py").read_text(encoding="utf-8") == "x = 1\n"
    assert (area / "README.md").read_text(encoding="utf-8") == "# mudado pelo executor\n"
    assert (area / "cache" / "velho.bin").read_text(encoding="utf-8") == "a suite mexeu" and (area / "cache" / "novo.bin").exists()
    assert git(area, "diff", "--cached", "--name-only").strip() == ""
    assert "pytest_pyfunc_call" in (tmp_path / "suite.patch").read_text(encoding="utf-8")


def test_suite_que_reescreve_arquivo_nao_confirma_a_borda_antiga_nem_para_em_falha_nominal(tmp_path: Path) -> None:
    """T2m.3 (K4): o S-D com a suíte que reescreve um arquivo a cada rodada; o arquivo não entra no commit, e o Goal fecha."""
    reg_c1 = {**NEGATIVOS_QUEBRADOS, "titulo": "somar(-2, -3) errado", "local": "soma.py:2"}
    reg_c2 = {**EXEMPLO_ERRADO, "titulo": "README sem exemplo com zero", "descricao": "borda antiga dita regressao"}
    roteiro = roteiro_completo()
    roteiro["executor"][0] = executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR_COM_REGISTRO})
    roteiro["executor"][2] = executor_pronto({"README.md": README_COM_EXEMPLO, "soma.py": SOMA_COM_DOCSTRING})
    roteiro["executor"].append(executor_pronto({"soma.py": "# so um comentario\n" + SOMA_COM_DOCSTRING}))
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "x\n"}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [reg_c1]),
                              verificacao("atende", [reg_c2]), verificacao("atende")]
    roteiro["revisor"] = [revisao() for _ in range(8)]

    bancada, parada, estado = _rodar(tmp_path, roteiro)

    assert parada.motivo != MotivoDaParada.FALHA, parada.mensagem
    assert parada.fechou, parada.mensagem
    k2 = next(f for f in estado.fatias if f.codigo == "M1.K2.1")
    assert _arquivos(bancada, k2.texto("commit")) == ["soma.py"]
    assert _commits_com(bancada, "ultima_rodada.txt") == []
    terceira = estado.verificacoes[2]
    assert terceira.bloqueantes() == ()
    assert [(x.texto("titulo"), x.gravidade, x.texto("marca")) for x in terceira.achados] == [
        ("README sem exemplo com zero", "acompanhamento", MARCA_DA_REGRESSAO)]
    assert len(estado.verificacoes) == 3
