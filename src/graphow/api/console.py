"""Adaptadores de escrita em console imunes a limitações de codificação do terminal.

A saída que vai para um cano ou arquivo sai em UTF-8: no Windows o Python abre
os canos na página de código da máquina (cp1252), e quem lê a saída de um
comando (o Claude Code, um script, outro processo) espera UTF-8; "operações"
chegava como "opera\ufffd\ufffdes". O console de verdade (TTY) fica como está:
o Windows já escreve nele em Unicode.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
import sys
from typing import TextIO


class EscritorConsole(ABC):
    """Contrato de saída textual da linha de comando."""

    @abstractmethod
    def escrever_linha(self, texto: str) -> None:
        """Emite uma linha de texto para o operador."""
        raise NotImplementedError


class EscritorConsolePadrao(EscritorConsole):
    """Escreve no fluxo do processo sem jamais falhar por caractere não representável.

    Consoles Windows em cp1252 lançam UnicodeEncodeError em qualquer caractere fora
    da tabela, derrubando o comando antes de ele executar.
    """

    def __init__(self, fluxo: TextIO | None = None) -> None:
        self._fluxo: TextIO = fluxo if fluxo is not None else sys.stdout

    def escrever_linha(self, texto: str) -> None:
        """Escreve a linha substituindo caracteres que a codificação não suporta."""
        self._fluxo.write(self._transcrever_para_codificacao_do_fluxo(texto) + "\n")
        self._fluxo.flush()

    def _transcrever_para_codificacao_do_fluxo(self, texto: str) -> str:
        """Converte o texto para o que o fluxo consegue representar, sem levantar erro."""
        codificacao = getattr(self._fluxo, "encoding", None) or "utf-8"
        try:
            texto.encode(codificacao)
        except UnicodeEncodeError:
            return texto.encode(codificacao, errors="replace").decode(codificacao, errors="replace")
        return texto


def saida_em_utf8(fluxos: Sequence[TextIO] | None = None) -> None:
    """Põe em UTF-8 a saída padrão e a de erro que não são console; o fluxo que não sabe se reconfigurar fica."""
    for fluxo in fluxos if fluxos is not None else (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None and not fluxo.isatty():
            reconfigurar(encoding="utf-8", errors="replace")


class EscritorConsoleEmMemoria(EscritorConsole):
    """Captura as linhas emitidas, para asserção determinística em testes."""

    def __init__(self) -> None:
        self._linhas: list[str] = []

    def escrever_linha(self, texto: str) -> None:
        """Acumula a linha na lista interna."""
        self._linhas.append(texto)

    @property
    def linhas(self) -> tuple[str, ...]:
        """Cópia imutável das linhas emitidas até agora."""
        return tuple(self._linhas)
