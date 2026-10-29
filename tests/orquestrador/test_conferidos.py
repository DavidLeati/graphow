"""Os achados conferidos: um parecer por achado na conferência, e o defeito que persiste não some do ciclo."""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.esquemas import ESQUEMA_DA_CONFERENCIA
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.saida_do_verificador import Verificacao, conferir_verificacao
from graphow.orquestrador.validacao_json import validar_contra_esquema

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    Bancada,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
V1_1: str = "achado-goal-soma-v1-1"
V1_2: str = "achado-goal-soma-v1-2"
PROVA_QUE_PERSISTE: str = "grep -c somar README.md: 1, ainda sem exemplo com resultado"


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def _conferencia(pareceres: list[tuple[str, str]], achados: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A resposta da conferência com os pareceres dados, (id do achado, parecer), e os achados."""
    resposta = verificacao("atende", achados)
    resposta["saida"]["conferidos"] = [{"achado": id_a, "parecer": parecer, "prova": f"reproduzido de novo: {parecer}"}
                                       for id_a, parecer in pareceres]
    return resposta


def test_conferencia_que_omite_um_conferido_e_saida_invalida_edge_case() -> None:
    """T2f.2: a conferência que dá parecer a um dos dois conferidos não confere; o que falta volta à sessão."""
    saida = _conferencia([(V1_1, "corrigido")])["saida"]

    problemas = conferir_verificacao(Verificacao.de_json(saida), ("C1", "C2"), ("D1",), conferidos=(V1_1, V1_2))

    assert problemas == (f"falta o parecer do achado conferido {V1_2} (corrigido ou persiste)",)


@pytest.mark.parametrize(
    ("pareceres", "achados", "problema"),
    [
        ([(V1_1, "corrigido"), (V1_1, "corrigido")], [], f"parecer do achado conferido {V1_1} repetido"),
        ([(V1_1, "corrigido"), ("achado-inventado", "persiste")], [],
         "o parecer de achado-inventado nao corresponde a nenhum achado conferido"),
        ([(V1_1, "corrigido")], [{**BLOQUEANTE_DO_README, "persiste": V1_1}],
         f"o achado 'README sem exemplo' persiste {V1_1}, e o parecer dele diz corrigido"),
    ],
)
def test_parecer_do_conferido_repetido_inventado_ou_contraditorio_e_recusado_edge_case(
    pareceres: list[tuple[str, str]], achados: list[dict[str, Any]], problema: str
) -> None:
    """Caso de borda: um parecer por conferido, só de conferido, e o achado que persiste não tem o parecer `corrigido`."""
    saida = _conferencia(pareceres, achados)["saida"]

    assert conferir_verificacao(Verificacao.de_json(saida), ("C1", "C2"), ("D1",), conferidos=(V1_1,)) == (problema,)


def test_schema_da_conferencia_exige_os_pareceres_dos_conferidos_edge_case() -> None:
    """Caso de borda: sem `conferidos`, a saída da conferência não passa no schema, e o parecer é corrigido ou persiste."""
    sem = verificacao("atende")["saida"]
    com_outro = _conferencia([(V1_1, "talvez")])["saida"]

    assert any("conferidos" in problema for problema in validar_contra_esquema(sem, ESQUEMA_DA_CONFERENCIA))
    assert validar_contra_esquema(com_outro, ESQUEMA_DA_CONFERENCIA)
    assert validar_contra_esquema(_conferencia([(V1_1, "persiste")])["saida"], ESQUEMA_DA_CONFERENCIA) == ()


def test_conferencia_que_omite_o_conferido_volta_a_sessao_e_so_o_corrigido_resolve_nominal(tmp_path: Path) -> None:
    """T2f.2 no laço: a conferência sem parecer volta à mesma sessão; o parecer `corrigido` da retomada resolve o achado."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), _conferencia([]), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    conferencias = bancada.chamadas("conferencia")
    assert len(conferencias) == 2 and "--resume" in conferencias[1]["argv"]
    assert f"falta o parecer do achado conferido {V1_1}" in conferencias[1]["stdin"]
    estado = _estado(bancada)
    assert [p["parecer"] for p in estado.verificacoes[1].propriedades["conferidos"]] == ["corrigido"]
    original = estado.achado(V1_1)
    assert original is not None and original.estado == "resolvido"


def test_parecer_persiste_sem_achado_listado_vira_o_bloqueante_e_o_original_se_resolve_com_ele_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o `persiste` só no parecer repete o achado como bloqueante, e o original se resolve com a cópia."""
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto({"README.md": "# brinquedo\nUse somar(a, b) agora.\n"})
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO}))
    persiste = _conferencia([(V1_1, "persiste")])
    persiste["saida"]["conferidos"][0]["prova"] = PROVA_QUE_PERSISTE
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), persiste, verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    copia = estado.verificacoes[1].achados[0]
    assert (copia.gravidade, copia.texto("titulo"), copia.lista("criterios")) == ("bloqueante", "README sem exemplo", ("C2",))
    assert (copia.texto("persiste"), copia.texto("prova")) == (V1_1, PROVA_QUE_PERSISTE)
    assert [f.codigo for f in estado.fatias if copia.id in f.lista("achados")] == ["M1.K2.1"]
    assert [(a.id, a.estado) for v in estado.verificacoes for a in v.bloqueantes()] == [(V1_1, "resolvido"), (copia.id, "resolvido")]
