"""A revisão por fatia só na fatia de risco: o planejador a marca, ou ela já falhou; nas outras não há revisão."""

import copy
from pathlib import Path
from typing import Any

from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado

from tests.orquestrador.apoio_laco import (
    PLANO,
    SOMA_CERTA,
    VERIFICAR,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")


def _roteiro_com_f1_de_risco(revisoes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """F1 marcada como risco pelo planejador; F2 não; verificação limpa."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][0].update(risco=True, motivo_do_risco="regra de dominio da soma")
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"saida": plano, "custo": 0.4}]
    roteiro["executor"] = roteiro["executor"][:2]
    roteiro["verificador"] = [verificacao("atende")]
    roteiro["revisor"] = revisoes
    return roteiro


def test_so_a_fatia_de_risco_e_revisada_antes_do_commit_nominal(tmp_path: Path) -> None:
    """F2.5: o revisor roda depois do executor de F1, antes do commit dela; F2, sem risco, não tem revisão."""
    bancada = montar_bancada(tmp_path, _roteiro_com_f1_de_risco([revisao()]))

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    assert [c["papel"] for c in bancada.chamadas()] == ["planejador", "aceite", "executor", "revisor", "executor", "verificador"]
    revisor = bancada.chamadas("revisor")[0]
    assert "# Revisao da fatia de risco F1" in revisor["stdin"] and "regra de dominio da soma" in revisor["stdin"]
    assert "Edit" not in revisor["argv"][revisor["argv"].index("--tools") + 1]
    evidencia = bancada.kernel.obter_view().obter_no("rev-task-soma-f1-t1")
    assert evidencia is not None and evidencia.obter_propriedade("veredito") == "aprovado"
    assert bancada.kernel.obter_view().obter_no("rev-task-soma-f2-t1") is None


def test_revisao_que_rejeita_vira_falha_com_os_problemas_no_briefing_seguinte_nominal(tmp_path: Path) -> None:
    """A rejeição não commita: a tentativa falha, o executor seguinte lê os problemas, e a revisão dele aprova."""
    roteiro = _roteiro_com_f1_de_risco([revisao("rejeitado"), revisao()])
    roteiro["executor"].insert(0, executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}))
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    assert "a revisao da fatia de risco rejeitou a entrega" in bancada.chamadas("executor")[1]["stdin"]
    assert "somar nao trata negativos" in bancada.chamadas("executor")[1]["stdin"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and (estado.fatias[0].falhas, estado.fatias[0].tentativas) == (1, 2)
    view = bancada.kernel.obter_view()
    assert [view.obter_no(f"rev-task-soma-f1-t{n}").obter_propriedade("veredito") for n in (1, 2)] == ["rejeitado", "aprovado"]
    achado = view.obter_no("achado-rev-task-soma-f1-t1-1")
    assert achado is not None and achado.tipo == TipoNo.ACHADO, "a rejeicao vira Achado (acompanhamento 7)"
    assert (achado.obter_propriedade("gravidade"), achado.obter_propriedade("estado")) == ("bloqueante", "resolvido")
    assert [a.destino_id for a in view.obter_arestas_saida(achado.id, TipoAresta.FERE)] == ["crit-soma-c1"]
    assert view.obter_no("nota-task-soma-f1-t1") is None, "e nao uma Note"
    assert [a.id for a in estado.fatias[0].achados_de_revisao] == [achado.id]


def test_fatia_sem_risco_que_ja_falhou_passa_pela_revisao_na_nova_tentativa_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a fatia que já falhou uma vez é de risco na tentativa seguinte, mesmo sem a marca do planejador."""
    roteiro = roteiro_completo()
    roteiro["executor"] = [executor_pronto({"soma.py": "def somar(a, b):\n    return 1\n", "verificar.py": VERIFICAR}),
                           *roteiro["executor"][:2]]
    roteiro["verificador"] = [verificacao("atende")]
    roteiro["revisor"] = [revisao()]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    evidencia = bancada.kernel.obter_view().obter_no("rev-task-soma-f1-t2")
    assert evidencia is not None and evidencia.obter_propriedade("motivo") == "uma tentativa anterior dela falhou"
    assert len(bancada.chamadas("revisor")) == 1


def test_revisor_que_mexe_na_area_e_desfeito_e_o_commit_e_do_executor_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o que o revisor escreveu some; o commit da fatia leva só o que o executor deixou."""
    bancada = montar_bancada(tmp_path, _roteiro_com_f1_de_risco([revisao(arquivos={"soma.py": "def somar(a, b):\n    return 42\n",
                                                                                   "intruso.txt": "x"})]))

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    assert (bancada.repositorio / "soma.py").read_text(encoding="utf-8") == SOMA_CERTA
    assert not (bancada.repositorio / "intruso.txt").exists()
    evidencia = bancada.kernel.obter_view().obter_no("rev-task-soma-f1-t1")
    assert "o revisor mexeu na area" in evidencia.obter_propriedade("observacao")
