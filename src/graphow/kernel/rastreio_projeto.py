"""Rastreio do Projeto ancestral de um nó, resistente a ciclos na hierarquia.

Apenas arestas `depende_de` são garantidamente acíclicas pelo InvariantGate.
`contem`, `substitui` e `deriva_de` podem formar ciclos, então a subida precisa
de controle de visitados. Ver auditoria F-10.
"""

from collections.abc import Sequence
from typing import Any

from graphow.core.models import ArestaGrafo, GrafoEstado, MetadadosTemporais, NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch

PROFUNDIDADE_MAXIMA_DE_SUBIDA: int = 64
SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2


class RastreadorProjetoAncestral:
    """Encontra o Projeto que contém um nó, percorrendo as arestas de entrada."""

    def rastrear(self, id_no: str, estado: GrafoEstado) -> str | None:
        """Consulta iterativa que devolve o identificador do Projeto ancestral, se existir."""
        no_inicial = estado.nos.get(id_no)
        if no_inicial is None:
            return None
        if no_inicial.tipo == TipoNo.PROJETO:
            return no_inicial.id
        return self._subir_ate_projeto(id_no, estado)

    def _subir_ate_projeto(self, id_no: str, estado: GrafoEstado) -> str | None:
        """Percorre em largura os ancestrais, abandonando ciclos e caminhos longos."""
        visitados: set[str] = {id_no}
        fronteira: list[str] = [id_no]
        for _ in range(PROFUNDIDADE_MAXIMA_DE_SUBIDA):
            if not fronteira:
                return None
            projeto_encontrado, proxima_fronteira = self._expandir_nivel(fronteira, estado, visitados)
            if projeto_encontrado is not None:
                return projeto_encontrado
            fronteira = proxima_fronteira
        return None

    def _expandir_nivel(
        self,
        fronteira: list[str],
        estado: GrafoEstado,
        visitados: set[str],
    ) -> tuple[str | None, list[str]]:
        """Expande um nível de ancestrais e sinaliza o primeiro Projeto alcançado."""
        proxima_fronteira: list[str] = []
        alvos = frozenset(fronteira)
        for aresta in self._arestas_que_chegam(estado, alvos):
            pai = estado.nos.get(aresta.origem_id)
            if pai is None or pai.id in visitados:
                continue
            visitados.add(pai.id)
            if pai.tipo == TipoNo.PROJETO:
                return pai.id, proxima_fronteira
            proxima_fronteira.append(pai.id)
        return None, proxima_fronteira

    def _arestas_que_chegam(
        self,
        estado: GrafoEstado,
        destinos: frozenset[str],
    ) -> tuple[ArestaGrafo, ...]:
        """Seleciona as arestas cujo destino pertence ao conjunto informado."""
        return tuple(aresta for aresta in estado.arestas.values() if aresta.destino_id in destinos)


def projetar_lote(operacoes: Sequence[ItemPatch], estado: GrafoEstado) -> GrafoEstado:
    """Antecipa o estado como se o lote já estivesse aplicado, só para consulta.

    O nível de autonomia era lido de `origem_id`, `id_sessao` ou `id` dentro do
    valor do nó — chaves que nenhuma ferramenta MCP escreve, o que tornava a
    autonomia ilimitada inerte na prática. A âncora correta é a aresta `contem`
    ou `produz` que vem no mesmo lote, e ela só é visível se o lote for projetado
    antes da consulta. Ver achado A-05.
    """
    nos = dict(estado.nos)
    arestas = dict(estado.arestas)
    for item in operacoes:
        _aplicar_criacao_em_antevisao(item, nos, arestas)
    return GrafoEstado(nos=nos, arestas=arestas, versao_log=estado.versao_log)


def _aplicar_criacao_em_antevisao(
    item: ItemPatch,
    nos: dict[str, NoGrafo],
    arestas: dict[str, ArestaGrafo],
) -> None:
    """Insere na antevisão o nó ou a aresta que a operação de criação declara."""
    segmentos = [seg for seg in item.path.split("/") if seg]
    if item.op != OperacaoPatch.ADD or len(segmentos) != SEGMENTOS_DE_ELEMENTO_INTEIRO:
        return
    if not isinstance(item.value, dict):
        return
    if segmentos[0] == "nos":
        no = _converter_no_declarado(segmentos[1], item.value)
        _registrar_se_valido(nos, segmentos[1], no)
        return
    if segmentos[0] == "arestas":
        aresta = _converter_aresta_declarada(segmentos[1], item.value)
        _registrar_se_valido(arestas, segmentos[1], aresta)


def _registrar_se_valido(destino: dict[str, Any], chave: str, elemento: Any) -> None:
    """Grava o elemento apenas quando a conversão reconheceu a forma declarada."""
    if elemento is not None:
        destino[chave] = elemento


def _converter_no_declarado(id_no: str, valor: dict[str, Any]) -> NoGrafo | None:
    """Constrói o nó da antevisão, ignorando formas que o SchemaGate recusará."""
    try:
        tipo = TipoNo(valor["tipo"])
    except (KeyError, ValueError):
        return None
    return NoGrafo(
        id=id_no,
        tipo=tipo,
        rotulo=str(valor.get("rotulo", "")),
        propriedades=dict(valor.get("propriedades", {})),
        metadados=MetadadosTemporais.agora(),
    )


def _converter_aresta_declarada(id_aresta: str, valor: dict[str, Any]) -> ArestaGrafo | None:
    """Constrói a aresta da antevisão, ignorando formas incompletas ou inválidas."""
    try:
        tipo = TipoAresta(valor["tipo"])
        origem = str(valor["origem_id"])
        destino = str(valor["destino_id"])
    except (KeyError, ValueError):
        return None
    return ArestaGrafo(
        id=id_aresta,
        origem_id=origem,
        destino_id=destino,
        tipo=tipo,
        metadados=MetadadosTemporais.agora(),
    )
