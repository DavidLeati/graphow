"""A spec de um Goal que o gerente gravou, montada dos nós ligados a ele com o texto inteiro.

A vista do agente mostrava do Goal só o rótulo, e as Decisions chegavam ao
executor reduzidas a um título: os agentes compensavam com `expandir_no` e
descrições de Task que copiavam as decisões. Aqui a spec sai inteira, uma vez:
a descrição e o que ficou em aberto, cada critério de aceite numerado C1..Cn
com o id do nó e o tipo de verificação, a fronteira item a item, as outras
restrições e cada Decision vigente (a substituída fica de fora) numerada
D1..Dn, com o texto inteiro, o motivo e o trecho da Evidence que a sustenta.

O critério de aceite é o nó Criterio que o gerente grava (ontologia 1.7.0); o
Goal de antes dele traz a Constraint `criterio_aceite`, que segue valendo. O
texto e o tipo de verificação de cada critério do humano vão também no
`SpecDoGoal`: o orquestrador os grava como o humano os escreveu, e não pede ao
planejador que os extraia de novo.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from graphow.core import aceite as a
from graphow.core.escopo import CAMPO_TIPO_CONSTRAINT, CONSTRAINT_CRITERIO_ACEITE, CONSTRAINT_FRONTEIRA
from graphow.core.models import NoGrafo
from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador.saidas import Criterio, IdsFixados
from graphow.projection.graph_view import GrafoView


@dataclass(frozen=True)
class SpecDoGoal:
    """O texto da spec, os ids que o plano tem de manter e o nó de cada um."""

    texto: str
    fixados: IdsFixados = field(default_factory=IdsFixados)
    nos_fixados: dict[str, str] = field(default_factory=dict)
    criterios_do_humano: tuple[Criterio, ...] = ()


def montar_spec_do_goal(view: GrafoView, id_goal: str) -> SpecDoGoal:
    """A spec do Goal a partir do grafo, com os critérios e as decisões numerados."""
    goal = view.obter_no(id_goal)
    if goal is None:
        return SpecDoGoal("")
    restricoes = _ordenados(view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(id_goal, TipoAresta.ESCOPA))
    criterios = [no for no in restricoes if no.tipo == TipoNo.CRITERIO or _tipo_da_restricao(no) == CONSTRAINT_CRITERIO_ACEITE]
    decisoes = [no for no in _ordenados(view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(id_goal, TipoAresta.ORIENTA))
                if no.tipo == TipoNo.DECISION and not view.obter_arestas_entrada(no.id, TipoAresta.SUBSTITUI)]
    codigos = {**{f"C{i}": no.id for i, no in enumerate(criterios, 1)}, **{f"D{i}": no.id for i, no in enumerate(decisoes, 1)}}
    partes = [
        f"# {goal.rotulo}",
        str(goal.obter_propriedade("descricao") or ""),
        _secao("Criterios de aceite (definidos pelo humano: mantenha o id e o texto)",
               [f"- C{i} ({no.id}, {_verificacao(no)}): {_texto(no)}" for i, no in enumerate(criterios, 1)]),
        _secao("Fora do escopo", _itens_da_fronteira(restricoes)),
        _secao("Restricoes", [f"- {no.rotulo}" for no in restricoes if no.tipo == TipoNo.CONSTRAINT and not _tipo_da_restricao(no)]),
        _secao("Decisoes do humano (mantenha o id)", [_linha_da_decisao(view, i, no) for i, no in enumerate(decisoes, 1)]),
        _secao("Em aberto", [str(goal.obter_propriedade("em_aberto") or "")]),
    ]
    texto = "\n\n".join(parte for parte in partes if parte.strip()) + "\n"
    fixados = IdsFixados(criterios=tuple(f"C{i}" for i in range(1, len(criterios) + 1)),
                         decisoes=tuple(f"D{i}" for i in range(1, len(decisoes) + 1)))
    do_humano = tuple(Criterio(f"C{i}", _texto(no), _verificacao(no)) for i, no in enumerate(criterios, 1))
    return SpecDoGoal(texto, fixados, codigos, do_humano)


def _texto(no: NoGrafo) -> str:
    """O texto inteiro do critério ou da decisão: a propriedade `texto`, ou o rótulo do nó antigo."""
    return str(no.obter_propriedade(a.CAMPO_TEXTO) or no.rotulo)


def _verificacao(no: NoGrafo) -> str:
    """Como o critério se prova; o critério sem o tipo declarado se prova por teste."""
    valor = str(no.obter_propriedade(a.CAMPO_VERIFICACAO) or "")
    return valor if valor in a.VERIFICACOES_DE_CRITERIO else a.VERIFICACAO_POR_TESTE


def _ordenados(nos: Iterable[NoGrafo | None]) -> list[NoGrafo]:
    """Os nós existentes na ordem em que nasceram no log."""
    return sorted((no for no in nos if no is not None), key=lambda no: (no.ordem.seq_criacao, no.id))


def _tipo_da_restricao(no: NoGrafo) -> str:
    """O tipo da Constraint (critério, fronteira) ou vazio para a restrição comum."""
    return str(no.obter_propriedade(CAMPO_TIPO_CONSTRAINT) or "") if no.tipo == TipoNo.CONSTRAINT else "outro"


def _itens_da_fronteira(restricoes: Iterable[NoGrafo]) -> list[str]:
    """Os itens da Constraint `fronteira`, um por linha."""
    linhas: list[str] = []
    for no in restricoes:
        itens = no.obter_propriedade("itens") if _tipo_da_restricao(no) == CONSTRAINT_FRONTEIRA else None
        linhas.extend(f"- {item}" for item in itens or [] if isinstance(itens, list))
    return linhas


def _linha_da_decisao(view: GrafoView, numero: int, no: NoGrafo) -> str:
    """A decisão com o motivo e os trechos que a sustentam."""
    linha = f"- D{numero} ({no.id}): {_texto(no)}"
    motivo = str(no.obter_propriedade("motivo") or "")
    if motivo:
        linha += f" Motivo: {motivo}"
    for aresta in view.obter_arestas_entrada(no.id, TipoAresta.JUSTIFICA):
        evidencia = view.obter_no(aresta.origem_id)
        if evidencia is not None and evidencia.obter_propriedade("trecho"):
            linha += f"\n  Evidencia ({evidencia.obter_propriedade('fonte') or evidencia.obter_propriedade('arquivo') or ''}): " \
                     f"\"{evidencia.obter_propriedade('trecho')}\""
    return linha


def _secao(titulo: str, linhas: list[str]) -> str:
    """Uma seção da spec; vazia quando não há linha."""
    conteudo = [linha for linha in linhas if linha.strip()]
    return f"## {titulo}\n" + "\n".join(conteudo) if conteudo else ""
