"""Os três tipos de verificação: a caçada uma vez, na primeira final; a do marco intermediário; a conferência depois de cada correção."""

from pathlib import Path
from typing import Any

from graphow.kernel.fechamento_do_goal import motivos_para_nao_fechar
from graphow.orquestrador.contexto_do_laco import OpcoesDoLaco
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado
from graphow.orquestrador.saida_do_verificador import MARCA_DA_CONFERENCIA, Verificacao, conferir_verificacao
from graphow.orquestrador.status import formatar_status

from tests.orquestrador.apoio_laco import (
    BLOQUEANTE_DO_README,
    README_COM_EXEMPLO,
    SOMA_COM_DOCSTRING,
    Bancada,
    executor_pronto,
    montar_bancada,
    roteiro_completo,
    roteiro_em_dois_marcos_com_um_ciclo_cada,
    verificacao,
)

AUTONOMO: OpcoesDoLaco = OpcoesDoLaco(modo="autonomo")
VERIFICACOES: tuple[str, ...] = ("verificador", "marco", "conferencia")
# A conferência acha uma borda nova em C2 (o README não fala de negativos) e uma regressão em C1.
BORDA_NOVA_EM_C2: dict[str, Any] = {
    "titulo": "README sem exemplo com negativos", "descricao": "o README nao mostra somar(-2, -3)",
    "prova": "README.md lido: so o exemplo com positivos", "local": "README.md:2", "criterios": ["C2"], "decisoes": [],
    "severidade": "media", "alcance": "uso_previsto", "regressao": False,
}
REGRESSAO_EM_C1: dict[str, Any] = {
    "titulo": "somar quebrou na correcao do README", "descricao": "somar(2, 3) devolve 6 depois da correcao",
    "prova": "python -c 'from soma import somar; print(somar(2, 3))' imprimiu 6", "local": "soma.py:2", "criterios": ["C1"],
    "decisoes": [], "severidade": "alta", "alcance": "uso_previsto", "regressao": True,
}


def _verificacoes(bancada: Bancada) -> list[dict[str, Any]]:
    """As chamadas das sessões de verificação, dos três tipos, na ordem."""
    return [chamada for chamada in bancada.chamadas() if chamada["papel"] in VERIFICACOES]


def _modelo(chamada: dict[str, Any]) -> str:
    """O `--model` do comando que o falso recebeu."""
    argv = chamada["argv"]
    return str(argv[argv.index("--model") + 1])


def _estado(bancada: Bancada) -> EstadoDoGoal:
    """O estado do Goal da bancada."""
    estado = ler_estado(bancada.kernel.obter_view(), "goal-soma")
    assert estado is not None
    return estado


def test_dois_marcos_com_um_ciclo_cada_rodam_marco_conferencia_cacada_conferencia_nominal(tmp_path: Path) -> None:
    """T2d.1: a ordem das sessões de verificação é marco, conferência, caçada, conferência, e o tipo vai na Evidence e no status."""
    bancada = montar_bancada(tmp_path, roteiro_em_dois_marcos_com_um_ciclo_cada())

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    sessoes = _verificacoes(bancada)
    assert [c["papel"] for c in sessoes] == ["marco", "conferencia", "verificador", "conferencia"]
    assert [_modelo(c) for c in sessoes] == ["sonnet", "sonnet", "opus", "sonnet"]
    estado = _estado(bancada)
    assert [(v.marco, v.tipo) for v in estado.verificacoes] == [("M1", "marco"), ("M1", "conferencia"), ("M2", "caca"),
                                                                 ("M2", "conferencia")]
    assert [f.codigo for f in estado.fatias] == ["F1", "F2", "M1.K1.1", "M2.K1.1"]
    conferencia = sessoes[1]["stdin"]
    assert "# Conferencia do Goal goal-soma" in conferencia and "achado-goal-soma-v1-1: somar sem docstring" in conferencia
    assert "## Diff das correcoes" in conferencia and '"""Soma."""' in conferencia
    assert "## Spec completa" not in conferencia, "o briefing da conferencia e curto"
    linhas = formatar_status(estado, bancada.telemetria.listar("goal-soma"))
    assert any("(M1, marco)" in linha for linha in linhas) and any("(M2, caca)" in linha for linha in linhas)
    assert any(linha.startswith("  conferencia: 2 invocacao(oes)") for linha in linhas)


def test_conferencia_rebaixa_o_achado_novo_e_bloqueia_a_regressao_nominal(tmp_path: Path) -> None:
    """T2d.2: na conferência, a borda nova em C2 vira acompanhamento marcado, e a regressão em C1 vira bloqueante e correção."""
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [BORDA_NOVA_EM_C2, REGRESSAO_EM_C1]),
                              verificacao("atende")]
    roteiro["executor"].append(executor_pronto({"soma.py": SOMA_COM_DOCSTRING}))
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    conferencia = estado.verificacoes[1]
    assert conferencia.tipo == "conferencia"
    destinos = {a.texto("titulo"): (a.gravidade, a.texto("marca")) for a in conferencia.achados}
    assert destinos["somar quebrou na correcao do README"][0] == "bloqueante"
    assert destinos["README sem exemplo com negativos"] == ("acompanhamento", MARCA_DA_CONFERENCIA)
    regressao = next(a for a in conferencia.achados if a.bloqueante)
    assert [f.codigo for f in estado.fatias if regressao.id in f.lista("achados")] == ["M1.K2.1"]
    assert any(p.get("titulo") == "README sem exemplo com negativos" for p in estado.pendencias)
    assert bancada.chamadas("segunda_opiniao") == [], "o destino do achado da conferencia nao depende da segunda opiniao"


def test_achado_conferido_que_persiste_segue_bloqueante_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a conferência reproduz o achado e diz que ele persiste; mesmo sem citar critério, ele é bloqueante de novo."""
    persiste = {**BLOQUEANTE_DO_README, "criterios": [], "persiste": "achado-goal-soma-v1-1"}
    roteiro = roteiro_completo()
    roteiro["verificador"] = [verificacao("parcial", [BLOQUEANTE_DO_README]), verificacao("atende", [persiste]), verificacao("atende")]
    roteiro["executor"].append(executor_pronto({"README.md": README_COM_EXEMPLO + "Exemplo: somar(1, 1) == 2.\n"}))
    bancada = montar_bancada(tmp_path, roteiro)

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    de_novo = estado.verificacoes[1].achados[0]
    assert (de_novo.gravidade, de_novo.lista("criterios"), de_novo.texto("persiste")) == ("bloqueante", ("C2",), "achado-goal-soma-v1-1")
    assert [v.tipo for v in estado.verificacoes] == ["caca", "conferencia", "conferencia"]


def test_conferencia_que_diz_persistir_achado_que_nao_confere_e_recusada_edge_case() -> None:
    """Caso de borda: `persiste` só vale com o id de um achado conferido; o resto volta à sessão."""
    saida = verificacao("atende", [{**BLOQUEANTE_DO_README, "persiste": "achado-inventado"}])["saida"]
    saida["conferidos"] = [{"achado": "achado-goal-soma-v1-1", "parecer": "persiste", "prova": "README.md lido de novo: sem exemplo"}]

    problemas = conferir_verificacao(Verificacao.de_json(saida), ("C1", "C2"), ("D1",), conferidos=("achado-goal-soma-v1-1",))

    assert problemas == ("o achado 'README sem exemplo' persiste achado-inventado, que nao e achado conferido",)


def test_goal_fecha_na_conferencia_final_limpa_e_o_kernel_aceita_nominal(tmp_path: Path) -> None:
    """T2d.3: a caçada acha o bloqueante, a correção o trata, e a conferência final limpa fecha o Goal com a prova do kernel."""
    bancada = montar_bancada(tmp_path, roteiro_completo())

    parada = bancada.orquestrador().iniciar_da_spec(bancada.spec, bancada.repositorio, AUTONOMO)

    assert parada.fechou, parada.mensagem
    estado = _estado(bancada)
    ultima = estado.verificacoes[-1]
    assert [v.tipo for v in estado.verificacoes] == ["caca", "conferencia"]
    assert ultima.limpa and ultima.propriedades["final"] is True and estado.fechado
    assert motivos_para_nao_fechar(bancada.kernel.obter_view(), "goal-soma") == ()
