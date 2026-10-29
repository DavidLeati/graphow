"""O desacordo sobre o teste de aceite de um critério expira quando o teste dele é refeito (T2m.4).

Na revisão da T2k+T2l, `criterios_em_desacordo` valia para sempre: depois de
um refazer que mudava o teste do critério, a conferência ainda julgava o
critério sozinha, e a regra (orquestrador/regra_da_conferencia.py) nunca mais
virava o parecer dele. Agora o desacordo leva o commit do aceite que o
critério tinha quando ele nasceu, e vale enquanto o Criterio tem esse commit.
"""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_REFAZER_ACEITE, NovoPedido
from graphow.orquestrador.saida_do_verificador import MARCA_DO_PARECER
from graphow.orquestrador.tipo_da_verificacao import criterios_em_desacordo
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, ResultadoDeSessao

from tests.orquestrador.apoio_laco import Bancada, Queda, montar_bancada, roteiro_completo, verificacao
from tests.orquestrador.test_regra_da_conferencia import NEGATIVOS_QUEBRADOS, _mantido, _teste_errado
from tests.orquestrador.test_vermelho_do_refeito import ACEITE_COM_NEGATIVOS, _refeito

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


class CaiNaConferencia(ExecutorDeSessao):
    """Cai antes da primeira sessão da conferência, sem rodá-la: o roteiro não gasta a resposta dela."""

    def __init__(self, base: ExecutorDeSessao) -> None:
        super().__init__(base._executavel, base._ambiente)
        self.caiu: bool = False

    def rodar(self, pedido: PedidoDeSessao) -> ResultadoDeSessao:
        """A sessão roda, menos a primeira conferência, onde o processo cai."""
        if not self.caiu and "## Achados conferidos" in pedido.prompt:
            self.caiu = True
            raise Queda()
        return super().rodar(pedido)


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def _roteiro() -> dict[str, list[dict[str, Any]]]:
    """O T2k.5: a correção diz que o teste de C1 está errado e o autor o mantém; a conferência reprova C1 por um achado novo."""
    julgou = verificacao("atende", [{**NEGATIVOS_QUEBRADOS, "titulo": "C1 nao atendido (desacordo julgado)",
                                     "local": "soma.py:1", "regressao": False}])
    julgou["saida"]["criterios"][0] = {"id": "C1", "veredito": "nao_atende", "prova": "julguei o desacordo: o executor tem razao"}
    roteiro = roteiro_completo()
    roteiro["executor"].insert(2, _teste_errado())
    roteiro["aceite"] += [_mantido(), _refeito(ACEITE_COM_NEGATIVOS)]
    roteiro["verificador"][1] = julgou
    return roteiro


def test_refazer_que_muda_o_teste_devolve_o_criterio_em_desacordo_a_regra_nominal(tmp_path: Path) -> None:
    """T2m.4: o desacordo de C1 nasce do autor que mantém o teste; o humano o refaz; a conferência que reprova C1 volta à regra."""
    bancada = montar_bancada(tmp_path, _roteiro())
    with pytest.raises(Queda):
        bancada.orquestrador(executor=CaiNaConferencia(bancada.executor)).iniciar_da_spec(
            bancada.spec, bancada.repositorio, AUTONOMO)
    assert criterios_em_desacordo(_estado(bancada)) == frozenset({"C1"})
    orquestrador = bancada.orquestrador()
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"))

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    estado = _estado(bancada)
    assert criterios_em_desacordo(estado) == frozenset()
    assert "o autor o manteve" not in bancada.chamadas("conferencia")[-1]["stdin"]
    pareceres = {str(p["id"]): str(p["veredito"]) for p in estado.verificacoes[1].propriedades["pareceres"]}
    assert pareceres["C1"] == "atende"
    assert MARCA_DO_PARECER in [x.texto("marca") for x in estado.verificacoes[1].achados]
    assert parada.fechou, parada.mensagem
