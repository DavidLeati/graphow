"""O alcance do achado e o teto de bloqueantes por verificação (T2c).

O achado de entrada extrema vira acompanhamento quando as duas opiniões
concordam, e uma verificação abre no máximo 5 bloqueantes.

Na bancada de 12/10 cada verificação caçava uma borda patológica nova (NUL,
surrogate, id de 4300 dígitos, a última semana de 9999), toda borda tocava
algum critério, e "toca critério = bloqueante" fez a esteira que não deixou
nenhum Goal fechar.
"""

from pathlib import Path
from typing import Any

from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.documento_do_goal import com_pendencias
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.saida_do_verificador import Achado, Parecer, Verificacao, conferir_verificacao
from graphow.orquestrador.tipo_da_verificacao import TIPO_CONFERENCIA, TipoDaVerificacao

from tests.orquestrador.apoio_git import git
from tests.orquestrador.apoio_laco import montar_bancada, roteiro_completo, segunda_opiniao, verificacao

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
# A borda que a fase 2 caçava: toca C2, mas nenhum usuário do README a produz.
EXTREMO_QUE_TOCA_C2: dict[str, Any] = {
    "titulo": "README com NUL no exemplo quebra o leitor", "descricao": "um NUL colado no exemplo trava a leitura do README",
    "prova": "printf 'somar\\0' >> README.md; python ler.py README.md saiu 1", "local": "README.md:2", "criterios": ["C2"],
    "decisoes": [], "severidade": "media", "alcance": "extremo",
}
# O ano 9999 diante de uma decisão que fala daquele limite (D3 "não ocupar a sala para sempre" na agenda).
SERIE_ATE_9999: dict[str, Any] = {
    **EXTREMO_QUE_TOCA_C2, "titulo": "serie ate 31/12/9999 aceita", "descricao": "a serie semanal ate 9999 ocupa a sala para sempre",
    "prova": "python -m agenda reservar --semanal-ate 31/12/9999 saiu 0", "criterios": [], "decisao_do_limite": "D1",
}
BASE: dict[str, Any] = {"titulo": "t", "descricao": "d", "prova": "comando e saida", "local": "", "criterios": ["C1"], "decisoes": []}


def test_achado_que_toca_criterio_com_alcance_extremo_vira_acompanhamento_nominal() -> None:
    """T2c.1: tocar C1 com entrada extrema é acompanhamento; com uso previsto, ou sem alcance dito, é bloqueante."""
    assert Achado.de_json({**BASE, "alcance": "extremo"}).gravidade == "acompanhamento"
    assert Achado.de_json({**BASE, "alcance": "uso_previsto"}).gravidade == "bloqueante"
    assert Achado.de_json(BASE).gravidade == "bloqueante"
    assert Achado.de_json({**BASE, "alcance": "talvez"}).alcance == "uso_previsto"


def test_criterio_reprovado_que_so_um_extremo_toca_ganha_bloqueante_sintetico_edge_case() -> None:
    """Caso de borda, na caçada: C2 parcial com só o achado extremo tocando-o; sem o sintético, nada a corrigir e nada fecha."""
    dados = {**verificacao("parcial")["saida"], "achados": [EXTREMO_QUE_TOCA_C2]}

    verificacao_lida = Verificacao.de_json(dados)

    assert [achado.titulo for achado in verificacao_lida.bloqueantes()] == ["C2 parcial"]
    assert [achado.titulo for achado in verificacao_lida.acompanhamentos()] == ["README com NUL no exemplo quebra o leitor"]


def test_na_conferencia_o_criterio_que_atendia_e_so_um_extremo_toca_fica_com_o_parecer_anterior_edge_case() -> None:
    """Caso de borda (T2h): a mesma saída numa conferência, com C2 `atende` antes, não ganha o sintético; o que não atendia, ganha."""
    dados = {**verificacao("parcial")["saida"], "achados": [EXTREMO_QUE_TOCA_C2]}
    antes = {c2: TipoDaVerificacao(TIPO_CONFERENCIA, anteriores=(Parecer("C2", c2, "README lido"),)) for c2 in ("atende", "parcial")}

    atendia, nao_atendia = (antes[c2].sustentar(Verificacao.de_json(dados)) for c2 in ("atende", "parcial"))

    assert atendia.bloqueantes() == () and [p.veredito for p in atendia.criterios] == ["atende", "atende"]
    assert [achado.titulo for achado in atendia.acompanhamentos()] == ["README com NUL no exemplo quebra o leitor",
                                                                      "C2 parcial na conferencia"]
    assert [achado.titulo for achado in nao_atendia.bloqueantes()] == ["C2 parcial"]


def test_decisao_que_fala_do_limite_faz_o_extremo_ser_uso_previsto_nominal() -> None:
    """T2c.2: o extremo cuja decisão fala do limite é de uso previsto, toca a decisão e é bloqueante."""
    achado = Achado.de_json(SERIE_ATE_9999)

    assert (achado.extremo, achado.toca, achado.gravidade) == (False, ("D1",), "bloqueante")
    assert achado.em_json()["decisao_do_limite"] == "D1"


def test_decisao_do_limite_que_nao_e_do_goal_nao_confere_edge_case() -> None:
    """Caso de borda: a decisão do limite tem de ser do Goal, como tudo o que o achado toca."""
    dados = {**verificacao()["saida"], "achados": [{**SERIE_ATE_9999, "decisao_do_limite": "D9"}]}

    problemas = conferir_verificacao(Verificacao.de_json(dados), ["C1", "C2"], ["D1"])

    assert problemas == ("o achado 'serie ate 31/12/9999 aceita' toca D9, que nao e criterio nem decisao desta verificacao",)


def test_extremo_que_a_segunda_opiniao_confirma_vira_pendencia_nominal(tmp_path: Path) -> None:
    """T2c.1 no laço: a segunda opinião, sem ver o alcance do verificador, também diz extremo; o achado fica pendência."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [EXTREMO_QUE_TOCA_C2])]
    roteiro["segunda_opiniao"] = [segunda_opiniao(alcance="extremo")]
    roteiro["executor"] = roteiro["executor"][:2]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    (achado,) = estado.verificacoes[0].achados
    assert (achado.gravidade, achado.lista("criterios"), achado.texto("alcance_da_segunda_opiniao")) == (
        "acompanhamento", ("C2",), "extremo")
    assert [p["titulo"] for p in estado.pendencias] == ["README com NUL no exemplo quebra o leitor"]
    pedido = bancada.chamadas("segunda_opiniao")[0]["stdin"]
    assert "O verificador diz que ele fere: C2" in pedido and "extremo" not in pedido.split("## O achado")[1]


def test_segunda_opiniao_que_discorda_do_alcance_mantem_o_bloqueante_nominal(tmp_path: Path) -> None:
    """T2c.4: o verificador diz extremo e a segunda opinião, uso previsto; sem acordo, o achado segue bloqueante e é corrigido."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [EXTREMO_QUE_TOCA_C2]), verificacao("atende")]
    roteiro["segunda_opiniao"] = [segunda_opiniao(alcance="uso_previsto")]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    achado = estado.verificacoes[0].achados[0]
    assert (achado.gravidade, achado.texto("alcance"), achado.texto("alcance_da_segunda_opiniao")) == (
        "bloqueante", "extremo", "uso_previsto")
    assert achado.lista("criterios") == ("C2",) and achado.estado == "resolvido"
    assert "Fatia M1.K1.1: README com NUL no exemplo quebra o leitor (C2)" in git(bancada.repositorio, "log", "--format=%s")


def test_decisao_do_limite_dispensa_a_segunda_opiniao_e_vira_correcao_edge_case(tmp_path: Path) -> None:
    """T2c.2 no laço: com a decisão que fala do limite, o extremo não é rebaixável, não vai à segunda opinião e vira correção."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("atende", [SERIE_ATE_9999]), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    achado = estado.verificacoes[0].achados[0]
    assert (achado.gravidade, achado.estado) == ("bloqueante", "resolvido")
    assert bancada.chamadas("segunda_opiniao") == []


def _oito_bloqueantes() -> list[dict[str, Any]]:
    """Oito achados de uso previsto que tocam C2, na ordem de prioridade do verificador."""
    return [{**EXTREMO_QUE_TOCA_C2, "titulo": f"README falha {n}", "alcance": "uso_previsto"} for n in range(1, 9)]


def test_de_oito_bloqueantes_cinco_seguem_e_tres_viram_acompanhamento_marcado_nominal() -> None:
    """T2c.3: os 5 primeiros pela ordem do verificador seguem bloqueantes; os outros 3 são acompanhamento com a marca."""
    lida = Verificacao.de_json({**verificacao("parcial")["saida"], "achados": _oito_bloqueantes()})

    assert [achado.titulo for achado in lida.bloqueantes()] == [f"README falha {n}" for n in range(1, 6)]
    excedentes = lida.acompanhamentos()
    assert [achado.titulo for achado in excedentes] == ["README falha 6", "README falha 7", "README falha 8"]
    assert {(achado.gravidade, achado.em_json()["marca"]) for achado in excedentes} == {("acompanhamento", "excedeu o teto do ciclo")}
    assert com_pendencias("# Goal\n", [excedentes[0].em_json()]).count("- [acompanhamento: excedeu o teto do ciclo] README falha 6") == 1


def test_o_que_o_orquestrador_viu_falhar_fica_dentro_do_teto_edge_case() -> None:
    """Caso de borda: a suíte vermelha, listada depois dos achados do verificador, fica; sai o quinto do verificador."""
    lida = Verificacao.de_json({**verificacao("parcial")["saida"], "achados": _oito_bloqueantes()})

    com_a_suite = lida.com_achado_do_orquestrador("A suite do plano falhou no commit verificado", "1 failed")

    assert [achado.titulo for achado in com_a_suite.bloqueantes()] == [
        *(f"README falha {n}" for n in range(1, 5)), "A suite do plano falhou no commit verificado"]
    assert len(com_a_suite.achados_finais()) == 9 and len(lida.achados_finais()) == 8


def test_excedentes_do_teto_ficam_visiveis_como_pendencia_no_laco_nominal(tmp_path: Path) -> None:
    """T2c.3 no laço: os 5 bloqueantes viram correção; os 3 do teto ficam nós Achado pendentes e pendências marcadas."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", _oito_bloqueantes()), verificacao("atende")]
    bancada = montar_bancada(tmp_path, roteiro)

    assert bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO).fechou

    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    primeira = estado.verificacoes[0]
    assert [a.texto("titulo") for a in primeira.bloqueantes()] == [f"README falha {n}" for n in range(1, 6)]
    assert [(p["titulo"], p["marca"]) for p in estado.pendencias] == [
        (f"README falha {n}", "excedeu o teto do ciclo") for n in (6, 7, 8)]
    assert {a.estado for a in primeira.achados if not a.bloqueante} == {"pendente"}
    documento = git(bancada.repositorio, "show", "main:docs/goals/soma.md")
    assert documento.count("[acompanhamento: excedeu o teto do ciclo]") == 3
