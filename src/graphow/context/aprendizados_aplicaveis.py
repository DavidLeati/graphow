"""A seção Aprendizados Aplicaveis: os aprendizados que alcançam o alvo, por herança, por léxico ou por índice.

Nada condensado voltava ao agente: conhecimento antigo só reaparecia por descida
na hierarquia ou por busca textual, e o agente precisava saber a palavra para
reencontrar o que aprendeu. A seção monta a memória em três passos, do mais
barato ao mais caro. A herança pela hierarquia resolve o mesmo projeto ou setor
sem busca nenhuma, como as restrições herdadas. O casamento lexical cobre o
aprendizado promovido a outro lugar cujo texto casa com o alvo. O índice
semântico é injetável e nulo por padrão: sem configurar, não custa nada e não
traz dependência. A leitura de cada Aprendizado (alcance, origem, substituição
e a linha que a vista carrega) fica em `context/memoria.py`.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.context.memoria import ALCANCE_GLOBAL, alcances_de, aprendizados_vigentes, formatar_aprendizado
from graphow.context.secoes import GrupoDeLinhas, PrioridadeRetencao, SecaoContexto
from graphow.core.models import NoGrafo
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import contar_palavras_casadas, palavras_significativas

TITULO_APRENDIZADOS: str = "Aprendizados Aplicaveis"
ORDEM_DE_EXIBICAO_DOS_APRENDIZADOS: int = 2
CAMPO_DESCRICAO: str = "descricao"
PROFUNDIDADE_DA_HERANCA: int = 8
LIMITE_DE_CASAMENTOS_LEXICAIS: int = 5
MECANISMO_HERANCA: str = "heranca"
MECANISMO_LEXICO: str = "lexico"
MECANISMO_SEMANTICO: str = "semantico"


class IndiceSemantico(ABC):
    """Recuperação por sentido, para quando herança e léxico não atravessam projetos.

    É opcional e injetável, no padrão da telemetria com destino nulo. O contrato
    é pequeno de propósito: recebe o texto do alvo e os candidatos, e devolve os
    identificadores que julga aplicáveis, do mais ao menos provável.
    """

    @abstractmethod
    def sugerir(self, texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]:
        """Identificadores dos candidatos aplicáveis ao texto, em ordem."""
        raise NotImplementedError

    @abstractmethod
    def descrever(self) -> str:
        """Nome do índice em uso, para o relatório de avaliação declarar."""
        raise NotImplementedError


class IndiceSemanticoNulo(IndiceSemantico):
    """O padrão: não sugere nada e não custa nada."""

    def sugerir(self, texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]:
        """Nenhuma sugestão."""
        return ()

    def descrever(self) -> str:
        """Nome do índice nulo."""
        return "nulo"


@dataclass(frozen=True)
class PedidoDeMemoria:
    """O que a seção precisa: o alvo, a projeção, o índice e o instante de referência."""

    alvo: NoGrafo
    view: GrafoView
    indice: IndiceSemantico = field(default_factory=IndiceSemanticoNulo)
    agora: str = ""

    @property
    def instante(self) -> str:
        """Instante ISO contra o qual `valido_ate` é comparado; o relógio, se não vier."""
        return self.agora or datetime.now(timezone.utc).isoformat()

    @property
    def texto_do_alvo(self) -> str:
        """Título e descrição do alvo, que é o que o léxico e o índice comparam."""
        descricao = str(self.alvo.obter_propriedade(CAMPO_DESCRICAO, ""))
        return f"{self.alvo.rotulo} {descricao}".strip()


@dataclass(frozen=True)
class AprendizadoAplicavel:
    """Um aprendizado que alcançou o alvo, com o mecanismo pelo qual chegou."""

    no: NoGrafo
    mecanismo: str
    alcance: str


def montar_secao_de_aprendizados(pedido: PedidoDeMemoria) -> SecaoContexto:
    """Monta a seção nos três passos, agrupada por mecanismo para encolher sob orçamento."""
    vigentes = aprendizados_vigentes(pedido.view, pedido.instante)
    herdados = _por_heranca(pedido, vigentes)
    restantes = _excluir(vigentes, herdados)
    lexicais = _por_lexico(pedido, restantes)
    semanticos = _por_indice(pedido, _excluir(restantes, lexicais))
    candidatos = (
        _grupo("Aprendizado herdado", herdados, pedido.view),
        _grupo("Aprendizado por casamento lexical", lexicais, pedido.view),
        _grupo("Aprendizado por indice semantico", semanticos, pedido.view),
    )
    grupos = tuple(grupo for grupo in candidatos if grupo.linhas)
    return SecaoContexto(
        titulo=_titulo(herdados),
        linhas=tuple(linha for grupo in grupos for linha in grupo.linhas),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DOS_APRENDIZADOS,
        prioridade_retencao=PrioridadeRetencao.MEMORIA,
        ids_incluidos=tuple(id_no for grupo in grupos for id_no in grupo.ids),
        grupos=grupos,
    )


def _excluir(nos: Sequence[NoGrafo], ja_incluidos: Sequence[AprendizadoAplicavel]) -> tuple[NoGrafo, ...]:
    """Os nós que nenhum passo anterior trouxe."""
    incluidos = {item.no.id for item in ja_incluidos}
    return tuple(no for no in nos if no.id not in incluidos)


def _titulo(herdados: Sequence[AprendizadoAplicavel]) -> str:
    """O título nomeia de onde a herança veio, para o agente saber o alcance."""
    alcances = sorted({item.alcance for item in herdados})
    if not alcances:
        return TITULO_APRENDIZADOS
    return f"{TITULO_APRENDIZADOS} (herdados de {', '.join(alcances)})"


def _por_heranca(pedido: PedidoDeMemoria, promovidos: Sequence[NoGrafo]) -> tuple[AprendizadoAplicavel, ...]:
    """Aprendizados que valem para o alvo ou para um ancestral dele por contenção."""
    ancestrais = _ancestrais_por_contencao(pedido.alvo, pedido.view)
    herdados: list[AprendizadoAplicavel] = []
    for no in promovidos:
        alcance = _alcance_que_cobre(no, ancestrais, pedido.view)
        if alcance is not None:
            herdados.append(AprendizadoAplicavel(no=no, mecanismo=MECANISMO_HERANCA, alcance=alcance))
    return tuple(herdados)


def _alcance_que_cobre(no: NoGrafo, ancestrais: frozenset[str], view: GrafoView) -> str | None:
    """O primeiro alcance do aprendizado que contém o alvo, ou None."""
    for alcance in alcances_de(no, view):
        if alcance == ALCANCE_GLOBAL or alcance in ancestrais:
            return alcance
    return None


def _ancestrais_por_contencao(alvo: NoGrafo, view: GrafoView) -> frozenset[str]:
    """O alvo e tudo que o contém, subindo `contem`, `produz` e `decompoe`."""
    pedido = PedidoExploracao(
        id_alvo=alvo.id,
        tipos_de_aresta=ARESTAS_DE_CONTENCAO,
        direcao=DirecaoTravessia.ENTRADA,
        saltos_maximos=PROFUNDIDADE_DA_HERANCA,
    )
    ancestrais = ExploradorSubgrafo(view).coletar_alcancaveis(pedido)
    return frozenset({alvo.id} | {no.id for no in ancestrais})


def _por_lexico(pedido: PedidoDeMemoria, candidatos: Sequence[NoGrafo]) -> tuple[AprendizadoAplicavel, ...]:
    """Aprendizados cujo texto casa com o do alvo, os mais casados primeiro."""
    palavras = palavras_significativas(pedido.texto_do_alvo)
    if not palavras:
        return ()
    pontuados = [(contar_palavras_casadas(no, palavras), no) for no in candidatos]
    casados = sorted(
        (par for par in pontuados if par[0] > 0), key=lambda par: (-par[0], par[1].id)
    )
    return tuple(
        AprendizadoAplicavel(no=no, mecanismo=MECANISMO_LEXICO, alcance=MECANISMO_LEXICO)
        for _, no in casados[:LIMITE_DE_CASAMENTOS_LEXICAIS]
    )


def _por_indice(pedido: PedidoDeMemoria, candidatos: Sequence[NoGrafo]) -> tuple[AprendizadoAplicavel, ...]:
    """O que o índice semântico sugerir entre os que herança e léxico não alcançaram."""
    if not candidatos:
        return ()
    por_id = {no.id: no for no in candidatos}
    sugeridos = pedido.indice.sugerir(pedido.texto_do_alvo, candidatos)
    return tuple(
        AprendizadoAplicavel(no=por_id[id_no], mecanismo=MECANISMO_SEMANTICO, alcance=MECANISMO_SEMANTICO)
        for id_no in dict.fromkeys(sugeridos)
        if id_no in por_id
    )


def _grupo(rotulo: str, itens: Sequence[AprendizadoAplicavel], view: GrafoView) -> GrupoDeLinhas:
    """Um grupo cortável por mecanismo, em ordem estável de identificador."""
    ordenados = sorted(itens, key=lambda item: item.no.id)
    return GrupoDeLinhas(
        rotulo=rotulo,
        linhas=tuple(formatar_aprendizado(item.no, view) for item in ordenados),
        ids=tuple(item.no.id for item in ordenados),
    )
