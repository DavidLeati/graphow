"""A revisão de risco rejeitada confere no clone do Goal, onde a árvore dela ficou; sem o clone, sai não conferida.

A tentativa rejeitada não vira commit: a `arvore` que a revisão grava fica
solta no clone, e o repositório do humano só recebe o que a branch alcança. Na
revisão da T3d2, a vista e o canvas a conferiam no repositório do humano, ela
saía `sem_ancora`, e o inspetor dizia "gravada sem o commit", o que era falso.

No roteiro, a tentativa rejeitada já traz soma.py e verificar.py certos; a
aprovada repete os dois e acrescenta um teste de negativos. A árvore da
rejeitada não é a de commit nenhum, e os arquivos que ela afirma não mudaram
até a ponta: com o clone, ela está vigente.
"""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.core.types import PapelAutor
from graphow.orquestrador import verificacao_do_goal
from graphow.orquestrador.conferencia_na_leitura import LeituraPorGoal
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.git_do_goal import GitDoGoal, remover_area
from graphow.web.rest_canvas_controller import CanvasWebController

from tests.orquestrador.apoio_laco import (
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    Bancada,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)

REJEITADA: str = "rev-task-soma-f1-t1"
APROVADA: str = "rev-task-soma-f1-t2"
NEGATIVOS: str = "from soma import somar\nassert somar(-2, -3) == -5\n"


def _roteiro_com_revisao_rejeitada() -> dict[str, list[dict[str, Any]]]:
    """F1 de risco: a primeira tentativa é rejeitada, e a segunda acrescenta um arquivo sem mexer nos da primeira."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][0].update(risco=True, motivo_do_risco="regra de dominio da soma")
    roteiro = roteiro_completo()
    certos = {"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}
    roteiro.update(planejador=[{"saida": plano, "custo": 0.4}], verificador=[verificacao("atende")],
                   revisor=[revisao("rejeitado"), revisao()],
                   executor=[executor_pronto(certos), executor_pronto({**certos, "negativos.py": NEGATIVOS}), roteiro["executor"][1]])
    return roteiro


def _fechado_com_o_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Bancada, Path]:
    """O Goal fechado no autônomo, com o clone deixado no disco (o fecho o apagaria)."""
    monkeypatch.setattr(verificacao_do_goal, "remover_area", lambda _area: False)
    bancada = montar_bancada(tmp_path, _roteiro_com_revisao_rejeitada())
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco(modo="autonomo"))
    assert parada.fechou, parada.mensagem
    return bancada, bancada.raiz / "estado" / "goal-soma" / "area"


def test_revisao_rejeitada_vigente_com_o_clone_e_nao_conferida_sem_ele_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T3d3.2: com o clone, a rejeitada sai vigente; sem ele, não conferida, e o canvas e a vista dizem o motivo."""
    bancada, clone = _fechado_com_o_clone(tmp_path, monkeypatch)
    view = bancada.kernel.obter_view()
    rejeitada = view.obter_no(REJEITADA)
    assert rejeitada is not None and rejeitada.obter_propriedade("veredito") == "rejeitado"
    arvore = f"{rejeitada.obter_propriedade('arvore')}^{{tree}}"
    assert GitDoGoal(clone).tentar("cat-file", "-e", arvore).codigo == 0
    assert GitDoGoal(bancada.repositorio).tentar("cat-file", "-e", arvore).codigo != 0, "a arvore so ficou no clone"

    com_clone = LeituraPorGoal(view).conferir(rejeitada)
    assert remover_area(clone)
    sem_clone = LeituraPorGoal(view).conferir(rejeitada)
    canvas = {no.id: no.conferencia or {} for no in CanvasWebController(bancada.kernel).obter_canvas().nos}
    vista = MaterializadorContexto().materializar(RequisicaoVista("task-soma-f1", PapelAutor.EXECUTOR, orcamento_tokens=50000), view)

    assert com_clone is not None and (com_clone.estado, com_clone.arquivos) == ("vigente", ())
    assert sem_clone is not None and sem_clone.estado == "nao_conferida"
    assert f"a arvore revisada {arvore[:12]} so ficou no clone do Goal, que nao existe mais: {clone}" == sem_clone.motivo
    assert canvas[REJEITADA] == {"estado": "nao_conferida", "arquivos": [], "motivo": sem_clone.motivo, "rotulo": "nao conferida",
                                 "marca": f"nao conferida: {sem_clone.motivo}"}
    assert canvas[APROVADA]["estado"] == "vigente", "a arvore da aprovada e a do commit da fatia, no repositorio do humano"
    assert f"- [{REJEITADA}] [nao conferida: a arvore revisada {arvore[:12]} so ficou no clone do Goal" in vista.conteudo_formatado
