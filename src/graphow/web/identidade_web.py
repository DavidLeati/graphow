"""Identidade da sessão web, fixada no servidor e nunca lida do corpo da requisição.

POST e PUT liam `papel` do corpo com padrão "humano", e o JavaScript gravava um
autor fixo. Era o inverso exato da garantia do MCP: o log de autoria deixava de
ser confiável enquanto a interface estivesse aberta. O servidor é local e sem
autenticação, mas quem escreveu o quê é justamente o que o produto promete
mostrar. Ver achado A-11.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import getpass
from typing import Any

from graphow.core.types import PapelAutor

AUTOR_PADRAO_DA_INTERFACE: str = "humano-ui"

# Campos que a interface não tem o direito de declarar: a identidade é da conexão.
CAMPOS_DE_IDENTIDADE_RECUSADOS: frozenset[str] = frozenset({"papel", "autor"})


@dataclass(frozen=True)
class IdentidadeSessaoWeb:
    """Autor e papel de toda escrita vinda do canvas nesta execução do servidor."""

    autor: str = AUTOR_PADRAO_DA_INTERFACE
    papel: PapelAutor = PapelAutor.HUMANO

    @classmethod
    def do_usuario_local(cls) -> "IdentidadeSessaoWeb":
        """Identifica quem abriu o servidor, caindo no autor genérico se não der."""
        return cls(autor=cls._nome_do_usuario(), papel=PapelAutor.HUMANO)

    @staticmethod
    def _nome_do_usuario() -> str:
        """Lê o usuário do sistema operacional sem deixar a falha escapar."""
        try:
            nome = getpass.getuser().strip()
        except (OSError, KeyError):
            return AUTOR_PADRAO_DA_INTERFACE
        return nome or AUTOR_PADRAO_DA_INTERFACE

    @property
    def papel_textual(self) -> str:
        """Papel em texto, como os controladores REST o consomem."""
        return self.papel.value


def detectar_identidade_declarada(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Lista os campos de identidade que a requisição tentou declarar."""
    return tuple(sorted(campo for campo in CAMPOS_DE_IDENTIDADE_RECUSADOS if campo in payload))


def montar_recusa_de_identidade(
    campos: tuple[str, ...],
    identidade: IdentidadeSessaoWeb,
) -> dict[str, Any]:
    """Recusa explícita, no mesmo espírito da mensagem do servidor MCP.

    Ignorar o campo em silêncio faria a interface crer que ele surte efeito.
    """
    return {
        "sucesso": False,
        "mensagem": (
            f"Os campos {', '.join(campos)} nao sao aceitos no corpo da requisicao. "
            f"Esta sessao web escreve como '{identidade.autor}' "
            f"no papel '{identidade.papel_textual}', fixado na abertura do servidor."
        ),
        "versao_log": 0,
    }
