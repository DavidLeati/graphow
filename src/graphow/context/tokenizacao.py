"""Estimadores de tokens atrás de uma interface, calibrados por classe de caractere.

A heurística fixa de quatro caracteres por token foi escrita para inglês em
ASCII. Os rótulos do Graphow são em português, com acentos e pictogramas, e
todos custam mais que isso nos tokenizadores BPE atuais: um orçamento declarado
de 1.500 chegava ao modelo maior do que o agente pediu, e qualquer métrica de
"tokens por tarefa" herdaria o mesmo erro. Ver achado A-16.

O custo por classe abaixo é um limite superior deliberado. Errar para cima gasta
orçamento; errar para baixo quebra a promessa da ferramenta, que é a única coisa
que o agente não tem como conferir. Quando um tokenizador real estiver
disponível, ele entra por `EstimadorTokens` sem tocar em quem chama.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import math
import unicodedata

PRIMEIRO_PONTO_ASTRAL: int = 0x10000
ULTIMO_PONTO_ASCII: int = 0x7F
ULTIMO_PONTO_LATINO_ESTENDIDO: int = 0x024F


class ClasseDeCaractere(str, Enum):
    """Faixas de custo distinto nos tokenizadores BPE de vocabulário grande."""

    ASCII = "ascii"
    LATINO_ACENTUADO = "latino_acentuado"
    OUTRO_PLANO_BASICO = "outro_plano_basico"
    ASTRAL = "astral"


# Um caractere ASCII entra em subpalavras longas; um acentuado quebra a fusão BPE
# e costuma sair sozinho; fora do latim quase não há fusão; um pictograma ocupa
# quatro bytes UTF-8 e vira dois ou mais tokens.
CUSTO_POR_CLASSE: dict[ClasseDeCaractere, float] = {
    ClasseDeCaractere.ASCII: 0.25,
    ClasseDeCaractere.LATINO_ACENTUADO: 0.5,
    ClasseDeCaractere.OUTRO_PLANO_BASICO: 1.0,
    ClasseDeCaractere.ASTRAL: 2.0,
}


def classificar(caractere: str) -> ClasseDeCaractere:
    """Consulta pura que enquadra o caractere na faixa de custo correspondente."""
    ponto = ord(caractere)
    if ponto <= ULTIMO_PONTO_ASCII:
        return ClasseDeCaractere.ASCII
    if ponto >= PRIMEIRO_PONTO_ASTRAL:
        return ClasseDeCaractere.ASTRAL
    if ponto <= ULTIMO_PONTO_LATINO_ESTENDIDO:
        return ClasseDeCaractere.LATINO_ACENTUADO
    return ClasseDeCaractere.OUTRO_PLANO_BASICO


class EstimadorTokens(ABC):
    """Contrato de estimativa de tokens usado por todo o materializador."""

    @abstractmethod
    def estimar_texto(self, texto: str) -> int:
        """Devolve o número estimado de tokens do texto informado."""
        raise NotImplementedError

    @abstractmethod
    def descrever(self) -> str:
        """Identifica a calibração em uso, para registro em métricas e recibos."""
        raise NotImplementedError


@dataclass(frozen=True)
class EstimadorPorClasseDeCaractere(EstimadorTokens):
    """Estimador padrão: soma o custo de cada caractere segundo a sua faixa."""

    nome: str = "classe-de-caractere-v1"

    def estimar_texto(self, texto: str) -> int:
        """Arredonda para cima a soma dos custos, nunca reportando menos que um."""
        if not texto:
            return 0
        custo = sum(CUSTO_POR_CLASSE[classificar(caractere)] for caractere in texto)
        return max(1, math.ceil(custo))

    def descrever(self) -> str:
        """Nome da calibração corrente."""
        return self.nome


@dataclass(frozen=True)
class EstimadorPorNormalizacao(EstimadorTokens):
    """Variante que decompõe acentos antes de medir, para textos já normalizados.

    Existe para tornar a escolha explícita: se o pipeline a montante normalizar
    em NFD, o acento vira um caractere combinante próprio e o custo muda. Medir
    a mesma string com as duas calibrações torna a diferença visível.
    """

    nome: str = "normalizacao-nfd-v1"

    def estimar_texto(self, texto: str) -> int:
        """Mede o texto após decomposição canônica."""
        return EstimadorPorClasseDeCaractere().estimar_texto(unicodedata.normalize("NFD", texto))

    def descrever(self) -> str:
        """Nome da calibração corrente."""
        return self.nome


ESTIMADOR_PADRAO: EstimadorTokens = EstimadorPorClasseDeCaractere()
