"""Os marcos do plano: as fatias rodam marco a marco, cada marco tem o verificador dele e o último é a verificação final."""

import copy
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import MotivoDaParada, OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, LoteRecusado
from graphow.orquestrador.saidas import IdsFixados, Plano, conferir_plano

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    PLANO,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
README_COM_EXEMPLO: str = "# brinquedo\nUse somar(a, b): somar(2, 3) == 5.\n"


def _plano_em_dois_marcos() -> dict[str, Any]:
    """F1 (C1) no marco M1 e F2 (C2) no M2, o final."""
    plano = copy.deepcopy(PLANO)
    plano["marcos"] = [{"id": "M1", "titulo": "Soma", "fatias": ["F1"]}, {"id": "M2", "titulo": "README", "fatias": ["F2"]}]
    return plano


def _roteiro_em_dois_marcos(verificacoes: list[dict[str, Any]], executores: int = 2) -> dict[str, list[dict[str, Any]]]:
    """O roteiro completo com o plano em dois marcos e as verificações dadas."""
    roteiro = roteiro_completo()
    roteiro["planejador"] = [{"saida": _plano_em_dois_marcos(), "custo": 0.4}]
    roteiro["executor"] = roteiro["executor"][:executores]
    roteiro["verificador"] = verificacoes
    return roteiro


def test_cada_marco_tem_o_verificador_dele_e_o_ultimo_e_o_final_nominal(tmp_path: Path) -> None:
    """F2.3: F1, a verificação de M1 (só C1), F2 e a verificação final sobre o Goal inteiro, nessa ordem."""
    bancada = montar_bancada(tmp_path, _roteiro_em_dois_marcos([verificacao("nao_atende"), verificacao("atende")]))

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    assert [c["papel"] for c in bancada.chamadas()] == ["planejador", "aceite", "executor", "verificador", "executor", "verificador"]
    do_marco, final = (chamada["stdin"] for chamada in bancada.chamadas("verificador"))
    assert "verificacao do marco M1 (Soma), fatias F1" in do_marco
    assert "- C1 (teste)" in do_marco and "- C2 (checagem)" not in do_marco
    assert "verificacao final (M2), sobre o Goal inteiro" in final and "- C2 (checagem)" in final
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    assert [(v.marco, v.propriedades["final"], v.limpa) for v in estado.verificacoes] == [("M1", False, True), ("M2", True, True)]
    assert [p["id"] for p in estado.verificacoes[0].propriedades["pareceres"]] == ["C1", "D1"], "o C2 de M2 nao conta em M1"


def test_bloqueante_do_marco_vira_correcao_antes_do_marco_seguinte_nominal(tmp_path: Path) -> None:
    """O bloqueante de M1 é corrigido e M1 verificado de novo antes de F2 rodar."""
    bloqueante_em_c1 = {**BLOQUEANTE_DO_README, "titulo": "somar sem docstring", "criterios": ["C1"]}
    roteiro = _roteiro_em_dois_marcos([verificacao("atende", [bloqueante_em_c1]), verificacao("atende"), verificacao("atende")])
    roteiro["executor"].insert(1, executor_pronto({"soma.py": "def somar(a, b):\n    \"\"\"Soma.\"\"\"\n    return a + b\n"}))
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    assert [(f.codigo, f.texto("marco")) for f in estado.fatias] == [("F1", "M1"), ("F2", "M2"), ("M1.K1.1", "M1")]
    assert [v.marco for v in estado.verificacoes] == ["M1", "M1", "M2"]
    executores = bancada.chamadas("executor")
    assert "# Fatia M1.K1.1" in executores[1]["stdin"] and "# Fatia F2" in executores[2]["stdin"]


def test_limite_de_dois_ciclos_por_marco_para_o_goal_com_os_bloqueantes_abertos_edge_case(tmp_path: Path) -> None:
    """Caso de borda: M1 segue com bloqueante depois de dois ciclos; o laço para, os Achados ficam abertos e o kernel não fecha."""
    bloqueante_em_c1 = {**BLOQUEANTE_DO_README, "titulo": "somar sem docstring", "criterios": ["C1"]}
    roteiro = _roteiro_em_dois_marcos([verificacao("atende", [bloqueante_em_c1]) for _ in range(3)], executores=1)
    roteiro["executor"] += [executor_pronto({"soma.py": f"def somar(a, b):\n    return a + b  # {n}\n"}) for n in (1, 2)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.motivo == MotivoDaParada.BLOQUEANTES_RESTANTES, parada.mensagem
    assert "2 ciclos de correcao no marco M1" in parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and not estado.fechado
    assert [f.codigo for f in estado.fatias if f.texto("marco") == "M1"] == ["F1", "M1.K1.1", "M1.K2.1"]
    assert [a.estado for a in estado.verificacoes[-1].achados] == ["aberto"]
    assert len(bancada.chamadas("executor")) == 3, "F2, do marco seguinte, nunca rodou"
    with pytest.raises(LoteRecusado) as recusa:
        LivroRazaoDoGoal(bancada.kernel, "goal-soma").fechar("qualquer")
    assert "nao e a final" in recusa.value.contexto["motivo"]


@pytest.mark.parametrize(
    ("marcos", "trecho"),
    [
        ([{"id": "M1", "titulo": "t", "fatias": ["F1"]}], "a fatia F2 nao esta em nenhum marco"),
        ([{"id": "M1", "titulo": "t", "fatias": ["F1", "F2"]}, {"id": "M2", "titulo": "t", "fatias": ["F2"]}],
         "a fatia F2 esta em mais de um marco"),
        ([{"id": "M1", "titulo": "t", "fatias": ["F2"]}, {"id": "M2", "titulo": "t", "fatias": ["F1"]}],
         "a fatia F2 depende de F1, que e de um marco seguinte"),
        ([{"id": "M1", "titulo": "t", "fatias": ["F1", "F2", "F9"]}], "o marco M1 cita F9, que nao e fatia do plano"),
    ],
)
def test_plano_com_marcos_que_nao_repartem_as_fatias_e_recusado_edge_case(marcos: list[dict[str, Any]], trecho: str) -> None:
    """Caso de borda: toda fatia num marco só, dependência só para trás e marco que cita só fatia do plano."""
    plano = {**copy.deepcopy(PLANO), "marcos": marcos}

    problemas = conferir_plano(Plano.de_json(plano), IdsFixados())

    assert trecho in problemas, problemas


def test_marco_intermediario_que_nao_completa_criterio_e_recusado_edge_case() -> None:
    """Caso de borda: um marco que não entrega critério nenhum não tem o que verificar."""
    plano = copy.deepcopy(PLANO)
    plano["fatias"][0]["criterios"] = ["C2"]
    plano["fatias"][1]["criterios"] = ["C1", "C2"]
    plano["marcos"] = [{"id": "M1", "titulo": "t", "fatias": ["F1"]}, {"id": "M2", "titulo": "t", "fatias": ["F2"]}]

    problemas = conferir_plano(Plano.de_json(plano), IdsFixados())
    so_c1 = Plano.de_json({**plano, "fatias": [{**plano["fatias"][0], "criterios": ["C1"]}, {**plano["fatias"][1], "criterios": ["C2"]}]})

    assert "o marco M1 nao completa nenhum criterio: junte-o ao seguinte" in problemas
    assert so_c1.criterios_do_marco("M1") == ("C1",) and so_c1.criterios_do_marco("M2") == ("C1", "C2")


def test_plano_de_antes_dos_marcos_e_um_marco_so_o_final_edge_case() -> None:
    """Caso de borda: o plano gravado sem marcos (fase 1) vale como um marco M1 com todas as fatias."""
    plano = {chave: valor for chave, valor in copy.deepcopy(PLANO).items() if chave != "marcos"}

    lido = Plano.de_json(plano)

    assert [(m.id, m.fatias) for m in lido.marcos] == [("M1", ("F1", "F2"))]
    assert lido.criterios_do_marco("M1") == ("C1", "C2")
