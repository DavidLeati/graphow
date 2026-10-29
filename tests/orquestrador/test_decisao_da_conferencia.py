"""A conferência só bloqueia o que o código confirma: a regressão e o critério que ela reprova (T2h, T2j, T2k).

Na revisão da T2c+T2d, a borda nova que a conferência chamava de regressão
num critério que já estava `parcial` virava bloqueante e correção, e o
critério que atendia e ela dava por `parcial` por uma borda nova ganhava o
bloqueante sintético: as duas saídas eram só a palavra dela. O critério que
já não atendia, com o bloqueante dele dado por `corrigido`, também (T2j).
"""

from pathlib import Path
from typing import Any

import pytest

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.saida_do_verificador import (
    MARCA_DA_CONFERENCIA,
    MARCA_DA_REGRESSAO,
    MARCA_DO_CORRIGIDO,
    MARCA_DO_PARECER,
    Parecer,
    Verificacao,
)
from graphow.orquestrador.regra_da_conferencia import RegraDaConferencia
from graphow.orquestrador.tipo_da_verificacao import na_conferencia

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    SEM_DOCSTRING,
    SOMA_CERTA,
    SOMA_COM_DOCSTRING,
    SOMA_ERRADA,
    VERIFICAR,
    Bancada,
    executor_pronto,
    montar_bancada,
    revisao,
    roteiro_completo,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
V1_1: str = "achado-goal-soma-v1-1"
NUL_COMO_REGRESSAO: dict[str, Any] = {
    "titulo": "README com NUL trava o leitor", "descricao": "NUL colado no exemplo", "prova": "printf '\\0' >> README.md",
    "local": "README.md:2", "criterios": ["C2"], "decisoes": [], "severidade": "media", "alcance": "uso_previsto",
    "regressao": True,
}
REGRESSAO_EM_C1: dict[str, Any] = {
    "titulo": "somar quebrou na correcao", "descricao": "somar(2, 3) devolve 6 depois da correcao",
    "prova": "python -c 'from soma import somar; print(somar(2, 3))' imprimiu 6", "local": "soma.py:2", "criterios": ["C1"],
    "decisoes": [], "severidade": "alta", "alcance": "uso_previsto", "regressao": True,
}
BORDA_NOVA_EM_C2: dict[str, Any] = {
    "titulo": "README sem exemplo com negativos", "descricao": "o README nao mostra somar(-2, -3)",
    "prova": "README.md lido: so o exemplo com positivos", "local": "README.md:2", "criterios": ["C2"], "decisoes": [],
    "severidade": "media", "alcance": "uso_previsto", "regressao": False,
}


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def _pareceres(estado: EstadoDoGoal, indice: int) -> dict[str, str]:
    """O veredito gravado de cada critério e decisão da verificação dada."""
    return {str(p["id"]): str(p["veredito"]) for p in estado.verificacoes[indice].propriedades["pareceres"]}


def test_regressao_num_criterio_que_segue_parcial_vira_acompanhamento_nominal(tmp_path: Path) -> None:
    """T2h.1 (S2), com a regra da T2k: C2 parcial e o bloqueante dele persiste; a borda nova dita regressão de C2 não bloqueia.

    Na T2h bastava C2 não atender antes. Na T2k, a regressão de quem não
    atendia se confirma quando o que o reprovava foi corrigido (o S-A); aqui o
    bloqueante persiste, C2 não viraria `atende`, e a borda fica acompanhamento.
    """
    roteiro = roteiro_completo()
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "somar(-2, -3) == -5.\n"}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]),
                              verificacao("parcial", [{**BLOQUEANTE_DO_README, "persiste": V1_1}, NUL_COMO_REGRESSAO]),
                              verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    nul = estado.verificacoes[1].achados[1]
    assert (nul.texto("titulo"), nul.gravidade, nul.texto("marca")) == ("README com NUL trava o leitor", "acompanhamento",
                                                                       MARCA_DA_REGRESSAO)
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]
    assert bancada.chamadas("segunda_opiniao") == [], "a regressao nao confirmada nao vai a segunda opiniao"


@pytest.mark.parametrize(
    ("correcao", "gravidade", "marca"),
    [
        ({"README.md": README_COM_EXEMPLO, "soma.py": SOMA_COM_DOCSTRING}, "bloqueante", ""),
        ({"README.md": README_COM_EXEMPLO}, "acompanhamento", MARCA_DA_REGRESSAO),
    ],
    ids=["diff-toca-soma", "diff-so-no-readme"],
)
def test_regressao_num_criterio_que_atendia_bloqueia_so_com_o_diff_no_arquivo_dele_nominal(
    tmp_path: Path, correcao: dict[str, str], gravidade: str, marca: str
) -> None:
    """T2h.1: C1 atendia; a regressão de C1 bloqueia quando a correção mexeu em soma.py (da fatia de C1), e não quando só no README."""
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto(correcao)
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_CERTA}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [REGRESSAO_EM_C1]),
                              verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    regressao = estado.verificacoes[1].achados[0]
    assert (regressao.gravidade, regressao.texto("marca")) == (gravidade, marca)
    corrigem = [f.codigo for f in estado.fatias if regressao.id in f.lista("achados")]
    assert corrigem == (["M1.K2.1"] if gravidade == "bloqueante" else [])


def test_sem_como_saber_vale_so_a_primeira_condicao_edge_case() -> None:
    """Caso de borda: sem o diff, ou com arquivo que não é de critério nenhum no diff, a regressão de quem atendia é confirmada."""
    antes = (Parecer("C1", "atende", "ok"), Parecer("C2", "atende", "ok"))
    arquivos = {"C1": frozenset({"soma.py"}), "C2": frozenset({"README.md"})}
    em_c1, em_c2 = Verificacao.de_json(verificacao("atende", [REGRESSAO_EM_C1, {**NUL_COMO_REGRESSAO, "local": ""}])["saida"]).achados
    casos = [(None, em_c1), (frozenset({"novo.py"}), em_c1), (frozenset({"README.md"}), em_c1), (frozenset({"README.md"}), em_c2)]

    confirmadas = [RegraDaConferencia(anteriores=antes, diff=diff, arquivos=arquivos).confirmada(achado, Verificacao("", ()))
                   for diff, achado in casos]

    assert confirmadas == [True, True, False, True]


def test_regressao_so_de_decisao_segue_a_mesma_regra_edge_case() -> None:
    """Caso de borda: a regressão que cita só uma decisão, sem arquivo de plano, só se confirma pelo local ou por arquivo sem critério.

    Na T2h ela nunca se confirmava; na T2k a regra vale para critério e decisão.
    """
    so_d1 = {**REGRESSAO_EM_C1, "titulo": "D1 quebrou", "criterios": [], "decisoes": ["D1"], "local": "README.md:2"}
    saida = verificacao("atende", [so_d1, REGRESSAO_EM_C1])["saida"]
    antes = (Parecer("C1", "atende", "ok"), Parecer("D1", "atende", "ok"))
    regra = RegraDaConferencia(anteriores=antes, diff=frozenset({"soma.py"}), arquivos={"C1": frozenset({"soma.py"}),
                                                                                    "C2": frozenset({"README.md"})})

    ajustada = na_conferencia(Verificacao.de_json(saida), regra)

    assert [(x.titulo, x.gravidade, x.marca) for x in ajustada.achados] == [
        ("D1 quebrou", "acompanhamento", MARCA_DA_REGRESSAO), ("somar quebrou na correcao", "bloqueante", "")]
    no_local = na_conferencia(Verificacao.de_json(verificacao("atende", [{**so_d1, "local": "soma.py:1"}])["saida"]), regra)
    assert [x.gravidade for x in no_local.achados] == ["bloqueante"]


def test_criterio_que_atendia_e_a_conferencia_reprova_por_borda_nova_nao_ganha_sintetico_nominal(tmp_path: Path) -> None:
    """T2h.2: C2 atendia; a conferência o dá por parcial só pela borda nova; vale o parecer anterior, e o Goal fecha."""
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto({"soma.py": SOMA_COM_DOCSTRING})
    roteiro["verificador"] = [verificacao("atende", [SEM_DOCSTRING]), verificacao("parcial", [BORDA_NOVA_EM_C2])]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    conferencia = estado.verificacoes[1]
    assert conferencia.bloqueantes() == () and conferencia.limpa
    assert _pareceres(estado, 1)["C2"] == "atende"
    marcas = [(x.texto("titulo"), x.gravidade, x.texto("marca")) for x in conferencia.achados]
    assert marcas == [("README sem exemplo com negativos", "acompanhamento", MARCA_DA_CONFERENCIA),
                      ("C2 parcial na conferencia", "acompanhamento", MARCA_DO_PARECER)]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1"]
    assert any(p.get("titulo") == "C2 parcial na conferencia" for p in estado.pendencias)


def test_criterio_com_teste_de_aceite_falhando_na_conferencia_ainda_bloqueia_nominal(tmp_path: Path) -> None:
    """T2h.3: a correção do README quebra somar; a conferência dá C1 parcial sem achado, e o teste de aceite vermelho o reprova."""
    c1_parcial = verificacao("atende")
    c1_parcial["saida"]["criterios"][0] = {"id": "C1", "veredito": "parcial", "prova": "somar(2, 3) imprimiu 0"}
    roteiro = roteiro_completo()
    roteiro["executor"][2] = executor_pronto({"README.md": README_COM_EXEMPLO, "soma.py": SOMA_ERRADA, "verificar.py": "print('ok')\n"})
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_CERTA, "verificar.py": VERIFICAR}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), c1_parcial, verificacao("atende")]
    roteiro["revisor"] = [revisao() for _ in range(6)]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    conferencia = estado.verificacoes[1]
    assert _pareceres(estado, 1)["C1"] == "nao_atende"
    assert [x.texto("titulo") for x in conferencia.bloqueantes()] == ["O teste de aceite test_c1_soma de C1 falhou"]
    assert all(x.texto("marca") != MARCA_DO_PARECER for x in conferencia.achados)
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]


def test_criterio_que_ja_estava_parcial_com_o_bloqueante_corrigido_fecha_pela_borda_nova_nominal(tmp_path: Path) -> None:
    """T2j.1 (S3): C2 parcial na caçada; a conferência dá o bloqueante por corrigido e C2 parcial pela borda nova; o Goal fecha."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("parcial", [BORDA_NOVA_EM_C2])]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    conferencia = estado.verificacoes[1]
    assert conferencia.bloqueantes() == () and conferencia.limpa
    assert _pareceres(estado, 1)["C2"] == "atende"
    assert f"{V1_1} conferido corrigido" in str(conferencia.propriedades["pareceres"])
    marcas = [(x.texto("titulo"), x.gravidade, x.texto("marca")) for x in conferencia.achados]
    assert marcas == [("README sem exemplo com negativos", "acompanhamento", MARCA_DA_CONFERENCIA),
                      ("C2 parcial na conferencia", "acompanhamento", MARCA_DO_CORRIGIDO)]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1"]
    assert any(p.get("titulo") == "README sem exemplo com negativos" for p in estado.pendencias)


def test_criterio_parcial_com_o_achado_que_persiste_continua_bloqueando_nominal(tmp_path: Path) -> None:
    """T2j.2: o mesmo S3, mas a conferência diz que o bloqueante de C2 persiste: C2 segue parcial e vai à correção."""
    roteiro = roteiro_completo()
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "somar(-2, -3) == -5.\n"}))
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]),
                              verificacao("parcial", [{**BLOQUEANTE_DO_README, "persiste": V1_1}, BORDA_NOVA_EM_C2]),
                              verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    conferencia = estado.verificacoes[1]
    assert _pareceres(estado, 1)["C2"] == "parcial"
    assert [(x.texto("titulo"), x.texto("persiste")) for x in conferencia.bloqueantes()] == [("README sem exemplo", V1_1)]
    assert all(x.texto("marca") not in (MARCA_DO_CORRIGIDO, MARCA_DO_PARECER) for x in conferencia.achados)
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M1.K2.1"]


def test_reprovado_sem_bloqueante_conferido_que_o_cite_segue_reprovado_edge_case() -> None:
    """Caso de borda: C2 parcial antes sem bloqueante conferido que o cite (só um acompanhamento) segue parcial, com o sintético."""
    saida = {**verificacao("parcial")["saida"], "conferidos": [{"achado": V1_1, "parecer": "corrigido", "prova": "ok"}]}
    acompanhamento = AchadoRegistrado(V1_1, "ver-goal-soma-1", "acompanhamento", "pendente", {"criterios": ["C2"]})
    regra = RegraDaConferencia(conferidos=(acompanhamento,), anteriores=(Parecer("C2", "parcial", "README lido"),))

    sustentada = regra.com_os_pareceres(Verificacao.de_json(saida))

    assert [p.veredito for p in sustentada.criterios] == ["atende", "parcial"] and sustentada.achados == ()
    assert [x.titulo for x in sustentada.bloqueantes()] == ["C2 parcial"]
