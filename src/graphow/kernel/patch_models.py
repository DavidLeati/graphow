"""Modelos imutáveis e sanitizadores para operações JSON Patch (RFC 6902)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid

from graphow.core.exceptions import ErroPatchInvalido, ErroSegurancaPatch
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import OrigemEvento, PapelAutor


class OperacaoPatch(str, Enum):
    """Operações padrão do RFC 6902."""

    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"
    MOVE = "move"
    COPY = "copy"
    TEST = "test"


@dataclass(frozen=True)
class ItemPatch:
    """Item individual de operação JSON Patch RFC 6902."""

    op: OperacaoPatch
    path: str
    value: Any = None
    from_path: str | None = None


@dataclass(frozen=True)
class DadosPropostaPatch:
    """DTO imutável para dados de criação de PropostaPatch."""

    autor: str
    papel: PapelAutor
    operacoes: Sequence[ItemPatch]
    justificativa: str = ""
    ramo_id: str = "main"
    trace_id: str | None = None
    origem: OrigemEvento | None = None


@dataclass(frozen=True)
class PropostaPatch:
    """Conjunto de operações de patch submetidas atomicamente por um autor."""

    id: str
    autor: str
    papel: PapelAutor
    operacoes: tuple[ItemPatch, ...]
    justificativa: str
    ramo_id: str = "main"
    trace_id: str | None = None
    # Declarada quando quem propõe não é nem o humano nem o harness: sem isso,
    # todo patch do motor reativo era gravado como origem "harness". Ver A-10.
    origem: OrigemEvento | None = None

    @classmethod
    def criar(cls, dados: DadosPropostaPatch) -> "PropostaPatch":
        """Fábrica para instanciação com geração de ID único a partir do DTO."""
        return cls(
            id=str(uuid.uuid4()),
            autor=dados.autor,
            papel=dados.papel,
            operacoes=tuple(dados.operacoes),
            justificativa=dados.justificativa,
            ramo_id=dados.ramo_id,
            trace_id=dados.trace_id,
            origem=dados.origem,
        )


@dataclass(frozen=True)
class ResultadoValidacao:
    """Resultado detalhado da avaliação de um patch pelos portões do kernel.

    `modo` é declarado por quem recusa. Antes o classificador MAST o adivinhava
    lendo a mensagem em português, e uma reescrita de texto o quebrava em
    silêncio. Ver achado A-13.
    """

    aprovado: bool
    mensagem_erro: str | None = None
    portao_falha: str | None = None
    contexto_detalhado: Mapping[str, str] = field(default_factory=dict)
    modo: ModoFalhaMAST | None = None

    @classmethod
    def sucesso(cls) -> "ResultadoValidacao":
        """Cria resultado de aprovação."""
        return cls(aprovado=True)

    @classmethod
    def falha(
        cls,
        mensagem: str,
        portao: str,
        contexto: Mapping[str, str] | None = None,
        *,
        modo: ModoFalhaMAST | None = None,
    ) -> "ResultadoValidacao":
        """Cria resultado de rejeição com motivo, modo declarado e contexto para LLMs."""
        return cls(
            aprovado=False,
            mensagem_erro=mensagem,
            portao_falha=portao,
            contexto_detalhado=contexto or {},
            modo=modo,
        )


class SanitizadorPatch:
    """Sanitizador estrito contra injeção de atributos e prototype pollution."""

    CHAVES_PROIBIDAS: frozenset[str] = frozenset(
        {"__proto__", "constructor", "prototype", "__class__", "__globals__", "__dict__"}
    )

    @classmethod
    def sanitizar_item(cls, item: ItemPatch) -> None:
        """Verifica se o caminho ou valores contêm propriedades proibidas."""
        cls._validar_caminho(item.path)
        if item.from_path is not None:
            cls._validar_caminho(item.from_path)
        if item.value is not None:
            cls._validar_valor_recursivo(item.value)

    @classmethod
    def _validar_caminho(cls, path: str) -> None:
        """Checa se os segmentos do path RFC 6902 são seguros."""
        if not path.startswith("/"):
            raise ErroPatchInvalido("O caminho do patch deve iniciar com '/'", {"path": path})
        segmentos: list[str] = [seg for seg in path.split("/") if seg]
        for seg in segmentos:
            if seg in cls.CHAVES_PROIBIDAS:
                raise ErroSegurancaPatch(
                    f"Acesso a propriedade protegida proibido: '{seg}'",
                    {"path": path, "segmento": seg},
                )

    @classmethod
    def _validar_valor_recursivo(cls, valor: Any) -> None:
        """Varre dicionários e listas recursivamente para barrar chaves perigosas."""
        if isinstance(valor, dict):
            cls._validar_dicionario(valor)
            return
        if not isinstance(valor, (list, tuple)):
            return
        for elemento in valor:
            cls._validar_valor_recursivo(elemento)

    @classmethod
    def _validar_dicionario(cls, dic: dict[str, Any]) -> None:
        """Valida chaves e valores de um dicionário."""
        for chave, sub_valor in dic.items():
            if chave in cls.CHAVES_PROIBIDAS:
                raise ErroSegurancaPatch(
                    f"Injeção de propriedade protegida detectada: '{chave}'",
                    {"chave": chave},
                )
            cls._validar_valor_recursivo(sub_valor)
