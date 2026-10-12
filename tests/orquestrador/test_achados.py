"""O achado da verificação vira nó Achado com a gravidade que o código decide: bloqueante vira correção, acompanhamento vira pendência, nunca Note."""

from pathlib import Path
from typing import Any

from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.saida_do_verificador import ORIGEM_DO_ORQUESTRADOR, Achado

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import ACOMPANHAMENTO, Bancada, executor_pronto, montar_bancada, roteiro_completo, verificacao

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
# O que a fase 1 chamaria de acompanhamento: o verificador o acha menor, mas ele toca o critério C2.
MENOR_QUE_TOCA_C2: dict[str, Any] = {
    "titulo": "README sem o resultado do exemplo", "descricao": "o exemplo nao diz o que somar devolve",
    "prova": "README.md lido: 'Use somar(a, b).' sem resultado", "local": "README.md:2", "criterios": ["C2"],
    "decisoes": [], "severidade": "baixa",
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
    assert "teste de regressao que reproduz este achado" in achado


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
