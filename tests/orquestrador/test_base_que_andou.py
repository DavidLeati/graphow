"""A integração do Goal: o cancelamento que chega no meio do passo, e a base que andou desde que a branch do Goal saiu dela."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal
from graphow.orquestrador.pedidos_do_humano import PEDIDO_CANCELAR, NovoPedido

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo, verificacao

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _roteiro_limpo() -> dict[str, list[dict[str, object]]]:
    """Plano, aceite, as duas fatias e a verificação final limpa de primeira."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende")]
    roteiro["executor"] = roteiro["executor"][:2]
    return roteiro


def test_cancelamento_que_chega_no_meio_do_passo_impede_a_integracao_edge_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso de borda (revisão da T3b, achado 7): o `--cancelar` gravado depois da leitura do passo não deixa o Goal integrar."""
    bancada = montar_bancada(tmp_path, _roteiro_limpo())
    orquestrador = bancada.orquestrador()
    original = LivroRazaoDoGoal.resolver

    def resolver_e_cancelar(livro: LivroRazaoDoGoal, achados: Sequence[str], justificativa: str) -> None:
        orquestrador.pedir(livro.id_goal, NovoPedido(PEDIDO_CANCELAR, "desisti durante o fechamento", "david"))
        original(livro, achados, justificativa)

    monkeypatch.setattr(LivroRazaoDoGoal, "resolver", resolver_e_cancelar)
    base_antes = git(bancada.repositorio, "rev-parse", "main").strip()

    parada = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.CANCELADO, parada.mensagem
    assert "antes da integracao" in parada.mensagem and "desisti durante o fechamento" in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", "main").strip() == base_antes, "a base nao recebe o Goal cancelado"
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and estado.cancelado
