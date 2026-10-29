"""A verificação final que deixou de valer não some com os bloqueantes que ela abriu (T2m.3).

Na sonda K4 da revisão da T2k+T2l, o commit das pendências contava como
código, e a verificação com o bloqueante aberto deixava de valer. A
conferência que a refazia não o conferia (nenhuma correção tinha nascido
dela), saía limpa, e o laço tentava fechar com ele aberto: o kernel recusava
o lote, e o laço parava em falha (`LoteRecusado`). O commit que tira a
verificação do commit atual pode vir de outro lugar, como o refazer do aceite
que o humano pede depois dos bloqueantes restantes.
"""

from pathlib import Path

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_REFAZER_ACEITE, NovoPedido

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    Bancada,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)
from tests.orquestrador.test_vermelho_do_refeito import ACEITE_COM_NEGATIVOS, _refeito

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def test_conferencia_limpa_depois_da_verificacao_que_deixou_de_valer_para_em_bloqueantes_restantes_nominal(tmp_path: Path) -> None:
    """T2m.3: o bloqueante do README persiste até a 3ª, sem ciclo; o humano refaz o aceite de C1, e a 4ª sai limpa sem conferi-lo."""
    roteiro = roteiro_completo()
    roteiro["aceite"].append(_refeito(ACEITE_COM_NEGATIVOS))
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "x\n"}))
    roteiro["verificador"] = [
        verificacao("parcial", [BLOQUEANTE_DO_README]),
        verificacao("atende", [{**BLOQUEANTE_DO_README, "persiste": "achado-goal-soma-v1-1"}]),
        verificacao("atende", [{**BLOQUEANTE_DO_README, "persiste": "achado-goal-soma-v2-1"}]),
        verificacao("atende"),
    ]
    roteiro["revisor"] = [revisao() for _ in range(8)]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    antes = orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"))

    depois = orquestrador.rodar("goal-soma", AUTONOMO)

    assert antes.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, antes.mensagem
    estado = _estado(bancada)
    assert len(estado.verificacoes) == 4 and estado.verificacoes[3].bloqueantes() == ()
    assert estado.verificacoes[2].achados[0].estado == "aberto"
    assert depois.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, depois.mensagem
    assert "achado-goal-soma-v3-1" in depois.mensagem
