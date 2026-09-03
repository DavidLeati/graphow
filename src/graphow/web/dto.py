"""Objetos de Transferência de Dados (DTOs) imutáveis para a interface Web do Graphow."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DadosNoVisual:
    """DTO imutável para representação de um nó no Canvas.

    A idade e a posição no log viajam juntas de propósito: o carimbo de tempo
    responde há quanto tempo o card existe, e a sequência responde se ele veio
    antes ou depois de outro — o que relógios de processos diferentes não
    conseguem decidir sozinhos.
    """

    id: str
    tipo: str
    rotulo: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    esta_bloqueado: bool = False
    lock_ativo: str | None = None
    sessao_id: str | None = None
    criado_em: str = ""
    atualizado_em: str | None = None
    seq_criacao: int = 0
    seq_atualizacao: int = 0


@dataclass(frozen=True)
class DadosArestaVisual:
    """DTO imutável para representação de uma aresta no Canvas."""

    id: str
    origem_id: str
    destino_id: str
    tipo: str
    propriedades: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DadosCanvasVisual:
    """DTO imutável contendo o estado integral do Canvas para renderização."""

    ramo_id: str
    versao_log: int
    total_nos: int
    total_arestas: int
    nos: Sequence[DadosNoVisual]
    arestas: Sequence[DadosArestaVisual]


@dataclass(frozen=True)
class RequisicaoNovoNo:
    """DTO imutável de entrada para criação de novo nó via interface.

    Autor e papel não aparecem aqui de propósito: a identidade da escrita é da
    sessão do servidor, não do corpo da requisição. Ver achado A-11.
    """

    tipo: str
    rotulo: str
    id_no: str | None = None
    sessao_id: str | None = None
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoNovaAresta:
    """DTO imutável de entrada para criação de nova aresta via interface."""

    origem_id: str
    destino_id: str
    tipo: str
    id_aresta: str | None = None
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoEdicaoNo:
    """DTO imutável de entrada para modificação de atributos de um nó."""

    id_no: str
    novas_propriedades: Mapping[str, Any]
    novo_rotulo: str | None = None
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoCriarFork:
    """DTO imutável de entrada para criação de novo ramo a partir do log."""

    novo_ramo: str
    ramo_origem: str = "main"
    evento_id_ponto_corte: str | None = None


@dataclass(frozen=True)
class RequisicaoSimularVista:
    """DTO imutável de entrada para simulação de orçamentos de tokens."""

    id_alvo: str
    papel: str = "planejador"
    orcamento_tokens: int = 1000
    ramo_id: str = "main"


@dataclass(frozen=True)
class RespostaReciboWeb:
    """DTO imutável de saída contendo recibo padronizado de mutação."""

    sucesso: bool
    mensagem: str
    versao_log: int = 0
    eventos_gerados: Sequence[str] = field(default_factory=tuple)
    diagnostico_mast: str | None = None
    modo_de_falha: str | None = None


@dataclass(frozen=True)
class RequisicaoExclusaoLote:
    """DTO imutável de entrada para exclusão em lote de nós e arestas."""

    ids_nos: Sequence[str] = field(default_factory=tuple)
    ids_arestas: Sequence[str] = field(default_factory=tuple)
    ramo_id: str = "main"


@dataclass(frozen=True)
class PosicaoNoCanvas:
    """Coordenada imutável de um nó na superfície do canvas."""

    id_no: str
    x: int
    y: int


@dataclass(frozen=True)
class RequisicaoSalvarLayout:
    """DTO imutável de entrada para persistir o arranjo visual do grafo.

    O layout vivia apenas no localStorage do navegador: num produto cujo tema é
    common ground, o arranjo que uma pessoa monta nao chegava a ninguem e sumia
    ao trocar de maquina. Ver auditoria F-11.
    """

    posicoes: tuple[PosicaoNoCanvas, ...]
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoExclusaoProjeto:
    """DTO imutável de entrada para exclusão em cascata de um projeto inteiro."""

    id_projeto: str
    ramo_id: str = "main"

