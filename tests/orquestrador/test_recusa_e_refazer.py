"""Recusar o plano e refazer o aceite: as saídas do humano que pedem trabalho de novo ao planejador ou ao autor de aceite."""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.pedidos_do_humano import PEDIDO_RECUSAR_PLANO, PEDIDO_REFAZER_ACEITE, NovoPedido, PedidoRecusado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    ACEITE_C1,
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _so_c1() -> tuple[dict[str, Any], dict[str, Any]]:
    """Um plano só com C1 e F1, e o aceite dele: o que o planejador devolve depois da recusa."""
    plano = copy.deepcopy(PLANO)
    plano["titulo"] = "Soma, so a funcao"
    plano["criterios"] = plano["criterios"][:1]
    plano["fatias"] = plano["fatias"][:1]
    plano["marcos"] = [{"id": "M1", "titulo": "Soma", "fatias": ["F1"]}]
    aceite = autor_de_aceite()
    aceite["saida"]["criterios"] = aceite["saida"]["criterios"][:1]
    return plano, aceite


def test_recusar_o_plano_no_portao_faz_o_planejador_refaze_lo_com_o_motivo_nominal(tmp_path: Path) -> None:
    """Bloqueante 3 e acompanhamento 6: o humano recusa no portão; o plano novo, só com C1, roda e fecha; C2 fica retirado."""
    plano, aceite = _so_c1()
    roteiro = roteiro_completo()
    roteiro["planejador"].append({"saida": plano, "custo": 0.4})
    roteiro["aceite"].append(aceite)
    roteiro["executor"] = roteiro["executor"][:1]
    roteiro["verificador"] = [verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco()).motivo == MotivoDaParada.AGUARDANDO_APROVACAO

    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RECUSAR_PLANO, "o README fica para outro Goal", "david"))
    no_portao = orquestrador.rodar("goal-soma", OpcoesDoLaco())
    orquestrador.aprovar_plano("goal-soma", "david")
    fechado = orquestrador.rodar("goal-soma", AUTONOMO)

    assert no_portao.motivo == MotivoDaParada.AGUARDANDO_APROVACAO and "--recusar-plano" in no_portao.mensagem
    assert fechado.fechou, fechado.mensagem
    segundo = bancada.chamadas("planejador")[1]["stdin"]
    assert "O humano recusou o plano anterior" in segundo and "o README fica para outro Goal" in segundo
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [f.id for f in estado.fatias] == ["task-soma-v2-f1"]
    assert len(estado.propriedades["planos_recusados"]) == 1
    c2 = bancada.kernel.obter_view().obter_no("crit-soma-c2")
    assert c2 is not None and c2.obter_propriedade("retirado")["decisao"] == "pedido-goal-soma-1"
    assuntos = git(bancada.repositorio, "log", "--format=%s", "main")
    assert "Retira os testes de aceite do plano recusado do Goal soma" in assuntos


def test_plano_que_ja_rodou_nao_se_recusa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: depois que uma fatia rodou, recusar o plano é recusado; o que sobra é cancelar."""
    roteiro = roteiro_completo()
    roteiro["executor"] = roteiro["executor"][:1] + [{"saida": {"status": "duvida", "resumo": "?", "arquivos": [], "testes": [],
                                                               "duvida": "Inteiros ou decimais?"}, "custo": 0.1}]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo == MotivoDaParada.AGUARDANDO_RESPOSTA

    with pytest.raises(PedidoRecusado) as recusa:
        orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_RECUSAR_PLANO, "mudei de ideia", "david"))

    assert "ja rodaram" in recusa.value.formatar_para_llm() and "--cancelar" in recusa.value.formatar_para_llm()


def test_duvida_de_teste_errado_respondida_refaz_o_aceite_do_criterio_nominal(tmp_path: Path) -> None:
    """Bloqueante 3: o executor diz que o teste de C1 está errado; o humano responde; o autor refaz C1 e a fatia segue."""
    roteiro = roteiro_completo()
    duvida = {"saida": {"status": "duvida", "resumo": "o teste pede 5 para 2+3, mas a spec fala em inteiros", "arquivos": [],
                        "testes": [], "duvida": "O teste de C1 esta errado?", "teste_errado": "C1"}, "custo": 0.1}
    refeito = autor_de_aceite()
    refeito["saida"]["criterios"] = refeito["saida"]["criterios"][:1]
    refeito["arquivos"] = {"aceite/aceite_c1.py": ACEITE_C1.replace("test_c1_soma()\n", "test_c1_soma()\nprint('refeito')\n")}
    roteiro["aceite"].append(refeito)
    roteiro["executor"].insert(0, duvida)
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo == MotivoDaParada.AGUARDANDO_RESPOSTA
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    questao = estado.fatias[0].duvidas[0]
    commit_antes = estado.aceite["commit"]
    resposta = (ItemPatch(OperacaoPatch.REPLACE, f"/nos/{questao.id}/propriedades/status", "respondida"),
                ItemPatch(OperacaoPatch.REPLACE, f"/nos/{questao.id}/propriedades/resposta", "o teste precisa imprimir que refez"))
    assert bancada.kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=resposta, justificativa="resposta"))).sucesso

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert questao.criterio_do_teste == "C1"
    refazer = bancada.chamadas("aceite")[1]["stdin"]
    assert "Refazer os testes de aceite de C1" in refazer and "o teste precisa imprimir que refez" in refazer
    final = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert final is not None and final.aceite["commit"] != commit_antes and final.aceite["revisoes"] == 1
    assert questao.id in final.propriedades["pedidos_atendidos"]
    assert "print('refeito')" in (bancada.repositorio / "aceite" / "aceite_c1.py").read_text(encoding="utf-8")
    assert "Refaz os testes de aceite de C1 do Goal soma" in git(bancada.repositorio, "log", "--format=%s", "main")


def test_refazer_aceite_pela_cli_no_modo_supervisionado_volta_ao_portao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: refazer o aceite depois da aprovação faz o portão voltar, porque os testes aprovados mudaram."""
    refeito = autor_de_aceite()
    refeito["saida"]["criterios"] = refeito["saida"]["criterios"][:1]
    refeito["arquivos"] = {"aceite/aceite_c1.py": ACEITE_C1 + "# refeito\n"}
    roteiro = roteiro_completo()
    roteiro["aceite"].append(refeito)
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    orquestrador.aprovar_plano("goal-soma", "david")

    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"))
    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.AGUARDANDO_APROVACAO, parada.mensagem
    assert [c["papel"] for c in bancada.chamadas()] == ["planejador", "aceite", "aceite"]
    with pytest.raises(PedidoRecusado):
        orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "x", "david", alvo="C9"))


def test_refazer_que_mexe_no_teste_de_outro_criterio_nao_vale_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o autor que, refazendo C1, mexe em soma.py, ou devolve outro critério, volta com o problema."""
    roteiro = roteiro_completo()
    invasor = autor_de_aceite()
    invasor["arquivos"] = {**invasor["arquivos"], "soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}
    roteiro["aceite"] += [invasor, copy.deepcopy(invasor)]
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco())
    orquestrador.pedir("goal-soma", NovoPedido(PEDIDO_REFAZER_ACEITE, "o teste nao cobre negativos", "david", alvo="C1"))

    parada = orquestrador.rodar("goal-soma", OpcoesDoLaco())

    assert parada.motivo == MotivoDaParada.FALHA and "Os testes refeitos de C1 nao conferiram" in parada.mensagem
    assert "devolva so o criterio C1" in parada.mensagem
