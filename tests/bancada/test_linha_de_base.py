"""A linha de base contra números âncora fixados aqui, e a regra que os explica, medidos do recorte dos logs.

Comparar a medição com `linha-de-base.json` é circular quando a linha de base
saiu da própria medição. Os números de que tudo depende ficam então escritos
aqui, à mão: o custo corrigido de cada execução, o publicado no relatório de
10/10 e os commits. A regra vem conferida dos `result` crus do recorte, sem
passar pela medição: o `result` de uma sessão retomada com `--resume` traz o
custo acumulado da sessão, então o custo é a soma do último `result` de cada
`session_id`, e a soma de todos os `result` (o que o relatório publicou)
conta duas vezes o que veio antes de cada retomada. A medição e a linha de
base têm de dar os mesmos números âncora.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from graphow.bancada.execucao import ler_json
from graphow.bancada.medicao import Invocacao, contar_sessoes_retomadas, invocacoes_do_log, medir
from graphow.bancada.projetos import Bancada
from graphow.bancada.transcricoes import contar_tokens, localizar_transcricoes
from graphow.sessoes.leitura_stream import ResultadoDoStream, ler_resultado

from tests.bancada.apoio_laboratorio import desdobrar_recorte, ler_recorte

GRAPHOW: str = "graphow-0.4.4"
ENXUTA: str = "enxuta"
EXECUCOES: tuple[tuple[str, str], ...] = tuple(
    (arquitetura, projeto) for arquitetura in (GRAPHOW, ENXUTA) for projeto in ("agenda-salas", "estoque-loja", "api-tarefas")
)

# Custo corrigido: a soma do último `result` de cada sessão.
CUSTO_CORRIGIDO_USD: dict[tuple[str, str], float] = {
    (GRAPHOW, "agenda-salas"): 10.65,
    (GRAPHOW, "estoque-loja"): 7.30,
    (GRAPHOW, "api-tarefas"): 8.77,
    (ENXUTA, "agenda-salas"): 4.78,
    (ENXUTA, "estoque-loja"): 5.03,
    (ENXUTA, "api-tarefas"): 6.24,
}
# A agenda do graphow sem a terceira invocação, a do Goal de acabamento.
CUSTO_CORRIGIDO_DA_AGENDA_SEM_ACABAMENTO_USD: float = 7.57
# O que o relatório de 10/10 publicou: a soma de todos os `result`, acumulados.
CUSTO_PUBLICADO_USD: dict[tuple[str, str], float] = {
    (GRAPHOW, "agenda-salas"): 18.58,
    (GRAPHOW, "estoque-loja"): 7.73,
    (GRAPHOW, "api-tarefas"): 9.09,
    (ENXUTA, "agenda-salas"): 4.78,
    (ENXUTA, "estoque-loja"): 5.03,
    (ENXUTA, "api-tarefas"): 6.24,
}
CUSTO_PUBLICADO_DA_AGENDA_SEM_ACABAMENTO_USD: float = 7.93
# Commits no ramo de trabalho depois da semente, contados nos repositórios do laboratório.
COMMITS: dict[tuple[str, str], int] = {
    (GRAPHOW, "agenda-salas"): 0,
    (GRAPHOW, "estoque-loja"): 7,
    (GRAPHOW, "api-tarefas"): 0,
    (ENXUTA, "agenda-salas"): 11,
    (ENXUTA, "estoque-loja"): 11,
    (ENXUTA, "api-tarefas"): 10,
}
# O que o relatório e o plano publicaram para a enxuta (a agenda contou o Estado inicial).
COMMITS_PUBLICADOS_DA_ENXUTA: dict[str, int] = {"agenda-salas": 12, "estoque-loja": 11, "api-tarefas": 11}
# A conferência de que o `result` é acumulado, na agenda do graphow: o `modelUsage` do último bate com as
# transcrições pela última entrada de cada mensagem, e a soma dos três não.
TOKENS_DO_ULTIMO_RESULT_DA_AGENDA: int = 15_435_012
TOKENS_DA_SOMA_DOS_RESULTS_DA_AGENDA: int = 26_232_290


@pytest.fixture(scope="module")
def recorte() -> dict[str, Any]:
    """O recorte dos logs por `<arquitetura>/<projeto>`."""
    return ler_recorte()


@pytest.fixture(scope="module")
def projetos(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """As transcrições do recorte numa pasta de projetos, como em `~/.claude/projects`."""
    return desdobrar_recorte(tmp_path_factory.mktemp("laboratorio"))[1]


@pytest.fixture(scope="module")
def linha_de_base() -> dict[str, Any]:
    """`bancada/linha-de-base.json`, inteira."""
    return ler_json(Bancada().linha_de_base)


def _results(recorte: dict[str, Any], arquitetura: str, projeto: str) -> list[ResultadoDoStream]:
    """Os eventos `result` do log, na ordem em que saíram, lidos crus."""
    return [ler_resultado(evento) for evento in recorte[f"{arquitetura}/{projeto}"]["stream"] if evento.get("type") == "result"]


def _ultimo_por_sessao(resultados: list[ResultadoDoStream]) -> dict[str, ResultadoDoStream]:
    """O último `result` de cada `session_id`."""
    return {resultado.session_id: resultado for resultado in resultados}


def _invocacoes(recorte: dict[str, Any], arquitetura: str, projeto: str) -> tuple[Invocacao, ...]:
    """As invocações do log recortado, pelas marcas `_lab`."""
    return invocacoes_do_log(json.dumps(evento) for evento in recorte[f"{arquitetura}/{projeto}"]["stream"])


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_ultimo_result_de_cada_sessao_da_o_custo_corrigido_nominal(recorte: dict[str, Any], arquitetura: str, projeto: str) -> None:
    """A regra, dos `result` crus: soma-se só o último de cada `session_id`."""
    ultimos = _ultimo_por_sessao(_results(recorte, arquitetura, projeto))

    assert round(sum(resultado.custo_usd for resultado in ultimos.values()), 2) == CUSTO_CORRIGIDO_USD[(arquitetura, projeto)]


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_soma_de_todos_os_results_da_o_custo_publicado_edge_case(recorte: dict[str, Any], arquitetura: str, projeto: str) -> None:
    """Caso de borda: o relatório somou os `result`; no graphow, de sessão retomada, isso conta duas vezes o que veio
    antes e infla o custo; na enxuta, de sessão única, a soma é o próprio custo."""
    resultados = _results(recorte, arquitetura, projeto)
    retomada = len(resultados) > len(_ultimo_por_sessao(resultados))

    assert round(sum(resultado.custo_usd for resultado in resultados), 2) == CUSTO_PUBLICADO_USD[(arquitetura, projeto)]
    assert retomada is (arquitetura == GRAPHOW)
    assert (CUSTO_PUBLICADO_USD[(arquitetura, projeto)] > CUSTO_CORRIGIDO_USD[(arquitetura, projeto)]) is retomada


def test_agenda_sem_acabamento_e_o_acumulado_da_segunda_invocacao_nominal(recorte: dict[str, Any]) -> None:
    """O comparável: o `result` da segunda invocação já é o acumulado das duas; o relatório somou a primeira de novo."""
    primeira, segunda, _ = _results(recorte, GRAPHOW, "agenda-salas")

    assert round(segunda.custo_usd, 2) == CUSTO_CORRIGIDO_DA_AGENDA_SEM_ACABAMENTO_USD
    assert round(primeira.custo_usd + segunda.custo_usd, 2) == CUSTO_PUBLICADO_DA_AGENDA_SEM_ACABAMENTO_USD


@pytest.mark.parametrize("projeto", ["agenda-salas", "estoque-loja", "api-tarefas"])
def test_result_de_sessao_retomada_e_acumulado_e_as_transcricoes_confirmam_edge_case(
    recorte: dict[str, Any], projetos: Path, projeto: str
) -> None:
    """Caso de borda: o custo da sessão retomada nunca diminui, e as transcrições ficam com o `modelUsage` do último
    `result`, e não com a soma deles: é o que mostra que cada `result` traz o acumulado da sessão."""
    resultados = _results(recorte, GRAPHOW, projeto)
    (sessao,) = _ultimo_por_sessao(resultados)
    transcricoes = contar_tokens(localizar_transcricoes(projetos, sessao)).pela_ultima
    ultimo, soma = resultados[-1].tokens.total, sum(resultado.tokens.total for resultado in resultados)

    assert [resultado.custo_usd for resultado in resultados] == sorted(resultado.custo_usd for resultado in resultados)
    assert abs(transcricoes - ultimo) < abs(transcricoes - soma) / 100
    if projeto == "agenda-salas":
        assert (ultimo, soma, transcricoes) == (TOKENS_DO_ULTIMO_RESULT_DA_AGENDA, TOKENS_DA_SOMA_DOS_RESULTS_DA_AGENDA, ultimo)


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_medicao_da_os_numeros_ancora_e_a_linha_de_base_os_grava_nominal(
    recorte: dict[str, Any], projetos: Path, linha_de_base: dict[str, Any], arquitetura: str, projeto: str
) -> None:
    """A medição dos logs dá o custo âncora, e a linha de base grava ele, o publicado e os commits âncora."""
    invocacoes = _invocacoes(recorte, arquitetura, projeto)
    gravado = linha_de_base["execucoes"][arquitetura][projeto]

    medicao = medir(invocacoes, projetos)

    assert medicao.custo_usd is not None and round(medicao.custo_usd, 2) == CUSTO_CORRIGIDO_USD[(arquitetura, projeto)]
    assert (medicao.tokens, round(medicao.minutos or 0, 1)) == (gravado["tokens"], gravado["minutos"])
    assert medicao.fonte_dos_tokens == "transcricoes"
    assert contar_sessoes_retomadas(invocacoes) == (1 if arquitetura == GRAPHOW else 0)
    assert gravado["custo_usd"] == CUSTO_CORRIGIDO_USD[(arquitetura, projeto)]
    assert gravado["relatorio"]["custo_usd"] == CUSTO_PUBLICADO_USD[(arquitetura, projeto)]
    assert gravado["commits"] == COMMITS[(arquitetura, projeto)]


def test_comparavel_da_agenda_medido_e_gravado_nominal(recorte: dict[str, Any], projetos: Path, linha_de_base: dict[str, Any]) -> None:
    """As duas primeiras invocações da agenda do graphow, medidas e gravadas como o comparável."""
    gravado = linha_de_base["execucoes"][GRAPHOW]["agenda-salas"]
    comparavel = gravado["comparavel"]

    medicao = medir(_invocacoes(recorte, GRAPHOW, "agenda-salas")[: comparavel["invocacoes"]], projetos)

    assert medicao.custo_usd is not None and round(medicao.custo_usd, 2) == CUSTO_CORRIGIDO_DA_AGENDA_SEM_ACABAMENTO_USD
    assert comparavel["custo_usd"] == CUSTO_CORRIGIDO_DA_AGENDA_SEM_ACABAMENTO_USD
    assert (medicao.tokens, round(medicao.minutos or 0, 1)) == (comparavel["tokens"], comparavel["minutos"])
    assert gravado["relatorio"]["custo_sem_acabamento_usd"] == CUSTO_PUBLICADO_DA_AGENDA_SEM_ACABAMENTO_USD


@pytest.mark.parametrize("projeto", ["agenda-salas", "estoque-loja", "api-tarefas"])
def test_commits_publicados_da_enxuta_ficam_ao_lado_dos_corrigidos_edge_case(linha_de_base: dict[str, Any], projeto: str) -> None:
    """Caso de borda: o relatório e o plano contaram 12/11/11 commits na enxuta; os ramos têm 11/11/10."""
    gravado = linha_de_base["execucoes"][ENXUTA][projeto]

    assert (gravado["commits"], gravado["relatorio"]["commits"]) == (COMMITS[(ENXUTA, projeto)], COMMITS_PUBLICADOS_DA_ENXUTA[projeto])


def test_correcoes_ao_relatorio_registram_o_publicado_e_o_correto_nominal(linha_de_base: dict[str, Any]) -> None:
    """O bloco `correcoes_ao_relatorio` traz o custo publicado e o correto de cada execução, e os commits da enxuta,
    e diz o mesmo que os números âncora."""
    correcoes = linha_de_base["correcoes_ao_relatorio"]
    custos = {
        (arquitetura, projeto): (valores["publicado"], valores["correto"])
        for arquitetura, por_projeto in correcoes["custo_usd"].items()
        for projeto, valores in por_projeto.items()
    }
    commits = {projeto: (valores["publicado"], valores["correto"]) for projeto, valores in correcoes["commits"]["enxuta"].items()}

    assert custos.pop((GRAPHOW, "agenda-salas sem acabamento")) == (
        CUSTO_PUBLICADO_DA_AGENDA_SEM_ACABAMENTO_USD,
        CUSTO_CORRIGIDO_DA_AGENDA_SEM_ACABAMENTO_USD,
    )
    assert custos == {chave: (CUSTO_PUBLICADO_USD[chave], CUSTO_CORRIGIDO_USD[chave]) for chave in EXECUCOES}
    assert commits == {projeto: (COMMITS_PUBLICADOS_DA_ENXUTA[projeto], COMMITS[(ENXUTA, projeto)]) for projeto in commits}
    assert set(commits) == {"agenda-salas", "estoque-loja", "api-tarefas"}
    assert "somou os custos acumulados" in correcoes["resumo"]


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_cada_numero_da_linha_de_base_diz_de_onde_saiu_nominal(linha_de_base: dict[str, Any], arquitetura: str, projeto: str) -> None:
    """Tokens e minutos medidos ficam a até 1% e 1 min do relatório, que os arredondou; e todo número tem fonte."""
    gravado = linha_de_base["execucoes"][arquitetura][projeto]
    relatorio = gravado["relatorio"]

    assert abs(gravado["tokens"] - relatorio["tokens"]) <= 0.01 * relatorio["tokens"]
    assert abs(gravado["minutos"] - relatorio["minutos"]) <= 1.0
    for campo in ("custo_usd", "tokens", "minutos", "commits", "criterios", "sondas_ok", "bloqueantes"):
        assert campo in gravado["fontes"], (arquitetura, projeto, campo)
