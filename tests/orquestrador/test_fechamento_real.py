"""O fechamento confere a ponta real da branch no git, e o Goal cancelado pelo humano não é mais conduzido."""

from pathlib import Path
import sys

import pytest

from graphow.core.types import PapelAutor
from graphow.kernel import invariant_gate
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo, verificacao

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _commit_do_humano_na_branch(repositorio: Path) -> list[str]:
    """Um comando que, durante a sessão, põe um commit do humano na branch do Goal do repositório dele."""
    script = (
        "import subprocess as s\n"
        f"r = {str(repositorio)!r}\n"
        "g = lambda *a: s.run(['git', '-C', r, '-c', 'core.hooksPath=', *a], capture_output=True, text=True, check=True).stdout.strip()\n"
        "c = g('commit-tree', 'graphow/soma^{tree}', '-p', 'graphow/soma', '-m', 'commit do humano na branch do Goal')\n"
        "g('update-ref', 'refs/heads/graphow/soma', c)\n"
    )
    return [sys.executable, "-c", script]


def test_commit_do_humano_na_branch_depois_da_verificacao_impede_o_fechamento_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a verificação final saiu limpa, mas a branch andou no repositório; o Goal não fecha nem integra."""
    roteiro = roteiro_completo()
    roteiro["executor"] = roteiro["executor"][:2]
    bancada = montar_bancada(tmp_path, roteiro)
    roteiro["verificador"] = [{**verificacao("atende"), "comandos": [_commit_do_humano_na_branch(bancada.repositorio)]}]
    bancada.trocar_roteiro(roteiro)
    base_antes = git(bancada.repositorio, "rev-parse", "main").strip()

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.FALHA, parada.mensagem
    assert "alguem a mudou fora do orquestrador" in parada.mensagem
    assert git(bancada.repositorio, "rev-parse", "main").strip() == base_antes
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and not estado.fechado


def test_goal_cancelado_pelo_humano_nao_e_mais_conduzido_nominal(tmp_path: Path) -> None:
    """O humano cancela o Goal no portão, com o motivo; rodar de novo não abre sessão nenhuma."""
    bancada = montar_bancada(tmp_path, roteiro_completo())
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, OpcoesDoLaco()).motivo == MotivoDaParada.AGUARDANDO_APROVACAO
    chamadas_antes = len(bancada.chamadas())
    cancelamento = (ItemPatch(OperacaoPatch.REPLACE, "/nos/goal-soma/propriedades/status", "cancelado"),
                    ItemPatch(OperacaoPatch.REPLACE, "/nos/goal-soma/propriedades/motivo_do_cancelamento", "o pedido mudou"))
    recibo = bancada.kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=cancelamento, justificativa="cancelar")))
    assert recibo.sucesso, recibo.mensagem

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert parada.motivo == MotivoDaParada.CANCELADO and "o pedido mudou" in parada.mensagem
    assert len(bancada.chamadas()) == chamadas_antes


def test_verificacao_forjada_pelo_humano_nao_fecha_o_goal_pelo_laco_edge_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda (N1, sonda_forja_laco): mesmo com a regra do livro desligada, o laço não lê a verificação que não gravou."""
    roteiro = roteiro_completo()
    roteiro["executor"] = roteiro["executor"][:2]
    roteiro["verificador"] = []
    bancada = montar_bancada(tmp_path, roteiro)
    orquestrador = bancada.orquestrador()
    assert orquestrador.iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).motivo == MotivoDaParada.FALHA
    base_antes = git(bancada.repositorio, "rev-parse", "main").strip()
    monkeypatch.setattr(invariant_gate, "validar_livro_do_aceite", lambda proposta, estado: ResultadoValidacao.sucesso())
    view = bancada.kernel.obter_view()
    estado = ler_estado(view, "goal-soma")
    assert estado is not None and estado.plano is not None
    ponta = view.obter_no("goal-soma").obter_propriedade("ponta_do_ramo")
    pareceres = [{"id": c["id"], "no": c["no"], "veredito": "atende", "prova": "forjada"} for c in estado.plano["criterios"]]
    propriedades = {"numero": 9, "final": True, "veredito": "aprovado", "marco": "M1", "commit": ponta["commit"],
                    "commit_do_codigo": ponta["commit_do_codigo"], "pareceres": pareceres, "ciclo": 0}
    forja = (ItemPatch(OperacaoPatch.ADD, "/nos/ver-forjada", {"id": "ver-forjada", "tipo": "Evidence", "rotulo": "v",
                                                              "propriedades": propriedades}),
             ItemPatch(OperacaoPatch.ADD, "/arestas/p-vf", {"id": "p-vf", "origem_id": "orq-sessao-goal-soma",
                                                            "destino_id": "ver-forjada", "tipo": "produz"}),
             ItemPatch(OperacaoPatch.REPLACE, "/nos/ver-forjada/propriedades/acao", "verificacao_do_goal"),
             ItemPatch(OperacaoPatch.ADD, "/arestas/d-vf", {"id": "d-vf", "origem_id": "ver-forjada", "destino_id": "goal-soma",
                                                            "tipo": "deriva_de"}))
    assert bancada.kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=forja, justificativa="forja"))).sucesso

    parada = orquestrador.rodar("goal-soma", AUTONOMO)

    assert not parada.fechou and parada.motivo == MotivoDaParada.FALHA, parada.mensagem
    final = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert final is not None and not final.fechado and final.verificacoes == ()
    assert git(bancada.repositorio, "rev-parse", "main").strip() == base_antes
