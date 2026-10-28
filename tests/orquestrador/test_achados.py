"""O achado da verificação vira nó Achado com a gravidade que o código decide: bloqueante vira correção, acompanhamento vira pendência, nunca Note."""

import copy
import os
from pathlib import Path
from typing import Any

import pytest

from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.correcoes import MAXIMO_POR_FATIA, agrupar_o_ciclo, area_do_achado, normalizar_caminho, propriedades_da_correcao
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.saida_do_verificador import ORIGEM_DO_ORQUESTRADOR, Achado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import (
    ACOMPANHAMENTO,
    BLOQUEANTE_DO_README,
    VERIFICAR,
    Bancada,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    segunda_opiniao,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
# O que a fase 1 chamaria de acompanhamento: o verificador o acha menor, mas ele toca o critério C2.
MENOR_QUE_TOCA_C2: dict[str, Any] = {
    "titulo": "README sem o resultado do exemplo", "descricao": "o exemplo nao diz o que somar devolve",
    "prova": "README.md lido: 'Use somar(a, b).' sem resultado", "local": "README.md:2", "criterios": ["C2"],
    "decisoes": [], "severidade": "baixa", "alcance": "uso_previsto",
}


def _nos(bancada: Bancada, tipo: TipoNo) -> list[Any]:
    """Os nós do tipo dado no livro-razão."""
    return [no for no in bancada.kernel.obter_view().listar_todos_os_nos() if no.tipo == tipo]


def test_achado_de_baixa_severidade_que_toca_criterio_vira_correcao_nominal(tmp_path: Path) -> None:
    """F2.5b: o verificador diz C2 atende e acha o problema menor; o código o faz bloqueante, e ele vira correção."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [MENOR_QUE_TOCA_C2]), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    view = bancada.kernel.obter_view()
    achado = view.obter_no("achado-goal-soma-v1-1")
    assert achado is not None and achado.tipo == TipoNo.ACHADO
    assert (achado.obter_propriedade("gravidade"), achado.obter_propriedade("severidade")) == ("bloqueante", "baixa")
    assert [a.destino_id for a in view.obter_arestas_saida(achado.id, TipoAresta.FERE)] == ["crit-soma-c2"]
    assert [a.destino_id for a in view.obter_arestas_saida("achado-goal-soma-v1-1", TipoAresta.DERIVA_DE)] == ["ver-goal-soma-1"]
    assert [a.origem_id for a in view.obter_arestas_entrada(achado.id, TipoAresta.DERIVA_DE)] == ["task-soma-m1-k1-1"]
    assert achado.obter_propriedade("estado") == "resolvido"
    assert "Fatia M1.K1.1: README sem o resultado do exemplo (C2)" in git(bancada.repositorio, "log", "--format=%s")


def test_briefing_da_correcao_traz_o_achado_inteiro_e_pede_a_regressao_antes_nominal(tmp_path: Path) -> None:
    """A fatia de correção leva o achado com a prova e o critério que ele fere, e pede o teste de regressão primeiro."""
    bancada = montar_bancada(tmp_path, roteiro_completo())

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    correcao = bancada.chamadas("executor")[2]["stdin"]
    achado = correcao.split("## Achado que esta fatia corrige")[1]
    assert "achado-goal-soma-v1-1: README sem exemplo" in achado
    assert "Prova (como reproduzir): README.md lido: nenhum exemplo" in achado
    assert "Fere C2: o README explica como usar somar" in achado
    assert "escreva primeiro o teste de regressao que o reproduz" in achado


# Três bloqueantes em arquivos diferentes, cada um com a prova que cita o comando que o reproduz.
EM_TRES_ARQUIVOS: list[dict[str, Any]] = [
    {**BLOQUEANTE_DO_README, "titulo": "soma com negativos", "local": "soma.py:2", "criterios": ["C1"],
     "prova": "rodei `python -c 'print(somar(-2, -3))'` e saiu 5"},
    {**BLOQUEANTE_DO_README, "prova": "rodei `python ler_readme.py` e nao achei exemplo"},
    {**BLOQUEANTE_DO_README, "titulo": "verificar sem negativos", "local": "verificar.py:2", "criterios": ["C1"],
     "prova": "rodei `python verificar.py --negativos` e nada testou negativos"},
]
CHAMADAS_DOS_TRES: list[dict[str, Any]] = [
    {"comando": "python -c 'print(somar(-2, -3))'", "codigo": 0, "saida": "5"},
    {"comando": "python ler_readme.py", "codigo": 1, "saida": "sem exemplo"},
    {"comando": "python verificar.py --negativos", "codigo": 0, "saida": "ok, nada de negativos"},
]


def test_tres_bloqueantes_em_arquivos_diferentes_viram_uma_fatia_de_correcao_so_nominal(tmp_path: Path) -> None:
    """T2e.1: três bloqueantes em soma.py, README.md e verificar.py viram uma fatia só, com os três achados no briefing."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [{**verificacao("parcial", EM_TRES_ARQUIVOS), "bash": CHAMADAS_DOS_TRES}, verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    correcoes = [f for f in estado.fatias if f.texto("corrige_verificacao")]
    assert [(f.codigo, len(f.lista("achados"))) for f in correcoes] == [("M1.K1.1", 3)]
    assert correcoes[0].titulo == "Corrige: soma com negativos (e mais 2)"
    assert correcoes[0].lista("arquivos_alvo") == ("soma.py", "README.md", "verificar.py")
    assert [a.estado for a in estado.verificacoes[0].achados if a.bloqueante] == ["resolvido"] * 3
    assert len(bancada.chamadas("executor")) == 3, "duas fatias do plano e uma correcao so"
    briefing = bancada.chamadas("executor")[2]["stdin"]
    for achado, chamada in zip(EM_TRES_ARQUIVOS, CHAMADAS_DOS_TRES, strict=True):
        assert f"Prova (como reproduzir): {achado['prova']}" in briefing
        assert f"`{chamada['comando']}` saiu com {chamada['codigo']}: {chamada['saida']}" in briefing


def test_ciclo_acima_do_maximo_se_divide_em_pedacos_na_ordem_edge_case() -> None:
    """Caso de borda: a final que cobra os outros marcos passa do teto; o ciclo vira pedaços de 5, na ordem, sem repetir."""
    achados = [AchadoRegistrado(f"a{n}", "v", "bloqueante", "aberto", {"local": f"f{n}.py:1", "titulo": f"t{n}"}) for n in range(7)]

    grupos = agrupar_o_ciclo([*achados, achados[0]])

    assert [[a.id for a in grupo] for grupo in grupos] == [[f"a{n}" for n in range(MAXIMO_POR_FATIA)], ["a5", "a6"]]


def test_acompanhamento_vira_pendencia_e_nenhum_achado_vira_note_nominal(tmp_path: Path) -> None:
    """O achado que não toca nada fica pendente no Goal, no documento e no status; nenhuma Note de achado nasce."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [ACOMPANHAMENTO])]
    roteiro["executor"] = roteiro["executor"][:2]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    (achado,) = _nos(bancada, TipoNo.ACHADO)
    assert (achado.obter_propriedade("gravidade"), achado.obter_propriedade("estado")) == ("acompanhamento", "pendente")
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [(p["titulo"], p["achado"]) for p in estado.pendencias] == [("nome do modulo", achado.id)]
    assert f"Achado {achado.id}" in git(bancada.repositorio, "show", "main:docs/goals/soma.md").split("Pendencias")[-1]
    assert _nos(bancada, TipoNo.NOTE) == []


def test_o_mesmo_acompanhamento_em_duas_verificacoes_e_uma_pendencia_so_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a segunda verificação acha de novo o acompanhamento da primeira; a pendência não se repete."""
    roteiro = roteiro_completo()
    roteiro["verificador"][1] = verificacao("atende", [ACOMPANHAMENTO])
    roteiro["verificador"][0]["saida"]["achados"].append(ACOMPANHAMENTO)
    roteiro["executor"][2] = executor_pronto({"README.md": "# brinquedo\nUse somar(a, b): somar(2, 3) == 5.\n"})
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None and [p["titulo"] for p in estado.pendencias] == ["nome do modulo"]
    assert len([no for no in _nos(bancada, TipoNo.ACHADO) if no.obter_propriedade("gravidade") == "acompanhamento"]) == 2


def test_gravidade_vem_do_que_o_achado_toca_e_nao_da_severidade_edge_case() -> None:
    """Caso de borda: tocar uma decisão basta; a severidade alta sem tocar nada é acompanhamento; o do orquestrador é bloqueante."""
    base = {"titulo": "t", "descricao": "d", "prova": "comando e saida", "local": "", "criterios": [], "decisoes": []}

    assert Achado.de_json({**base, "decisoes": ["D1"], "severidade": "baixa"}).gravidade == "bloqueante"
    assert Achado.de_json({**base, "severidade": "alta"}).gravidade == "acompanhamento"
    assert Achado("suite", "vermelha", origem=ORIGEM_DO_ORQUESTRADOR).gravidade == "bloqueante"


def test_segunda_opiniao_que_cita_o_criterio_torna_o_achado_bloqueante_nominal(tmp_path: Path) -> None:
    """Acompanhamento 4: o achado sem citação vai a uma sessão curta; ela diz que fere C2, e ele vira bloqueante e correção."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [ACOMPANHAMENTO]), verificacao("atende")]
    roteiro["segunda_opiniao"] = [segunda_opiniao("C2")]
    roteiro["executor"].append(executor_pronto({"soma.py": "def somar(a, b):\n    return a + b  # calc\n"}))
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    achado = estado.verificacoes[0].achados[0]
    assert achado.bloqueante and achado.lista("criterios") == ("C2",) and achado.texto("segunda_opiniao") == "fere C2"
    pedido = bancada.chamadas("segunda_opiniao")[0]["stdin"]
    assert "- C2: o README explica como usar somar" in pedido and "soma.py poderia ser calc.py" in pedido
    assert [r.papel for r in bancada.telemetria.listar("goal-soma")].count("segunda_opiniao") == 1


def test_segunda_opiniao_que_nao_responde_nao_rebaixa_o_achado_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem a segunda opinião, os dois não concordaram, e o achado sem citação fica bloqueante."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [ACOMPANHAMENTO]), verificacao("atende")]
    roteiro["segunda_opiniao"] = [{"texto": "nao sei", "erro": True}]
    roteiro["executor"].append(executor_pronto({"soma.py": "def somar(a, b):\n    return a + b  # calc\n"}))
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    achado = estado.verificacoes[0].achados[0]
    assert achado.bloqueante and "sem acordo" in achado.texto("segunda_opiniao")


@pytest.mark.parametrize(
    ("locais", "juntos"),
    [(("./soma.py:3", "soma.py:1"), True), (("src\\soma.py:3", "src/soma.py:1"), True), (("soma.py:1", "README.md:1"), False)],
)
def test_area_do_achado_compara_o_caminho_normalizado_edge_case(locais: tuple[str, str], juntos: bool) -> None:
    """Caso de borda (ajuste 7): `./x.py` é `x.py`, a barra invertida é barra; arquivos diferentes são áreas diferentes."""
    achados = [AchadoRegistrado(f"a{n}", "v", "bloqueante", "aberto", {"local": local, "titulo": f"t{n}"}) for n, local in enumerate(locais)]

    assert (len({area_do_achado(achado) for achado in achados}) == 1) is juntos


def test_caixa_do_caminho_nao_separa_no_windows_edge_case() -> None:
    """Caso de borda: no Windows, `Soma.py` e `soma.py` são o mesmo arquivo para a área do achado."""
    assert normalizar_caminho("./Soma.py") == ("soma.py" if os.name == "nt" else "Soma.py")


def test_correcao_lista_todos_os_arquivos_que_o_local_cita_edge_case() -> None:
    """Caso de borda (fumaça da rodada 3): o local que cita dois arquivos põe os dois na fatia, não só o primeiro."""
    locais = ("cli.py:28-32 (so except ValueError); estatistica.py:32", ".\\src\\soma.py:3, com 1.5 e 1e308")
    grupo = [AchadoRegistrado(f"a{n}", "v", "bloqueante", "aberto", {"local": local, "titulo": f"t{n}"}) for n, local in enumerate(locais)]

    assert propriedades_da_correcao(grupo)["arquivos_alvo"] == ["cli.py", "estatistica.py", "src/soma.py"]


def test_correcao_agrupada_que_falha_duas_vezes_se_divide_em_uma_por_achado_nominal(tmp_path: Path) -> None:
    """T2e.2: a fatia com os três achados de arquivos diferentes falha duas vezes; ela se divide em três, que fecham o Goal."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", EM_TRES_ARQUIVOS), verificacao("atende")]
    falha = {"saida": {"status": "falhou", "resumo": "nao deu", "arquivos": [], "testes": [], "duvida": ""}, "custo": 0.1}
    roteiro["executor"] = [*roteiro["executor"][:2], falha, falha, executor_pronto({"soma.py": "def somar(a, b):\n    return b + a\n"}),
                           roteiro["executor"][2], executor_pronto({"verificar.py": VERIFICAR + "assert somar(-2, -3) == -5\n"})]
    roteiro["revisor"] = [revisao() for _ in range(6)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    divididas = [f for f in estado.fatias if f.texto("corrige_verificacao")]
    assert [(f.codigo, f.lista("achados"), f.lista("arquivos_alvo")) for f in divididas] == [
        ("M1.K1.1.1", ("achado-goal-soma-v1-1",), ("soma.py",)), ("M1.K1.1.2", ("achado-goal-soma-v1-2",), ("README.md",)),
        ("M1.K1.1.3", ("achado-goal-soma-v1-3",), ("verificar.py",))]
    agrupada = bancada.kernel.obter_view().obter_no("task-soma-m1-k1-1")
    assert agrupada is not None and agrupada.obter_propriedade("substituida_por") == "divisao-task-soma-m1-k1-1"
    assert len(agrupada.obter_propriedade("achados")) == 3


def test_segunda_opiniao_fora_do_formato_ganha_uma_retomada_edge_case(tmp_path: Path) -> None:
    """Caso de borda (ajuste 7): a segunda opinião que cita código que não é do Goal volta a ela uma vez, e a resposta certa vale."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README, ACOMPANHAMENTO]), verificacao("atende")]
    roteiro["segunda_opiniao"] = [segunda_opiniao("C9"), segunda_opiniao()]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    chamadas = bancada.chamadas("segunda_opiniao")
    assert len(chamadas) == 2 and "--resume" in chamadas[1]["argv"] and "codigos que nao sao do Goal: C9" in chamadas[1]["stdin"]
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    assert [(a.texto("titulo"), a.gravidade) for a in estado.verificacoes[0].achados] == [
        ("README sem exemplo", "bloqueante"), ("nome do modulo", "acompanhamento")]


# A sonda negativa que sai com erro de propósito: o verificador a rodou, mas ela não reproduz o achado.
SONDA_NEGATIVA: dict[str, Any] = {"comando": "python cli.py media", "codigo": 2, "saida": "lista vazia"}


def test_correcao_leva_o_comando_que_falhou_roda_em_opus_e_ve_a_tentativa_anterior_nominal(tmp_path: Path) -> None:
    """G: a correção recebe a chamada que a prova cita e roda em Opus; a do ciclo seguinte vê o diff da anterior."""
    em_soma = {**BLOQUEANTE_DO_README, "titulo": "somar com negativos", "local": "soma.py:2", "criterios": ["C1"],
               "prova": "rodei `python -c 'print(somar(-2, -3))'` e o assert viu -5 no lugar de -6"}
    reprovou = {**verificacao("atende", [em_soma]), "bash": [{"comando": "python -c 'print(somar(-2, -3))'", "codigo": 1,
                                                            "saida": "AssertionError: -5"}, SONDA_NEGATIVA]}
    roteiro = roteiro_completo()
    persiste = copy.deepcopy(reprovou)
    persiste["saida"]["achados"][0]["persiste"] = "achado-goal-soma-v1-1"
    roteiro["verificador"] = [reprovou, persiste, verificacao("atende")]
    roteiro["executor"] = [*roteiro["executor"][:2], executor_pronto({"soma.py": "def somar(a, b):\n    return a + b  # 1\n"}),
                           executor_pronto({"soma.py": "def somar(a, b):\n    return a + b  # 2\n"})]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador(modelos={"executor": "sonnet"}).iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    primeira, segunda = bancada.chamadas("executor")[2:4]
    assert "python -c 'print(somar(-2, -3))'` saiu com 1: AssertionError: -5" in primeira["stdin"]
    assert "python cli.py media" not in primeira["stdin"], "a sonda negativa esperada nao e reproducao"
    assert primeira["argv"][primeira["argv"].index("--model") + 1] == "opus"
    assert bancada.chamadas("executor")[0]["argv"][bancada.chamadas("executor")[0]["argv"].index("--model") + 1] == "sonnet"
    assert "A correcao M1.K1.1" in segunda["stdin"] and "+    return a + b  # 1" in segunda["stdin"]
    assert "A verificacao ver-goal-soma-2, depois dela, disse" in segunda["stdin"]


def test_correcao_recebe_so_as_chamadas_marcadas_como_reproducao_edge_case(tmp_path: Path) -> None:
    """Caso de borda (rodada 4, item 6): sem citação na prova, vale o que o verificador marcou em `reproducao`, ache-o o stream ou não."""
    em_soma = {**BLOQUEANTE_DO_README, "titulo": "somar com negativos", "local": "soma.py:2", "criterios": ["C1"],
               "reproducao": ["python verificar.py --negativos", "python -m pytest -q tests -k negativo"]}
    reprovou = {**verificacao("atende", [em_soma]), "bash": [{"comando": "python verificar.py  --negativos", "codigo": 1,
                                                            "saida": "esperava -6"}, SONDA_NEGATIVA]}
    roteiro = roteiro_completo()
    roteiro["verificador"] = [reprovou, verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    correcao = bancada.chamadas("executor")[2]["stdin"]
    assert "`python verificar.py  --negativos` saiu com 1: esperava -6" in correcao
    assert "`python -m pytest -q tests -k negativo` (o verificador o marcou como reproducao)" in correcao
    assert "lista vazia" not in correcao and "python cli.py media" not in correcao
    achado = ler_estado(bancada.kernel.obter_view(), "goal-soma").verificacoes[0].achados[0]
    assert achado.lista("reproducao") == ("python verificar.py --negativos", "python -m pytest -q tests -k negativo")
