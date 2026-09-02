"""Adaptadores de escrita em console imunes a limitações de codificação do terminal."""

from abc import ABC, abstractmethod
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
    da tabela, derrubando o comando antes de ele executar. Ver auditoria F-01.
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
