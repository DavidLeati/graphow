"""A regra da conferência num ponto só: os furos que a revisão da T2f+T2h+T2j achou, e o desacordo da T2i (T2k).

Na revisão, o Goal fechava com defeito real: a regressão num critério que
estava `parcial` não se confirmava (S-A), o excedente do teto não segurava o
critério que os conferidos corrigidos davam por `atende` (S-B), e a correção
que quebrava um módulo que nenhuma fatia tocou não confirmava a regressão
(S-C). Os arquivos do critério cresciam com cada correção, e uma borda antiga
virava regressão de um diff que não a tocou (S-D). Na revisão da T2i, a
conferência julgava o critério em desacordo e o reprovava, e o parecer
anterior o voltava a `atende` (T2k.5).
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.regra_da_conferencia import RegraDaConferencia
from graphow.orquestrador.saida_do_verificador import MARCA_DA_REGRESSAO, MARCA_DO_TETO, Parecer, Verificacao

from tests.orquestrador import apoio_laco
from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    SOMA_COM_DOCSTRING,
    VERIFICAR,
    Bancada,
    autor_de_aceite,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
V1_1: str = "achado-goal-soma-v1-1"
EXEMPLO_ERRADO: dict[str, Any] = {
    "titulo": "o exemplo novo do README esta errado", "descricao": "README diz somar(2, 3) == 6",
    "prova": "README.md:2 lido: somar(2, 3) == 6", "local": "README.md:2", "criterios": ["C2"], "decisoes": [],
    "severidade": "alta", "alcance": "uso_previsto", "regressao": True,
}
UTIL_CERTO: str = "def _soma(a, b):\n    return a + b\n"
UTIL_QUEBRADO: str = "def _soma(a, b):\n    return abs(a) + abs(b)\n"
SOMA_COM_UTIL: str = "from util import _soma\n\n\ndef somar(a, b):\n    return _soma(a, b)\n"
NEGATIVOS_QUEBRADOS: dict[str, Any] = {
    "titulo": "somar com negativos quebrou", "descricao": "somar(-2, -3) devolve 5 depois da correcao",
    "prova": "python -c 'from soma import somar; print(somar(-2, -3))' imprimiu 5", "local": "util.py:2",
    "criterios": ["C1"], "decisoes": [], "severidade": "alta", "alcance": "uso_previsto", "regressao": True,
}


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def _pareceres(estado: EstadoDoGoal, indice: int) -> dict[str, str]:
    """O veredito gravado de cada critério e decisão da verificação dada."""
    return {str(p["id"]): str(p["veredito"]) for p in estado.verificacoes[indice].propriedades["pareceres"]}


def _rodar(tmp_path: Path, roteiro: dict[str, list[dict[str, Any]]]) -> tuple[bool, EstadoDoGoal]:
    """O laço autônomo da spec com o roteiro dado: se fechou, e o estado do Goal."""
    bancada = montar_bancada(tmp_path, roteiro)
    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)
    return parada.fechou, _estado(bancada)


def test_regressao_no_criterio_parcial_cujo_bloqueante_foi_corrigido_bloqueia_nominal(tmp_path: Path) -> None:
    """T2k.1 (S-A): C2 parcial; a correção põe no README um exemplo errado; C2 viraria `atende`, e a regressão bloqueia."""
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto({"README.md": "# brinquedo\nUse somar(a, b): somar(2, 3) == 6.\n"})
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("nao_atende", [EXEMPLO_ERRADO])]

    fechou, estado = _rodar(tmp_path, roteiro)

    assert not fechou
    assert _pareceres(estado, 1)["C2"] == "nao_atende"
    assert [(x.texto("titulo"), x.texto("marca")) for x in estado.verificacoes[1].bloqueantes()] == [
        ("o exemplo novo do README esta errado", "")]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]


def test_excedente_do_teto_pendente_segura_o_criterio_nominal(tmp_path: Path) -> None:
    """T2k.1 (S-B): o 6º bloqueante de C2 passa do teto; os 5 conferidos corrigidos não dão C2 `atende` com ele pendente."""
    roteiro = roteiro_completo()
    seis = [{**BLOQUEANTE_DO_README, "titulo": f"README defeito {i}", "local": f"README.md:{i}"} for i in range(1, 7)]
    c2_parcial = verificacao("parcial")
    c2_parcial["saida"]["criterios"][1]["prova"] = "README defeito 6 continua: README.md:6"
    roteiro["verificador"] = [verificacao("parcial", seis), c2_parcial]

    fechou, estado = _rodar(tmp_path, roteiro)

    assert not fechou
    sexto = estado.verificacoes[0].achados[5]
    assert (sexto.texto("marca"), sexto.estado) == (MARCA_DO_TETO, "pendente")
    assert _pareceres(estado, 1)["C2"] == "parcial"
    assert [x.texto("titulo") for x in estado.verificacoes[1].bloqueantes()] == ["C2 parcial"]


def test_regressao_em_modulo_que_nenhuma_fatia_tocou_bloqueia_nominal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T2k.1 (S-C): util.py já existia; a correção de C2 o quebra; o diff toca o local, sem critério, e a regressão de C1 bloqueia."""
    original = apoio_laco.criar_repositorio
    monkeypatch.setattr(apoio_laco, "criar_repositorio", lambda pasta, arquivos: original(pasta, {**arquivos, "util.py": UTIL_CERTO}))
    c1_quebrado = verificacao("atende", [NEGATIVOS_QUEBRADOS])
    c1_quebrado["saida"]["criterios"][0] = {"id": "C1", "veredito": "nao_atende", "prova": "somar(-2, -3) imprimiu 5"}
    roteiro = roteiro_completo()
    roteiro["executor"][0] = executor_pronto({"soma.py": SOMA_COM_UTIL, "verificar.py": VERIFICAR})
    roteiro["executor"][2] = executor_pronto({"README.md": README_COM_EXEMPLO, "util.py": UTIL_QUEBRADO})
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), c1_quebrado]

    fechou, estado = _rodar(tmp_path, roteiro)

    assert not fechou
    assert _pareceres(estado, 1)["C1"] == "nao_atende"
    assert [(x.texto("titulo"), x.texto("marca")) for x in estado.verificacoes[1].bloqueantes()] == [
        ("somar com negativos quebrou", "")]


def test_borda_antiga_fora_do_diff_nao_e_confirmada_pelo_arquivo_de_outra_correcao_nominal(tmp_path: Path) -> None:
    """T2k.2 (S-D): K1 (de C2) mexe no README e em soma.py; K2 só em soma.py; a borda antiga do README não é regressão de C2."""
    reg_c1 = {**NEGATIVOS_QUEBRADOS, "titulo": "somar(-2, -3) errado", "local": "soma.py:2"}
    reg_c2 = {**EXEMPLO_ERRADO, "titulo": "README sem exemplo com zero", "descricao": "borda antiga dita regressao"}
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto({"README.md": README_COM_EXEMPLO, "soma.py": SOMA_COM_DOCSTRING})
    roteiro["executor"].append(executor_pronto({"soma.py": "# so um comentario\n" + SOMA_COM_DOCSTRING}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [reg_c1]),
                              verificacao("atende", [reg_c2])]
    roteiro["revisor"] = [revisao() for _ in range(8)]

    fechou, estado = _rodar(tmp_path, roteiro)

    assert fechou
    assert [x.texto("titulo") for x in estado.verificacoes[1].bloqueantes()] == ["somar(-2, -3) errado"]
    terceira = estado.verificacoes[2]
    assert terceira.bloqueantes() == ()
    assert [(x.texto("titulo"), x.gravidade, x.texto("marca")) for x in terceira.achados] == [
        ("README sem exemplo com zero", "acompanhamento", MARCA_DA_REGRESSAO)]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]


def _teste_errado() -> dict[str, Any]:
    """O executor da correção que diz que o teste de aceite de C1 está errado."""
    saida = {"status": "teste_errado", "resumo": "parei no teste de C1", "arquivos": [], "testes": [],
             "duvida": "o teste de C1 importa soma de uma pasta que a correcao nao usa", "teste_errado": "C1"}
    return {"saida": saida, "custo": 0.1}


def _mantido() -> dict[str, Any]:
    """O autor de aceite que, refazendo C1, mantém o teste como estava."""
    resposta = autor_de_aceite()
    resposta["saida"]["criterios"] = resposta["saida"]["criterios"][:1]
    resposta["saida"]["resumo"] = "o teste esta certo: importa da raiz, como a suite"
    return resposta


@pytest.mark.parametrize("regressao", [False, True], ids=["achado-novo", "regressao"])
def test_criterio_em_desacordo_que_a_conferencia_reprova_fica_reprovado_nominal(tmp_path: Path, regressao: bool) -> None:
    """T2k.5: o autor mantém o teste que o executor disse errado; a conferência julga C1 `nao_atende`, e o parecer dela vale."""
    julgou = verificacao("atende", [{**NEGATIVOS_QUEBRADOS, "titulo": "C1 nao atendido (desacordo julgado)",
                                     "local": "soma.py:1", "regressao": regressao}])
    julgou["saida"]["criterios"][0] = {"id": "C1", "veredito": "nao_atende", "prova": "julguei o desacordo: o executor tem razao"}
    roteiro = roteiro_completo()
    roteiro["executor"].insert(2, _teste_errado())
    roteiro["aceite"].append(_mantido())
    roteiro["verificador"][1] = julgou

    fechou, estado = _rodar(tmp_path, roteiro)

    assert not fechou
    assert _pareceres(estado, 1)["C1"] == "nao_atende"
    assert [x.texto("titulo") for x in estado.verificacoes[1].bloqueantes()] == ["C1 nao_atende"]


def test_regra_que_confirma_a_regressao_pelo_local_pelo_plano_ou_sem_como_saber_edge_case() -> None:
    """Caso de borda: o diff confirma a regressão pelo local, pelos arquivos do plano do critério ou por arquivo sem critério."""
    antes = (Parecer("C1", "atende", "ok"), Parecer("C2", "atende", "ok"))
    arquivos = {"C1": frozenset({"soma.py"}), "C2": frozenset({"README.md"})}
    em_c1 = Verificacao.de_json(verificacao("atende", [NEGATIVOS_QUEBRADOS])["saida"]).achados[0]
    casos = [(frozenset({"README.md"}), ""), (frozenset({"README.md"}), "README.md:3"), (frozenset({"soma.py"}), ""),
             (frozenset({"util.py"}), ""), (None, "")]

    confirmadas = [RegraDaConferencia(anteriores=antes, diff=diff, arquivos=arquivos).confirmada(
        replace(em_c1, local=local), Verificacao("", ())) for diff, local in casos]

    assert confirmadas == [False, True, True, True, True]


def test_regressao_de_quem_nao_viraria_atende_nao_se_confirma_edge_case() -> None:
    """Caso de borda: C2 parcial antes, com o conferido que o citava sem `corrigido`, ou fora do teto, não confirma a regressão."""
    conferido = AchadoRegistrado(V1_1, "v1", "bloqueante", "corrigido", {"criterios": ["C2"]})
    excedente = AchadoRegistrado("achado-goal-soma-v1-6", "v1", "acompanhamento", "pendente", {"criterios": ["C2"]})
    saida = {**verificacao("atende", [EXEMPLO_ERRADO])["saida"], "conferidos": [{"achado": V1_1, "parecer": "corrigido", "prova": "ok"}]}
    lida = Verificacao.de_json(saida)
    antes = (Parecer("C2", "parcial", "README lido"),)

    corrigido = RegraDaConferencia(conferidos=(conferido,), anteriores=antes, diff=frozenset({"README.md"}))
    com_excedente = RegraDaConferencia(conferidos=(conferido,), excedentes=(excedente,), anteriores=antes,
                                       diff=frozenset({"README.md"}))

    assert corrigido.confirmada(lida.achados[0], lida)
    assert not com_excedente.confirmada(lida.achados[0], lida)
    assert not RegraDaConferencia(anteriores=antes, diff=frozenset({"README.md"})).confirmada(lida.achados[0], lida)
