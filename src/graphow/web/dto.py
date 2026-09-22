"""Objetos de Transferência de Dados (DTOs) imutáveis para a interface Web do Graphow."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from graphow.projection.ambito import Ambito


@dataclass(frozen=True)
class DadosNoVisual:
    """DTO imutável para representação de um nó no Canvas.

    A idade e a posição no log viajam juntas de propósito: o carimbo de tempo
    responde há quanto tempo o card existe, e a sequência responde se ele veio
    antes ou depois de outro — o que relógios de processos diferentes não
    conseguem decidir sozinhos.

    `ambito` diz se o nó mora entre os projetos de trabalho (`projetos`) ou nas
    sessões que o hook abre (`hook`): é por ele que a árvore separa as duas raízes.
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
    resumo: Mapping[str, Any] | None = None
    ambito: str = Ambito.PROJETOS.value


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
    """DTO imutável contendo o estado do Canvas para renderização.

    `recorte` acompanha os dados porque a tela precisa dizer o que escondeu. Um
    canvas que mostra 27 de 191 nós sem explicar por quê é indistinguível de um
    canvas quebrado. `total_por_ambito` conta o grafo inteiro, qualquer que seja
    o recorte, para cada raiz da árvore mostrar o total do seu âmbito.
    """

    ramo_id: str
    versao_log: int
    total_nos: int
    total_arestas: int
    nos: Sequence[DadosNoVisual]
    arestas: Sequence[DadosArestaVisual]
    recorte: Mapping[str, Any] = field(default_factory=dict)
    total_por_ambito: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RequisicaoNovoNo:
    """DTO imutável de entrada para criação de novo nó via interface.

    Autor e papel não aparecem aqui de propósito: a identidade da escrita é da
    sessão do servidor, não do corpo da requisição.

    `sessao_id` pendura trabalho numa Sessão com `produz`; `contido_em` pendura
    um contêiner no pai com `contem`. Os dois viajam no mesmo lote que o nó.
    """

    tipo: str
    rotulo: str
    id_no: str | None = None
    sessao_id: str | None = None
    propriedades: Mapping[str, Any] = field(default_factory=dict)
    ramo_id: str = "main"
    contido_em: str | None = None


@dataclass(frozen=True)
class RequisicaoBusca:
    """DTO imutável de entrada da busca textual feita pela interface.

    A busca corre sobre o grafo inteiro do ramo, não sobre o recorte que está na
    tela: quem procura um nó não sabe em que contêiner ele mora.
    """

    termo: str
    tipos: tuple[str, ...] = ()
    limite: int = 20
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
    ao trocar de maquina.
    """

    posicoes: tuple[PosicaoNoCanvas, ...]
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoExclusaoProjeto:
    """DTO imutável de entrada para exclusão em cascata de um projeto inteiro."""

    id_projeto: str
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoRegistroDeAprendizado:
    """DTO imutável de entrada do registro de um Aprendizado pela interface.

    A origem é obrigatória por desenho: o InvariantGate recusa o lote sem
    `deriva_de`, e a tela só monta o pedido a partir de nós que existem.
    """

    afirmacao: str
    id_sessao: str
    origens: Sequence[str] = field(default_factory=tuple)
    como_aplicar: str = ""
    id_aprendizado: str | None = None
    ramo_id: str = "main"


@dataclass(frozen=True)
class RequisicaoPromocaoDeAprendizado:
    """DTO imutável de entrada da promoção: alcance por contêiner, ou global."""

    id_aprendizado: str
    id_alvo: str = ""
    eh_global: bool = False
    ramo_id: str = "main"


@dataclass(frozen=True)
class NoCitadoWeb:
    """Um nó que a memória cita: a origem de um aprendizado ou a evidência que o contradiz."""

    id: str
    tipo: str
    rotulo: str
    seq: int


@dataclass(frozen=True)
class AprendizadoWeb:
    """Um Aprendizado como o painel de memória o mostra: afirmação, origem, alcance e marcas."""

    id: str
    afirmacao: str
    como_aplicar: str
    sessao_id: str | None
    alcances: Sequence[str]
    origens: Sequence[NoCitadoWeb]
    contradicoes: Sequence[NoCitadoWeb]
    substituto: str | None
    valido_ate: str
    promovido: bool
    vigente: bool
    autor: str
    papel: str
    seq_criacao: int


@dataclass(frozen=True)
class SessaoDeMemoriaWeb:
    """Uma Sessão vista pela memória: status, fechamento e o estado da condensação."""

    id: str
    rotulo: str
    status: str
    resumo: str
    setor_id: str | None
    fechamento: Sequence[str]
    condensacao: str
    id_condensacao: str | None
    seq_criacao: int


@dataclass(frozen=True)
class RespostaMemoriaWeb:
    """DTO imutável de saída do painel de memória: os aprendizados e as sessões do ramo."""

    ramo_id: str
    versao_log: int
    aprendizados: Sequence[AprendizadoWeb]
    sessoes: Sequence[SessaoDeMemoriaWeb]
    sucesso: bool = True

