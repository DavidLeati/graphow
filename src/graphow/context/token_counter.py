"""Fachada de contagem de tokens sobre o estimador calibrado corrente.

A classe segue com a mesma superfície de antes; o que mudou é o que está por
baixo. A regra de quatro caracteres por token virou um estimador injetável e
calibrado por classe de caractere, em `context/tokenizacao.py`. Ver achado A-16.
"""

import json
from typing import Any

from graphow.context.tokenizacao import ESTIMADOR_PADRAO, EstimadorTokens


class ContadorTokens:
    """Contador determinístico de tokens delegado ao estimador configurado."""

    ESTIMADOR: EstimadorTokens = ESTIMADOR_PADRAO

    @classmethod
    def estimar_texto(cls, texto: str) -> int:
        """Estima o número de tokens de uma string."""
        return cls.ESTIMADOR.estimar_texto(texto)

    @classmethod
    def estimar_objeto(cls, obj: Any) -> int:
        """Serializa o objeto em JSON determinístico e calcula a contagem estimada."""
        if obj is None:
            return 0
        texto_json = json.dumps(obj, sort_keys=True, separators=(",", ":"))
        return cls.estimar_texto(texto_json)

    @classmethod
    def cabe_no_orcamento(cls, texto: str, orcamento: int) -> bool:
        """Verifica se o texto cabe dentro do limite de tokens especificado."""
        return cls.estimar_texto(texto) <= orcamento

    @classmethod
    def calibracao_em_uso(cls) -> str:
        """Nome da calibração corrente, para constar de recibos e medições."""
        return cls.ESTIMADOR.descrever()
