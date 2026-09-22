"""O Aprendizado como o grafo o lê: alcance, origem, substituição e a linha que a vista carrega.

Um Aprendizado não tem status gravado. Promovido é o que tem alcance, por
`vale_para` ou pela marca global; vigente é o promovido que nenhum promovido
substituiu; contradito é o que uma Evidence nova aponta. Tudo vem das arestas,
e a linha da vista diz isso de uma vez: afirmação, proveniência, como aplicar,
alcance, quem substitui, origem e marcas. A linha curta leva só a afirmação, a
proveniência, quem substitui e as marcas: é a forma do que alcança o alvo sem
casar com o texto dele, e `expandir_no` traz o resto.

A vista carrega só o vigente. O aprendizado substituído por um promovido fica
no grafo, no painel e no acervo, marcado, e a linha do substituto diz quem ele
absorveu. Enquanto o substituto não é promovido, o antigo segue valendo:
substituir é propor, promover é o humano aceitar. A seção que reúne os
aprendizados que alcançam um alvo fica em `context/aprendizados_aplicaveis.py`.
"""

from graphow.context.secoes import formatar_no_em_linha
from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

CAMPO_ALCANCE: str = "alcance"
ALCANCE_GLOBAL: str = "global"
CAMPO_COMO_APLICAR: str = "como_aplicar"
CAMPO_VALIDO_ATE: str = "valido_ate"
MARCA_DE_SUBSTITUIDO: str = "SUBSTITUIDO"
MARCA_DE_CONTRADITO: str = "CONTRADITO"
MARCA_DE_SUBSTITUTO_PENDENTE: str = "SUBSTITUTO PENDENTE"


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
    partes = [formatar_no_em_linha(no)]
    como_aplicar = str(no.obter_propriedade(CAMPO_COMO_APLICAR, "")).strip()
    if como_aplicar:
        partes.append(f"-> como aplicar: {como_aplicar}")
    alcances = alcances_de(no, view)
    if alcances:
        partes.append(f"[vale_para {', '.join(alcances)}]")
    partes.extend(_marca_de_substitutos(no.id, view))
    origens = origens_de(no, view)
    if origens:
        partes.append(f"[origem: {', '.join(origens)}]")
    partes.extend(_marcas_de_revisao(no.id, view))
    return " ".join(partes)


def formatar_aprendizado_curto(no: NoGrafo, view: GrafoView) -> str:
    """Só a afirmação, a proveniência, quem substitui e as marcas: `expandir_no` traz o resto."""
    return " ".join((formatar_no_em_linha(no), *_marca_de_substitutos(no.id, view), *_marcas_de_revisao(no.id, view)))


def _marca_de_substitutos(id_no: str, view: GrafoView) -> tuple[str, ...]:
    """Quem este aprendizado absorveu, quando é o consolidado de outros."""
    absorvidos = substituidos_por(id_no, view)
    return (f"[substitui {', '.join(absorvidos)}]",) if absorvidos else ()


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
