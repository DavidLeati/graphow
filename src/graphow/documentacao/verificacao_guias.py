"""Confere os exemplos de linha de comando dos guias contra o parser real.

O gerador de catálogo cobria `docs/`. Os guias e o script de teste em `.agents/`
ficaram de fora e apodreceram em silêncio: dois deles iniciavam o servidor MCP
sem `--papel`, obrigatório desde o Passo 1, e o script terminava em
`JSONDecodeError` porque o processo saía com erro de argumento antes de
responder. Aqui cada invocação documentada é passada pelo argparse de verdade.
Ver achado A-14.
"""

import argparse
from collections.abc import Iterator, Sequence
import contextlib
from dataclasses import dataclass
from enum import Enum
import io
import json
from pathlib import Path
import re
import shlex

PADRAO_INVOCACAO_CLI: re.Pattern[str] = re.compile(r"^\s*(?:\$\s*)?graphow\s+(?P<argumentos>\S.*)$")
PADRAO_INVOCACAO_STDIO: re.Pattern[str] = re.compile(
    r"^\s*(?:\$\s*)?(?:python|py)\s+-m\s+graphow\.mcp\.stdio_server\s*(?P<argumentos>.*)$"
)
PADRAO_ARGS_JSON: re.Pattern[str] = re.compile(r'"args"\s*:\s*(?P<lista>\[[^\]]*\])', re.DOTALL)
# A aspa escapada dentro do comando faz parte do valor: sem tratar a barra, o
# casamento parava em `--sessao "` e escondia justamente a variavel ofensora.
PADRAO_COMANDO_JSON: re.Pattern[str] = re.compile(
    r'"command"\s*:\s*"(?P<comando>(?:[^"\\]|\\.)*)"'
)

# O comando do hook nao passa por um shell do Graphow: uma variavel nao expandida
# chega ao argparse como texto e vira caminho vazio no patch. Ver defeito V-02.
PADRAO_VARIAVEL_DE_AMBIENTE: re.Pattern[str] = re.compile(r"\$\{?\w+\}?|%\w+%")

MODULO_STDIO: str = "graphow.mcp.stdio_server"
EXTENSOES_DE_GUIA: tuple[str, ...] = ("*.md", "*.json")


class AlvoDeParser(str, Enum):
    """Qual analisador de argumentos valida a invocação encontrada."""

    CLI = "graphow"
    STDIO = "graphow.mcp.stdio_server"


@dataclass(frozen=True)
class InvocacaoDocumentada:
    """Uma chamada de linha de comando encontrada em um guia."""

    arquivo: str
    linha: int
    alvo: AlvoDeParser
    argumentos: tuple[str, ...]

    def descrever(self) -> str:
        """Texto legível da invocação, para a mensagem de falha."""
        return f"{self.alvo.value} {' '.join(self.argumentos)}".strip()


@dataclass(frozen=True)
class ProblemaEmGuia:
    """Invocação documentada que o parser real recusaria."""

    arquivo: str
    linha: int
    invocacao: str
    motivo: str

    def descrever(self) -> str:
        """Linha de relatório apontando arquivo, posição e causa."""
        return f"{self.arquivo}:{self.linha}: `{self.invocacao}` -> {self.motivo}"


def _construir_parser(alvo: AlvoDeParser) -> argparse.ArgumentParser:
    """Devolve o parser de produção correspondente ao alvo da invocação."""
    from graphow.api.cli_parser import construir_parser
    from graphow.mcp.stdio_server import _construir_parser as construir_parser_stdio

    if alvo == AlvoDeParser.CLI:
        return construir_parser()
    return construir_parser_stdio()


def validar_invocacao(invocacao: InvocacaoDocumentada) -> ProblemaEmGuia | None:
    """Passa a invocação pelo argparse real, capturando a recusa como problema."""
    parser = _construir_parser(invocacao.alvo)
    erros = io.StringIO()
    try:
        with contextlib.redirect_stderr(erros):
            parser.parse_args(list(invocacao.argumentos))
    except SystemExit:
        return ProblemaEmGuia(
            arquivo=invocacao.arquivo,
            linha=invocacao.linha,
            invocacao=invocacao.descrever(),
            motivo=_resumir_erro(erros.getvalue()),
        )
    return None


def _resumir_erro(saida_de_erro: str) -> str:
    """Extrai a última linha significativa da recusa do argparse."""
    linhas = [linha.strip() for linha in saida_de_erro.splitlines() if linha.strip()]
    return linhas[-1] if linhas else "argumentos recusados pelo parser"


def extrair_invocacoes(caminho: Path, raiz: Path) -> tuple[InvocacaoDocumentada, ...]:
    """Reúne as invocações em texto e em blocos JSON de configuração do arquivo."""
    conteudo = caminho.read_text(encoding="utf-8")
    relativo = caminho.relative_to(raiz).as_posix()
    textuais = tuple(_extrair_de_linhas(conteudo, relativo))
    return (
        textuais
        + tuple(_extrair_de_blocos_json(conteudo, relativo))
        + tuple(_extrair_de_comandos_de_hook(conteudo, relativo))
    )


def _extrair_de_linhas(conteudo: str, relativo: str) -> Iterator[InvocacaoDocumentada]:
    """Percorre o texto procurando chamadas escritas para copiar e colar."""
    for numero, linha in enumerate(conteudo.splitlines(), start=1):
        invocacao = _reconhecer_linha(linha, relativo, numero)
        if invocacao is not None:
            yield invocacao


def _reconhecer_linha(linha: str, relativo: str, numero: int) -> InvocacaoDocumentada | None:
    """Identifica uma invocação de CLI ou de servidor stdio na linha."""
    correspondencia_stdio = PADRAO_INVOCACAO_STDIO.match(linha)
    if correspondencia_stdio is not None:
        argumentos = _dividir(correspondencia_stdio.group("argumentos"))
        return InvocacaoDocumentada(relativo, numero, AlvoDeParser.STDIO, argumentos)
    correspondencia_cli = PADRAO_INVOCACAO_CLI.match(linha)
    if correspondencia_cli is None:
        return None
    return InvocacaoDocumentada(
        relativo, numero, AlvoDeParser.CLI, _dividir(correspondencia_cli.group("argumentos"))
    )


def _dividir(texto: str) -> tuple[str, ...]:
    """Divide a linha em argumentos como um shell faria, tolerando aspas soltas."""
    try:
        return tuple(shlex.split(texto, posix=False))
    except ValueError:
        return tuple(texto.split())


def _extrair_de_blocos_json(conteudo: str, relativo: str) -> Iterator[InvocacaoDocumentada]:
    """Lê os arrays `args` das configurações de harness publicadas nos guias."""
    for correspondencia in PADRAO_ARGS_JSON.finditer(conteudo):
        argumentos = _interpretar_lista_json(correspondencia.group("lista"))
        if argumentos is None or MODULO_STDIO not in argumentos:
            continue
        linha = _numero_da_linha(conteudo, correspondencia.start())
        posteriores = argumentos[argumentos.index(MODULO_STDIO) + 1 :]
        yield InvocacaoDocumentada(relativo, linha, AlvoDeParser.STDIO, tuple(posteriores))


def _interpretar_lista_json(texto: str) -> list[str] | None:
    """Converte o array JSON em lista de strings, ignorando blocos malformados."""
    try:
        valores = json.loads(texto)
    except json.JSONDecodeError:
        return None
    if not isinstance(valores, list):
        return None
    return [str(valor) for valor in valores]


def validar_ausencia_de_variaveis(invocacao: InvocacaoDocumentada) -> ProblemaEmGuia | None:
    """Recusa o exemplo que depende de variável que o ambiente não expande.

    O argparse aceita `"$CLAUDE_SESSION_ID"` como texto qualquer, então este
    problema não aparece na validação de argumentos: precisa de regra própria.
    """
    encontradas = [arg for arg in invocacao.argumentos if PADRAO_VARIAVEL_DE_AMBIENTE.search(arg)]
    if not encontradas:
        return None
    return ProblemaEmGuia(
        arquivo=invocacao.arquivo,
        linha=invocacao.linha,
        invocacao=invocacao.descrever(),
        motivo=f"depende de variavel de ambiente nao definida: {' '.join(encontradas)}",
    )


def _extrair_de_comandos_de_hook(conteudo: str, relativo: str) -> Iterator[InvocacaoDocumentada]:
    """Lê os campos `command` das fiações de hook publicadas no repositório."""
    for correspondencia in PADRAO_COMANDO_JSON.finditer(conteudo):
        numero = _numero_da_linha(conteudo, correspondencia.start())
        comando = _desescapar(correspondencia.group("comando"))
        invocacao = _reconhecer_linha(comando, relativo, numero)
        if invocacao is not None:
            yield invocacao


def _desescapar(texto: str) -> str:
    """Devolve o comando como o shell o receberia, desfazendo o escape do JSON."""
    try:
        return str(json.loads(f'"{texto}"'))
    except json.JSONDecodeError:
        return texto


def _numero_da_linha(conteudo: str, posicao: int) -> int:
    """Converte a posição do casamento em número de linha do arquivo."""
    return conteudo.count("\n", 0, posicao) + 1


class VerificadorDeGuias:
    """Percorre os guias do repositório e valida cada exemplo executável."""

    def __init__(self, raiz: Path, diretorios: Sequence[str] = (".agents",)) -> None:
        self._raiz: Path = raiz
        self._diretorios: tuple[str, ...] = tuple(diretorios)

    def listar_guias(self) -> tuple[Path, ...]:
        """Enumera os documentos que contêm exemplos de linha de comando."""
        encontrados: list[Path] = []
        for diretorio in self._diretorios:
            encontrados.extend(self._listar_em(self._raiz / diretorio))
        readme = self._raiz / "README.md"
        return tuple(encontrados) + ((readme,) if readme.is_file() else ())

    def _listar_em(self, diretorio: Path) -> tuple[Path, ...]:
        """Reúne guias e fiações de hook de uma ala, em ordem estável."""
        encontrados: list[Path] = []
        for extensao in EXTENSOES_DE_GUIA:
            encontrados.extend(diretorio.rglob(extensao))
        return tuple(sorted(encontrados))

    def verificar(self) -> tuple[ProblemaEmGuia, ...]:
        """Consulta pura: devolve todo exemplo que o parser real recusaria."""
        problemas: list[ProblemaEmGuia] = []
        for guia in self.listar_guias():
            problemas.extend(self._verificar_guia(guia))
        return tuple(problemas)

    def _verificar_guia(self, guia: Path) -> tuple[ProblemaEmGuia, ...]:
        """Valida todas as invocações de um único documento."""
        problemas: list[ProblemaEmGuia] = []
        for invocacao in extrair_invocacoes(guia, self._raiz):
            problemas.extend(_avaliar_invocacao(invocacao))
        return tuple(problemas)


def _avaliar_invocacao(invocacao: InvocacaoDocumentada) -> tuple[ProblemaEmGuia, ...]:
    """Aplica as duas regras: o parser aceita, e nada depende do ambiente."""
    vereditos = (validar_invocacao(invocacao), validar_ausencia_de_variaveis(invocacao))
    return tuple(problema for problema in vereditos if problema is not None)
