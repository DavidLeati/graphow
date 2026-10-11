"""`graphow bancada medir-laboratorio`: a linha de base medida de novo dos logs do laboratório, número a número.

A linha de base (`bancada/linha-de-base.json`) saiu dos logs de 10/10/2026: o
stream-json de cada raiz, com as marcas `_lab` em volta de cada invocação, as
transcrições das sessões e dos subagentes em `~/.claude/projects` e os
repositórios das entregas. Este comando mede tudo de novo, com a mesma medição
das execuções da bancada, e confere cada número contra o gravado: arredondado
como a linha de base o grava (custo em centavos, minutos com uma casa), o
medido tem de ser o gravado, e tokens e commits são exatos.

Confere também a correção do relatório publicado: a soma dos `result` de cada
invocação, que o relatório usou como custo, tem de dar o número dele
(`relatorio.custo_usd`), e a diferença para o custo corrigido vem das sessões
retomadas, contadas na tabela. Onde ficam os logs e os repositórios de cada
arquitetura, relativo à pasta do laboratório, vem da própria linha de base
(`laboratorio`). Sem o repositório, os commits ficam sem conferir, e a tabela
diz isso.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphow.bancada.entrega import ler_estado_da_entrega
from graphow.bancada.execucao import ler_json
from graphow.bancada.formatacao import SEM_VALOR, formatar_inteiro, formatar_minutos
from graphow.bancada.medicao import Invocacao, contar_sessoes_retomadas, ler_log, medir
from graphow.bancada.projetos import Bancada, ErroDaBancada

CHAVE_DO_LABORATORIO: str = "laboratorio"
CHAVE_DO_COMPARAVEL: str = "comparavel"
ROTULO_DO_COMPARAVEL: str = "sem acabamento"
NUMEROS_CONFERIDOS: tuple[str, ...] = ("custo_usd", "tokens", "minutos", "commits", "soma_dos_results")
CRITERIOS: Mapping[str, Callable[[float, float], bool]] = {
    "custo_usd": lambda medido, gravado: round(medido, 2) == gravado,
    "soma_dos_results": lambda medido, gravado: round(medido, 2) == gravado,
    "tokens": lambda medido, gravado: medido == gravado,
    "minutos": lambda medido, gravado: round(medido, 1) == gravado,
    "commits": lambda medido, gravado: medido == gravado,
}
CABECALHO: str = "| Execucao | US$ | Tokens | Min | Commits | Soma dos result | Retomadas | Confere |"
ALINHAMENTO: str = "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |"


@dataclass(frozen=True)
class NumeroConferido:
    """Um número medido dos logs ao lado do gravado; `confere` é None quando um dos dois falta."""

    nome: str
    medido: float | None
    gravado: float | None

    @property
    def confere(self) -> bool | None:
        """Se o medido, arredondado como o gravado, é ele; None sem os dois."""
        if self.medido is None or self.gravado is None:
            return None
        return CRITERIOS[self.nome](self.medido, self.gravado)


@dataclass(frozen=True)
class ConferenciaDaExecucao:
    """Os números de uma execução do laboratório (ou do comparável dela) medidos de novo."""

    rotulo: str
    numeros: tuple[NumeroConferido, ...]
    sessoes_retomadas: int
    observacao: str = ""

    @property
    def divergencias(self) -> tuple[NumeroConferido, ...]:
        """Os números que não bateram."""
        return tuple(numero for numero in self.numeros if numero.confere is False)

    def numero(self, nome: str) -> NumeroConferido:
        """O número pelo nome."""
        return next(numero for numero in self.numeros if numero.nome == nome)


@dataclass(frozen=True)
class _FonteDaExecucao:
    """Onde estão o log e o repositório de uma execução, e o que a linha de base gravou dela."""

    rotulo: str
    projeto: str
    log: Path
    repositorio: Path
    gravado: Mapping[str, Any]


@dataclass(frozen=True)
class Laboratorio:
    """A pasta do laboratório, a bancada com a linha de base e as transcrições das sessões."""

    raiz: Path
    bancada: Bancada
    transcricoes: Path | None

    def conferir(self) -> tuple[ConferenciaDaExecucao, ...]:
        """Cada execução da linha de base, e o comparável onde houver, medidos dos logs."""
        base = ler_json(self.bancada.linha_de_base)
        conferencias: list[ConferenciaDaExecucao] = []
        for fonte in self._fontes(base):
            conferencias.extend(self._conferir_execucao(fonte))
        return tuple(conferencias)

    def _fontes(self, base: Mapping[str, Any]) -> list[_FonteDaExecucao]:
        """As execuções gravadas, com o log e o repositório de cada uma sob a raiz do laboratório."""
        pastas = base.get(CHAVE_DO_LABORATORIO) or {}
        return [
            _FonteDaExecucao(
                rotulo=f"{arquitetura} {projeto}",
                projeto=projeto,
                log=self.raiz / pastas[arquitetura]["logs"] / f"{projeto}.jsonl",
                repositorio=self.raiz / pastas[arquitetura]["repositorios"] / projeto,
                gravado=gravado,
            )
            for arquitetura, por_projeto in (base.get("execucoes") or {}).items()
            for projeto, gravado in por_projeto.items()
        ]

    def _conferir_execucao(self, fonte: _FonteDaExecucao) -> tuple[ConferenciaDaExecucao, ...]:
        """A execução inteira e, se a linha de base tem comparável, as primeiras invocações dela."""
        if not fonte.log.is_file():
            raise ErroDaBancada("log do laboratorio ausente", {"execucao": fonte.rotulo, "log": str(fonte.log)})
        invocacoes = ler_log(fonte.log)
        relatorio = fonte.gravado.get("relatorio") or {}
        commits, observacao = self._commits(fonte)
        gravado = {**fonte.gravado, "soma_dos_results": relatorio.get("custo_usd")}
        conferencias = [self._medir(fonte.rotulo, invocacoes, gravado, commits=commits, observacao=observacao)]
        comparavel = fonte.gravado.get(CHAVE_DO_COMPARAVEL)
        if comparavel:
            gravado = {**comparavel, "soma_dos_results": relatorio.get("custo_sem_acabamento_usd")}
            primeiras = invocacoes[: int(comparavel["invocacoes"])]
            conferencias.append(self._medir(f"{fonte.rotulo} {ROTULO_DO_COMPARAVEL}", primeiras, gravado, commits=None))
        return tuple(conferencias)

    def _medir(
        self, rotulo: str, invocacoes: Sequence[Invocacao], gravado: Mapping[str, Any], *, commits: int | None, observacao: str = ""
    ) -> ConferenciaDaExecucao:
        """Custo, tokens e minutos medidos, a soma dos `result` e os commits, ao lado do gravado."""
        medicao = medir(invocacoes, self.transcricoes)
        medidos = {
            "custo_usd": medicao.custo_usd,
            "tokens": medicao.tokens,
            "minutos": medicao.minutos,
            "commits": commits,
            "soma_dos_results": sum(invocacao.resultado.custo_usd for invocacao in invocacoes if invocacao.resultado),
        }
        numeros = tuple(NumeroConferido(nome, medidos[nome], gravado.get(nome)) for nome in NUMEROS_CONFERIDOS)
        return ConferenciaDaExecucao(rotulo, numeros, contar_sessoes_retomadas(invocacoes), observacao)

    def _commits(self, fonte: _FonteDaExecucao) -> tuple[int | None, str]:
        """Os commits do ramo de trabalho depois da semente, ou nenhum e o porquê."""
        if not fonte.repositorio.is_dir():
            return None, f"commits sem conferir: repositorio ausente em {fonte.repositorio}"
        return ler_estado_da_entrega(fonte.repositorio, self.bancada.projeto(fonte.projeto)).commits, ""


def formatar_conferencias(conferencias: Sequence[ConferenciaDaExecucao]) -> tuple[str, ...]:
    """A tabela do que foi medido, as divergências contra a linha de base e o que ficou sem conferir."""
    linhas = [CABECALHO, ALINHAMENTO, *(_linha(conferencia) for conferencia in conferencias)]
    divergencias = [
        f"- {conferencia.rotulo}: {numero.nome} medido {_valor(numero.medido)} contra {_valor(numero.gravado)} na linha de base"
        for conferencia in conferencias
        for numero in conferencia.divergencias
    ]
    observacoes = [f"- {conferencia.rotulo}: {conferencia.observacao}" for conferencia in conferencias if conferencia.observacao]
    for titulo, itens in (("Divergencias:", divergencias), ("Observacoes:", observacoes)):
        linhas.extend(["", titulo, *itens] if itens else [])
    total = sum(len(conferencia.divergencias) for conferencia in conferencias)
    linhas.extend(["", f"{len(conferencias)} conferencias, {total} divergencias"])
    return tuple(linhas)


def _linha(conferencia: ConferenciaDaExecucao) -> str:
    """Uma linha da tabela, com o medido de cada número e se tudo bateu."""
    custo, soma = (conferencia.numero(nome).medido for nome in ("custo_usd", "soma_dos_results"))
    celulas = (
        conferencia.rotulo,
        SEM_VALOR if custo is None else f"{custo:.2f}".replace(".", ","),
        formatar_inteiro(_inteiro(conferencia.numero("tokens").medido)),
        formatar_minutos(conferencia.numero("minutos").medido),
        formatar_inteiro(_inteiro(conferencia.numero("commits").medido)),
        SEM_VALOR if soma is None else f"{soma:.2f}".replace(".", ","),
        str(conferencia.sessoes_retomadas),
        "NAO" if conferencia.divergencias else "sim",
    )
    return "| " + " | ".join(celulas) + " |"


def _inteiro(valor: float | None) -> int | None:
    """O número como inteiro, para a formatação de milhar."""
    return None if valor is None else int(valor)


def _valor(valor: float | None) -> str:
    """Um número da divergência, com até quatro casas: o bastante para ver por quanto errou."""
    if isinstance(valor, float):
        return str(round(valor, 4))
    return SEM_VALOR if valor is None else str(valor)
