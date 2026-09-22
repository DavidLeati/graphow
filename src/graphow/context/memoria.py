"""Seção de memória: os aprendizados que alcançam o alvo, por herança, por léxico ou por índice.

Nada condensado voltava ao agente: conhecimento antigo só reaparecia por descida
na hierarquia ou por busca textual, e o agente precisava saber a palavra para
reencontrar o que aprendeu. A seção monta a memória em três passos, do mais
barato ao mais caro. A herança pela hierarquia resolve o mesmo projeto ou setor
sem busca nenhuma, como as restrições herdadas. O casamento lexical cobre o
aprendizado promovido a outro lugar cujo texto casa com o alvo. O índice
semântico é injetável e nulo por padrão: sem configurar, não custa nada e não
traz dependência.

A vista carrega só o vigente. O aprendizado substituído por um promovido fica
no grafo, no painel e no acervo, marcado, e a linha do substituto diz quem ele
absorveu. Enquanto o substituto não é promovido, o antigo segue valendo:
substituir é propor, promover é o humano aceitar.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.context.secoes import (
    GrupoDeLinhas,
    PrioridadeRetencao,
    SecaoContexto,
    anotar_ordem,
    anotar_proveniencia,
)
from graphow.core.models import NoGrafo
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import contar_palavras_casadas, palavras_significativas

TITULO_APRENDIZADOS: str = "Aprendizados Aplicaveis"
ORDEM_DE_EXIBICAO_DOS_APRENDIZADOS: int = 2
CAMPO_ALCANCE: str = "alcance"
ALCANCE_GLOBAL: str = "global"
CAMPO_COMO_APLICAR: str = "como_aplicar"
CAMPO_VALIDO_ATE: str = "valido_ate"
CAMPO_DESCRICAO: str = "descricao"
PROFUNDIDADE_DA_HERANCA: int = 8
LIMITE_DE_CASAMENTOS_LEXICAIS: int = 5
MECANISMO_HERANCA: str = "heranca"
MECANISMO_LEXICO: str = "lexico"
MECANISMO_SEMANTICO: str = "semantico"
MARCA_DE_SUBSTITUIDO: str = "SUBSTITUIDO"
MARCA_DE_CONTRADITO: str = "CONTRADITO"
MARCA_DE_SUBSTITUTO_PENDENTE: str = "SUBSTITUTO PENDENTE"


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


def aprendizados_promovidos(view: GrafoView, instante: str) -> tuple[NoGrafo, ...]:
    """Aprendizados com alcance declarado e ainda válidos, em ordem estável."""
    candidatos = view.listar_nos_por_tipo(TipoNo.APRENDIZADO)
    promovidos = [no for no in candidatos if _tem_alcance(no, view) and not _expirou(no, instante)]
    return tuple(sorted(promovidos, key=lambda no: (no.ordem.seq_criacao, no.id)))


def aprendizados_vigentes(view: GrafoView, instante: str) -> tuple[NoGrafo, ...]:
    """Os promovidos que nenhum promovido substituiu: o que a vista carrega."""
    return tuple(no for no in aprendizados_promovidos(view, instante) if substituto_promovido(no.id, view) is None)


def _tem_alcance(no: NoGrafo, view: GrafoView) -> bool:
    """Promovido é o que vale para um Projeto, um Setor ou para tudo."""
    if no.obter_propriedade(CAMPO_ALCANCE) == ALCANCE_GLOBAL:
        return True
    return bool(view.obter_arestas_saida(no.id, TipoAresta.VALE_PARA))


def _expirou(no: NoGrafo, instante: str) -> bool:
    """`valido_ate` passa a ser lido: um aprendizado vencido não volta à vista."""
    limite = no.obter_propriedade(CAMPO_VALIDO_ATE)
    return isinstance(limite, str) and bool(limite) and limite < instante


def alcances_de(no: NoGrafo, view: GrafoView) -> tuple[str, ...]:
    """Onde o aprendizado vale: a marca global e os destinos de `vale_para`."""
    destinos = sorted(aresta.destino_id for aresta in view.obter_arestas_saida(no.id, TipoAresta.VALE_PARA))
    if no.obter_propriedade(CAMPO_ALCANCE) == ALCANCE_GLOBAL:
        return (ALCANCE_GLOBAL, *destinos)
    return tuple(destinos)


def ja_vale_para(id_aprendizado: str, id_alvo: str, view: GrafoView) -> bool:
    """Diz se o aprendizado já tem `vale_para` chegando no alvo.

    Promover de novo para o mesmo alvo não muda nada, e recriar a aresta seria
    recusado pelo kernel: `add` só cria id novo.
    """
    arestas = view.obter_arestas_saida(id_aprendizado, TipoAresta.VALE_PARA)
    return any(aresta.destino_id == id_alvo for aresta in arestas)


def origens_de(no: NoGrafo, view: GrafoView) -> tuple[str, ...]:
    """De onde o aprendizado saiu: os destinos das arestas `deriva_de`."""
    return tuple(sorted(aresta.destino_id for aresta in view.obter_arestas_saida(no.id, TipoAresta.DERIVA_DE)))


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


def identificar_substituto(id_aprendizado: str, view: GrafoView) -> str | None:
    """O primeiro Aprendizado que substituiu o informado, promovido ou não, se houver."""
    substitutos = substitutos_de(id_aprendizado, view)
    return substitutos[0] if substitutos else None


def substitutos_de(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]:
    """Os Aprendizados de onde parte `substitui` chegando neste, em ordem estável."""
    entradas = view.obter_arestas_entrada(id_aprendizado, TipoAresta.SUBSTITUI)
    return tuple(id_no for id_no in sorted(aresta.origem_id for aresta in entradas) if _eh_aprendizado(id_no, view))


def substituidos_por(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]:
    """Os Aprendizados que este substitui: a linha do consolidado diz quem ele absorveu."""
    saidas = view.obter_arestas_saida(id_aprendizado, TipoAresta.SUBSTITUI)
    return tuple(id_no for id_no in sorted(aresta.destino_id for aresta in saidas) if _eh_aprendizado(id_no, view))


def substituto_promovido(id_aprendizado: str, view: GrafoView) -> str | None:
    """O substituto que já tem alcance, se houver: só ele tira o antigo da vista.

    Um agente pode escrever o substituto; quem lhe dá alcance é o humano. Até
    lá o antigo segue valendo, com a marca de que há um substituto à espera.
    """
    for id_no in substitutos_de(id_aprendizado, view):
        no = view.obter_no(id_no)
        if no is not None and _tem_alcance(no, view):
            return id_no
    return None


def _eh_aprendizado(id_no: str, view: GrafoView) -> bool:
    """Diz se o id nomeia um Aprendizado presente na projeção."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == TipoNo.APRENDIZADO


def identificar_contradicoes(id_aprendizado: str, view: GrafoView) -> tuple[str, ...]:
    """Evidences que contradizem o aprendizado: sinal de que ele precisa de revisão."""
    entradas = view.obter_arestas_entrada(id_aprendizado, TipoAresta.CONTRADIZ)
    return tuple(sorted(aresta.origem_id for aresta in entradas))


def formatar_aprendizado(no: NoGrafo, view: GrafoView) -> str:
    """Uma linha: afirmação, proveniência, como aplicar, alcance, quem substitui, origem e marcas."""
    partes = [f"- [{no.id}] {no.rotulo}{anotar_ordem(no)}{anotar_proveniencia(no)}"]
    como_aplicar = str(no.obter_propriedade(CAMPO_COMO_APLICAR, "")).strip()
    if como_aplicar:
        partes.append(f"-> como aplicar: {como_aplicar}")
    alcances = alcances_de(no, view)
    if alcances:
        partes.append(f"[vale_para {', '.join(alcances)}]")
    absorvidos = substituidos_por(no.id, view)
    if absorvidos:
        partes.append(f"[substitui {', '.join(absorvidos)}]")
    origens = origens_de(no, view)
    if origens:
        partes.append(f"[origem: {', '.join(origens)}]")
    partes.extend(_marcas_de_revisao(no.id, view))
    return " ".join(partes)


def _marcas_de_revisao(id_no: str, view: GrafoView) -> tuple[str, ...]:
    """Substituído, com substituto à espera de promoção, ou contradito: marcado, nunca apagado."""
    marcas: list[str] = [*_marca_de_substituicao(id_no, view)]
    contradicoes = identificar_contradicoes(id_no, view)
    if contradicoes:
        marcas.append(f"[{MARCA_DE_CONTRADITO} por {', '.join(contradicoes)}: precisa de revisao]")
    return tuple(marcas)


def _marca_de_substituicao(id_no: str, view: GrafoView) -> tuple[str, ...]:
    """Substituído por promovido diz por quem e não segue; o antigo ainda em vigor diz quem o espera."""
    promovido = substituto_promovido(id_no, view)
    if promovido is not None:
        return (f"[{MARCA_DE_SUBSTITUIDO} por {promovido}: nao siga]",)
    pendentes = substitutos_de(id_no, view)
    if pendentes:
        return (f"[{MARCA_DE_SUBSTITUTO_PENDENTE}: {', '.join(pendentes)} aguarda promocao, siga este ate la]",)
    return ()
