"""Avaliador de falhas na taxonomia MAST (Cemri et al., 2025).

O classificador decidia por substring da mensagem em português — "ciclo",
"permissão", "orçamento". Funcionava e quebraria na primeira reescrita de texto,
sem nada avisando. Agora quem recusa declara o modo (`core/falhas.py`), e este
módulo só traduz o modo para a macro-categoria. A escada textual sobrevive como
rede para resultados montados fora dos portões. Ver achado A-13.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from graphow.core.falhas import CATEGORIA_POR_MODO, CategoriaFalhaMAST, ModoFalhaMAST, categoria_de
from graphow.kernel.patch_models import ResultadoValidacao

__all__ = [
    "CATEGORIA_POR_MODO",
    "CategoriaFalhaMAST",
    "DiagnosticoFalha",
    "MASTEvaluator",
    "ModoFalhaMAST",
]

# Rede para vereditos montados fora dos portões, que não declaram modo. Cada par
# é (fragmento da mensagem, modo). A ordem importa: a primeira ocorrência vence.
PISTAS_TEXTUAIS: tuple[tuple[str, ModoFalhaMAST], ...] = (
    ("papel", ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL),
    ("permissão", ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL),
    ("protegida", ModoFalhaMAST.PROTOTYPE_POLLUTION),
    ("prototype", ModoFalhaMAST.PROTOTYPE_POLLUTION),
    ("ciclo", ModoFalhaMAST.CICLO_DEPENDENCIA),
    ("bloqueante", ModoFalhaMAST.FECHAMENTO_COM_BLOQUEIO_PENDENTE),
    ("orçamento", ModoFalhaMAST.ESTOURO_ORCAMENTO_TOKENS),
    ("token", ModoFalhaMAST.ESTOURO_ORCAMENTO_TOKENS),
    ("bloqueado para escrita", ModoFalhaMAST.CONFLITO_CONCORRENCIA_LOCK),
)

PORTAO_DESCONHECIDO: str = "Desconhecido"


@dataclass(frozen=True)
class DiagnosticoFalha:
    """Diagnóstico estruturado para análise de qualidade e auto-recuperação."""

    categoria: CategoriaFalhaMAST
    modo: ModoFalhaMAST
    mensagem: str
    portao: str
    detalhes: Mapping[str, str] = field(default_factory=dict)


class MASTEvaluator:
    """Traduz a recusa de um portão em diagnóstico da taxonomia MAST."""

    @classmethod
    def classificar_resultado(cls, resultado: ResultadoValidacao) -> DiagnosticoFalha | None:
        """Mapeia o resultado de validação de um patch para a taxonomia MAST."""
        if resultado.aprovado:
            return None
        modo = resultado.modo or cls._inferir_modo(resultado.mensagem_erro or "")
        return DiagnosticoFalha(
            categoria=categoria_de(modo),
            modo=modo,
            mensagem=resultado.mensagem_erro or "",
            portao=resultado.portao_falha or PORTAO_DESCONHECIDO,
            detalhes=resultado.contexto_detalhado,
        )

    @classmethod
    def _inferir_modo(cls, mensagem: str) -> ModoFalhaMAST:
        """Última tentativa, por texto, quando o veredito não declarou o modo."""
        minuscula = mensagem.lower()
        encontrados = [modo for pista, modo in PISTAS_TEXTUAIS if pista in minuscula]
        return encontrados[0] if encontrados else ModoFalhaMAST.OUTRO
