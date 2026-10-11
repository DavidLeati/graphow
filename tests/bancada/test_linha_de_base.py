"""A medição da bancada reproduz a linha de base a partir dos logs do laboratório.

`dados/laboratorio.json.gz` guarda, das seis execuções de 10/10/2026, só o que
a medição lê: do stream-json de cada raiz, as marcas `_lab`, o `system/init` e
os eventos `result` (sem o texto); de cada transcrição em `~/.claude/projects`
(a da sessão e as dos subagentes), a primeira e a última entrada de cada
mensagem do modelo, com o instante e o `usage`. Os logs inteiros têm 8 MB; o
recorte, 47 KB, e dá os mesmos números.
"""

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from graphow.bancada.medicao import Invocacao, contar_sessoes_retomadas, invocacoes_do_log, medir
from graphow.bancada.projetos import Bancada

RECORTE: Path = Path(__file__).parent / "dados" / "laboratorio.json.gz"
EXECUCOES: tuple[tuple[str, str], ...] = tuple(
    (arquitetura, projeto)
    for arquitetura in ("graphow-0.4.4", "enxuta")
    for projeto in ("agenda-salas", "api-tarefas", "estoque-loja")
)
TOLERANCIA_DE_TOKENS: float = 0.01
TOLERANCIA_DE_MINUTOS: float = 1.0
TOLERANCIA_DE_CUSTO: float = 0.005


@pytest.fixture(scope="module")
def laboratorio(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """O recorte desdobrado em disco: um log por execução e as transcrições numa pasta de projetos."""
    dados = json.loads(gzip.decompress(RECORTE.read_bytes()))
    raiz = tmp_path_factory.mktemp("laboratorio")
    for chave, execucao in dados.items():
        pasta = raiz / "projetos" / chave.replace("/", "-")
        for relativo, entradas in execucao["transcricoes"].items():
            (pasta / relativo).parent.mkdir(parents=True, exist_ok=True)
            (pasta / relativo).write_text("".join(json.dumps(entrada) + "\n" for entrada in entradas), encoding="utf-8")
    return {"raiz": raiz / "projetos", "dados": dados}


@pytest.fixture(scope="module")
def linha_de_base() -> dict[str, Any]:
    """`bancada/linha-de-base.json`, por arquitetura e projeto."""
    return json.loads(Bancada().linha_de_base.read_text(encoding="utf-8"))["execucoes"]


def _invocacoes(laboratorio: dict[str, Any], arquitetura: str, projeto: str) -> tuple[Invocacao, ...]:
    """As invocações do log recortado de uma execução."""
    stream = laboratorio["dados"][f"{arquitetura}/{projeto}"]["stream"]
    return invocacoes_do_log(json.dumps(evento) for evento in stream)


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_medicao_reproduz_custo_tokens_e_minutos_da_linha_de_base_nominal(
    laboratorio: dict[str, Any], linha_de_base: dict[str, Any], arquitetura: str, projeto: str
) -> None:
    """Custo em centavos, tokens com até 1% e minutos com até 1 min de diferença."""
    base = linha_de_base[arquitetura][projeto]

    medicao = medir(_invocacoes(laboratorio, arquitetura, projeto), laboratorio["raiz"])

    assert abs(medicao.custo_usd - base["custo_usd"]) < TOLERANCIA_DE_CUSTO
    assert abs(medicao.tokens - base["tokens"]) <= TOLERANCIA_DE_TOKENS * base["tokens"]
    assert medicao.minutos is not None and abs(medicao.minutos - base["minutos"]) <= TOLERANCIA_DE_MINUTOS
    assert medicao.fonte_dos_tokens == "transcricoes"


def test_agenda_do_graphow_sem_o_acabamento_e_o_comparavel_nominal(
    laboratorio: dict[str, Any], linha_de_base: dict[str, Any]
) -> None:
    """As duas primeiras invocações (gerente e Goal principal), sem a terceira, a do Goal de acabamento."""
    comparavel = linha_de_base["graphow-0.4.4"]["agenda-salas"]["comparavel"]

    medicao = medir(_invocacoes(laboratorio, "graphow-0.4.4", "agenda-salas")[:2], laboratorio["raiz"])

    assert abs(medicao.custo_usd - comparavel["custo_usd"]) < TOLERANCIA_DE_CUSTO
    assert abs(medicao.tokens - comparavel["tokens"]) <= TOLERANCIA_DE_TOKENS * comparavel["tokens"]
    assert medicao.minutos is not None and abs(medicao.minutos - comparavel["minutos"]) <= TOLERANCIA_DE_MINUTOS


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_linha_de_base_bate_com_o_relatorio_nas_tolerancias_nominal(
    linha_de_base: dict[str, Any], arquitetura: str, projeto: str
) -> None:
    """Tokens e minutos medidos são os do relatório, que os arredondou para exibir."""
    base = linha_de_base[arquitetura][projeto]
    relatorio = base["relatorio"]

    assert abs(base["tokens"] - relatorio["tokens"]) <= TOLERANCIA_DE_TOKENS * relatorio["tokens"]
    assert abs(base["minutos"] - relatorio["minutos"]) <= TOLERANCIA_DE_MINUTOS
    for campo in ("custo_usd", "tokens", "minutos", "commits", "criterios", "sondas_ok", "bloqueantes"):
        assert campo in base["fontes"], (arquitetura, projeto, campo)


@pytest.mark.parametrize(("arquitetura", "projeto"), EXECUCOES)
def test_custo_do_relatorio_e_a_soma_dos_resultados_acumulados_edge_case(
    laboratorio: dict[str, Any], linha_de_base: dict[str, Any], arquitetura: str, projeto: str
) -> None:
    """Caso de borda: o relatório somou os `result` de cada invocação. Na enxuta, de sessão única, a soma é o custo;
    no graphow, de sessões retomadas, a soma conta duas vezes o que veio antes, e a linha de base corrige."""
    invocacoes = _invocacoes(laboratorio, arquitetura, projeto)
    soma = sum(invocacao.resultado.custo_usd for invocacao in invocacoes if invocacao.resultado)
    base = linha_de_base[arquitetura][projeto]

    assert abs(soma - base["relatorio"]["custo_usd"]) < TOLERANCIA_DE_CUSTO
    if contar_sessoes_retomadas(invocacoes):
        assert base["custo_usd"] < base["relatorio"]["custo_usd"]
    else:
        assert base["custo_usd"] == base["relatorio"]["custo_usd"]
