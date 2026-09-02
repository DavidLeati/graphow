"""Identidade imutável de uma sessão MCP e política de autorização por ferramenta.

O papel do autor é propriedade da conexão, fixado quando o servidor MCP é aberto
pelo humano que o configura. Nenhum argumento de chamada de ferramenta pode
alterá-lo. Ver auditoria F-02.
"""

from dataclasses import dataclass

from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.types import PapelAutor

PAPEIS_VALIDOS_EM_SESSAO: frozenset[PapelAutor] = frozenset(
    {PapelAutor.HUMANO, PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR}
)

# Ferramentas cujo efeito anula uma garantia de governança se um agente as executar:
# responder_questao encerra a escalação ao humano; configurar_autonomia_projeto
# desliga o RoleGate do ramo; as exclusões apagam trabalho em cascata.
FERRAMENTAS_EXCLUSIVAS_DO_HUMANO: frozenset[str] = frozenset(
    {
        "responder_questao",
        "configurar_autonomia_projeto",
        "excluir_projeto",
        "excluir_em_lote",
    }
)


@dataclass(frozen=True)
class ResultadoAutorizacao:
    """Veredito imutável sobre a permissão de uso de uma ferramenta MCP."""

    autorizado: bool
    motivo: str

    @classmethod
    def permitido(cls) -> "ResultadoAutorizacao":
        """Constrói o veredito positivo padrão."""
        return cls(autorizado=True, motivo="")

    @classmethod
    def negado(cls, motivo: str) -> "ResultadoAutorizacao":
        """Constrói o veredito negativo com a justificativa exibida ao agente."""
        return cls(autorizado=False, motivo=motivo)


@dataclass(frozen=True)
class IdentidadeSessaoMCP:
    """Autor e papel fixados para toda a duração de uma sessão MCP."""

    autor: str
    papel: PapelAutor

    @classmethod
    def criar(cls, autor: str, papel_declarado: str) -> "IdentidadeSessaoMCP":
        """Valida e congela a identidade da sessão a partir da configuração do servidor."""
        autor_normalizado = autor.strip()
        if not autor_normalizado:
            raise ErroPermissaoPapel(
                "Uma sessao MCP exige um autor identificavel",
                {"autor_recebido": repr(autor)},
            )
        return cls(autor=autor_normalizado, papel=cls._converter_papel(papel_declarado))

    @staticmethod
    def _converter_papel(papel_declarado: str) -> PapelAutor:
        """Converte o texto do papel, recusando valores fora do contrato de sessão."""
        try:
            papel = PapelAutor(papel_declarado.strip().lower())
        except ValueError as erro:
            raise ErroPermissaoPapel(
                f"Papel de sessao invalido: '{papel_declarado}'",
                {"papeis_aceitos": ", ".join(sorted(p.value for p in PAPEIS_VALIDOS_EM_SESSAO))},
            ) from erro
        if papel not in PAPEIS_VALIDOS_EM_SESSAO:
            raise ErroPermissaoPapel(
                f"O papel '{papel.value}' nao pode ser atribuido a uma sessao MCP",
                {"papeis_aceitos": ", ".join(sorted(p.value for p in PAPEIS_VALIDOS_EM_SESSAO))},
            )
        return papel

    @property
    def eh_humano(self) -> bool:
        """Indica se a sessão foi aberta sob a identidade humana."""
        return self.papel == PapelAutor.HUMANO


class PoliticaIdentidadeMCP:
    """Decide, sem efeitos colaterais, se a identidade da sessão pode usar a ferramenta."""

    def autorizar(self, nome_ferramenta: str, identidade: IdentidadeSessaoMCP) -> ResultadoAutorizacao:
        """Consulta pura de autorização da ferramenta para a identidade corrente."""
        if nome_ferramenta not in FERRAMENTAS_EXCLUSIVAS_DO_HUMANO:
            return ResultadoAutorizacao.permitido()
        if identidade.eh_humano:
            return ResultadoAutorizacao.permitido()
        return ResultadoAutorizacao.negado(
            f"A ferramenta '{nome_ferramenta}' exige uma sessao humana. "
            f"Esta sessao foi aberta como '{identidade.papel.value}'. "
            "Use 'abrir_questao' para escalar a decisao ao humano."
        )
