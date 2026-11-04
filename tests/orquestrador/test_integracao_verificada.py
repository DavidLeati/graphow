"""A integração do Goal (revisão da T3g3 e da T3g4): o cancelamento que chega com a queda logo depois do fast-forward."""

from pathlib import Path

import pytest

from graphow.core.types import TipoNo
from graphow.orquestrador import laco, verificacao_do_goal
from graphow.orquestrador.contexto_do_laco import MotivoDaParada
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_CANCELAR, NovoPedido
from graphow.orquestrador.refs_do_humano import integrar_por_fast_forward

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import Queda, ate_o_portao_aprovado, montar_bancada
from tests.orquestrador.test_base_que_andou import AUTONOMO, RAMO, _roteiro_limpo

CANCELAR: NovoPedido = NovoPedido(PEDIDO_CANCELAR, "desisti tarde", "david")


def test_queda_logo_depois_do_fast_forward_com_o_cancelamento_no_meio_anota_na_retomada_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3g5.4 (T3 da sonda): o fast-forward acontece, o cancelamento chega e o processo cai; a execução seguinte anota e para."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = bancada.orquestrador()

    def integrar_cancelar_e_cair(repositorio: Path, ramo: str, base: str, **verificada: str) -> str:
        integrar_por_fast_forward(repositorio, ramo, base, **verificada)
        orquestrador.pedir("goal-soma", CANCELAR)
        raise Queda()

    monkeypatch.setattr(verificacao_do_goal, "integrar_por_fast_forward", integrar_cancelar_e_cair)
    with pytest.raises(Queda):
        orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    monkeypatch.undo()

    parada = bancada.orquestrador().rodar("goal-soma", AUTONOMO)

    integrado = git(bancada.repositorio, "rev-parse", "main").strip()
    assert integrado == git(bancada.repositorio, "rev-parse", RAMO).strip(), "o fast-forward aconteceu antes da queda"
    assert parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
    assert "cancelado tarde" in parada.mensagem and integrado[:12] in parada.mensagem and "desisti tarde" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.cancelado
    tardio = estado.propriedades["cancelamento_tardio"]
    assert tardio["integrado"] == integrado and "Na retomada" in tardio["texto"]
    nota = bancada.kernel.obter_view().obter_no(tardio["evidencia"])
    assert nota is not None and nota.tipo == TipoNo.EVIDENCE and nota.obter_propriedade("acao") == "cancelamento_tardio"
    assert nota.obter_propriedade("commit") == integrado and nota.obter_propriedade("motivo") == "desisti tarde"
    de_novo = bancada.orquestrador().rodar("goal-soma", AUTONOMO)
    assert de_novo.motivo == MotivoDaParada.CANCELADO and "cancelado tarde" not in de_novo.mensagem, "a nota e gravada uma vez"


def test_goal_cancelado_com_o_trabalho_fora_da_base_nao_ganha_a_nota_nominal(tmp_path: Path) -> None:
    """Contraprova de T3g5.4: o Goal cancelado no portão do plano tem a ponta fora da base; a retomada só para."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = ate_o_portao_aprovado(bancada)
    orquestrador.pedir("goal-soma", CANCELAR)

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
    assert "cancelamento_tardio" not in estado.propriedades and "cancelado tarde" not in parada.mensagem


def test_goal_cancelado_antes_do_primeiro_commit_tem_a_ponta_na_base_e_nao_ganha_a_nota_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contraprova de T3g5.4: a ponta gravada é a própria base (o Goal não commitou nada); sem o trailer dele, não há nota."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())

    def cair(*_: object) -> None:
        raise Queda()

    monkeypatch.setattr(laco, "planejar", cair)
    with pytest.raises(Queda):
        bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    monkeypatch.undo()
    orquestrador = bancada.orquestrador()
    orquestrador.pedir("goal-soma", CANCELAR)

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
    ponta = estado.propriedades["ponta_do_ramo"]["commit"]
    assert ponta == git(bancada.repositorio, "rev-parse", "main").strip(), "a ponta gravada esta na base"
    assert "cancelamento_tardio" not in estado.propriedades
