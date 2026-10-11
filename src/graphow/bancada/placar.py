"""`graphow bancada placar`: as execuções de uma saída contra a linha de base, com a variação de cada número.

Cada execução entra com o que `execucao.json` mediu (custo, tokens, minutos,
commits) e, se foi auditada, com o que `auditoria.json` extraiu do PLACAR
(critérios, sondas, bloqueantes). A linha de base entra por arquitetura, no
mesmo projeto. Na agenda do graphow 0.4.4 valem o custo, os tokens e os
minutos sem o Goal de acabamento, que é o comparável; a nota diz isso no fim
da tabela. A variação é percentual; contra uma base zero (bloqueantes da
enxuta, sondas do estoque no graphow), é a diferença absoluta.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from graphow.bancada.auditoria import ARQUIVO_DA_AUDITORIA
from graphow.bancada.execucao import ARQUIVO_DA_EXECUCAO, ler_json
from graphow.bancada.formatacao import SEM_VALOR, formatar_inteiro, formatar_minutos, formatar_tokens, formatar_variacao
from graphow.bancada.projetos import ErroDaBancada

CHAVE_DO_COMPARAVEL: str = "comparavel"
CAMPOS_DO_COMPARAVEL: tuple[str, ...] = ("custo_usd", "tokens", "minutos")
CABECALHO_DOS_NUMEROS: str = "| Execucao | Projeto | US$ | Tokens | Min | Commits | Criterios | Sondas ok | Bloqueantes |"
ALINHAMENTO_DOS_NUMEROS: str = "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: |"
CABECALHO_DAS_VARIACOES: str = "| Execucao | Contra | US$ | Tokens | Min | Commits | Atende | Sondas ok | Bloqueantes |"
ALINHAMENTO_DAS_VARIACOES: str = "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
CAMPOS_DA_VARIACAO: tuple[str, ...] = ("custo_usd", "tokens", "minutos", "commits", "atende", "sondas_ok", "bloqueantes")


@dataclass(frozen=True)
class Numeros:
    """O que o placar compara de uma execução; o que não foi medido fica None."""

    custo_usd: float | None = None
    tokens: int | None = None
    minutos: float | None = None
    commits: int | None = None
    atende: int | None = None
    parcial: int | None = None
    nao_atende: int | None = None
    sondas_ok: int | None = None
    sondas: int | None = None
    bloqueantes: int | None = None


@dataclass(frozen=True)
class LinhaDoPlacar:
    """Uma execução, ou uma referência da linha de base, num projeto."""

    rotulo: str
    arquitetura: str
    projeto: str
    numeros: Numeros
    observacao: str = ""


def ler_execucoes(saida: Path) -> tuple[LinhaDoPlacar, ...]:
    """Toda execução da saída (ou a própria saída, se for uma execução), em ordem de nome."""
    pastas = [saida] if (saida / ARQUIVO_DA_EXECUCAO).is_file() else sorted(saida.glob(f"*/{ARQUIVO_DA_EXECUCAO}"))
    execucoes = tuple(_ler_execucao(pasta if pasta.is_dir() else pasta.parent) for pasta in pastas)
    if not execucoes:
        raise ErroDaBancada("nenhuma execucao na saida", {"saida": str(saida)})
    return execucoes


def ler_linha_de_base(caminho: Path) -> dict[tuple[str, str], LinhaDoPlacar]:
    """As referências da linha de base por arquitetura e projeto, com o comparável onde houver."""
    execucoes = ler_json(caminho).get("execucoes", {})
    return {
        (arquitetura, projeto): _referencia(arquitetura, projeto, dados)
        for arquitetura, por_projeto in execucoes.items()
        for projeto, dados in por_projeto.items()
    }


def formatar_placar(execucoes: Sequence[LinhaDoPlacar], base: Mapping[tuple[str, str], LinhaDoPlacar]) -> tuple[str, ...]:
    """A tabela dos números, a das variações contra cada arquitetura de base e as observações."""
    referencias = [base[chave] for chave in sorted(base) if chave[1] in {execucao.projeto for execucao in execucoes}]
    linhas = [CABECALHO_DOS_NUMEROS, ALINHAMENTO_DOS_NUMEROS]
    linhas.extend(_linha_dos_numeros(linha) for linha in (*execucoes, *referencias))
    linhas.extend(("", CABECALHO_DAS_VARIACOES, ALINHAMENTO_DAS_VARIACOES))
    for execucao in execucoes:
        linhas.extend(_linha_da_variacao(execucao, referencia) for referencia in referencias if referencia.projeto == execucao.projeto)
    observacoes = [f"- {linha.rotulo}: {linha.observacao}" for linha in (*execucoes, *referencias) if linha.observacao]
    return tuple([*linhas, *([""] + observacoes if observacoes else [])])


def _ler_execucao(pasta: Path) -> LinhaDoPlacar:
    """`execucao.json` e, se houver, `auditoria.json` de uma pasta."""
    registro = ler_json(pasta / ARQUIVO_DA_EXECUCAO)
    metricas = registro.get("metricas", {})
    auditoria = ler_json(pasta / ARQUIVO_DA_AUDITORIA) if (pasta / ARQUIVO_DA_AUDITORIA).is_file() else {}
    placar = auditoria.get("placar") or {}
    criterios = placar.get("criterios") or {}
    numeros = Numeros(
        custo_usd=metricas.get("custo_usd"),
        tokens=metricas.get("tokens"),
        minutos=metricas.get("minutos"),
        commits=metricas.get("commits"),
        atende=criterios.get("atende"),
        parcial=criterios.get("parcial"),
        nao_atende=criterios.get("nao_atende"),
        sondas_ok=placar.get("sondas_ok"),
        sondas=_soma_ou_nada(placar.get("sondas_ok"), placar.get("sondas_defeito")),
        bloqueantes=placar.get("bloqueantes"),
    )
    return LinhaDoPlacar(pasta.name, str(registro.get("arquitetura")), str(registro.get("projeto")), numeros, _observacao(registro, auditoria))


def _referencia(arquitetura: str, projeto: str, dados: Mapping[str, Any]) -> LinhaDoPlacar:
    """Uma entrada da linha de base; o comparável, quando existe, troca custo, tokens e minutos."""
    comparavel = dados.get(CHAVE_DO_COMPARAVEL) or {}
    valores = {**dados, **{campo: comparavel[campo] for campo in CAMPOS_DO_COMPARAVEL if campo in comparavel}}
    criterios = dados.get("criterios") or {}
    nomes = {campo.name for campo in fields(Numeros)}
    numeros = Numeros(**{chave: valor for chave, valor in {**valores, **criterios}.items() if chave in nomes})
    observacao = "custo, tokens e minutos sem o Goal de acabamento (o comparavel)" if comparavel else ""
    return LinhaDoPlacar(f"base {arquitetura}", arquitetura, projeto, numeros, observacao)


def _linha_dos_numeros(linha: LinhaDoPlacar) -> str:
    """Uma linha da tabela dos números."""
    numeros = linha.numeros
    criterios = SEM_VALOR if numeros.atende is None else f"{numeros.atende}/{numeros.parcial}/{numeros.nao_atende}"
    sondas = SEM_VALOR if numeros.sondas_ok is None else f"{numeros.sondas_ok}/{numeros.sondas}"
    celulas = (
        linha.rotulo,
        linha.projeto,
        SEM_VALOR if numeros.custo_usd is None else f"{numeros.custo_usd:.2f}".replace(".", ","),
        formatar_tokens(numeros.tokens),
        formatar_minutos(numeros.minutos),
        formatar_inteiro(numeros.commits),
        criterios,
        sondas,
        formatar_inteiro(numeros.bloqueantes),
    )
    return "| " + " | ".join(celulas) + " |"


def _linha_da_variacao(execucao: LinhaDoPlacar, referencia: LinhaDoPlacar) -> str:
    """A variação de cada número da execução contra uma referência do mesmo projeto."""
    variacoes = (
        formatar_variacao(getattr(execucao.numeros, campo), getattr(referencia.numeros, campo)) for campo in CAMPOS_DA_VARIACAO
    )
    return "| " + " | ".join((execucao.rotulo, referencia.arquitetura, *variacoes)) + " |"


def _observacao(registro: Mapping[str, Any], auditoria: Mapping[str, Any]) -> str:
    """O que o leitor precisa saber da execução: erro, falta de auditoria ou auditoria sem placar."""
    if registro.get("erro"):
        return f"execucao com erro: {registro['erro']}"
    if not auditoria:
        return "sem auditoria: criterios, sondas e bloqueantes em aberto"
    return f"auditoria com erro: {auditoria['erro']}" if auditoria.get("erro") else ""


def _soma_ou_nada(primeiro: int | None, segundo: int | None) -> int | None:
    """A soma de dois números do placar, ou None se faltar um."""
    return None if primeiro is None or segundo is None else primeiro + segundo
