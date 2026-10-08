"""O que o histórico pré-1.5.0 não tem e a medição precisa: plano aprovado, `motivada_por` e respostas de desvio.

O log anterior à ontologia 1.5.0 não conhece `Goal.planos`, `respostas_de_desvio` nem
`motivada_por`. A avaliação os injeta numa CÓPIA do estado, nunca no corpus: o plano
é a aprovação humana sintética no `seq` em que o trabalho começou, a `motivada_por`
é a aresta `orienta` (Decision para Task) lida ao contrário, e a resposta de desvio
é a que o humano daria olhando o placar logo depois do alerta.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.types import PapelAutor, TipoAresta, TipoNo

AUTOR_SINTETICO: str = "avaliacao"
RESPOSTA_SINTETICA: str = "seguir"


class EscolhaDoMotivo(str, Enum):
    """Qual das Decisions que orientam a Task vira a `motivada_por` dela.

    A Task pré-1.5.0 é orientada por todas as Decisions aplicáveis (até 11), e a
    `motivada_por` real nomeia a que a motivou. O log não diz qual, então a escolha
    é uma hipótese e a medição a varre.
    """

    NENHUM = "nenhum"
    TODAS = "todas"
    MAIS_RECENTE = "mais_recente"
    MAIS_ANTIGA = "mais_antiga"
    MAIS_ABRANGENTE = "mais_abrangente"


@dataclass(frozen=True)
class Sobreposicao:
    """O que se injeta no Goal: o `seq` do plano humano, as respostas já dadas e como nasce a `motivada_por`."""

    seq_do_plano: int
    respostas: tuple[Mapping[str, Any], ...] = ()
    motivo: EscolhaDoMotivo = EscolhaDoMotivo.MAIS_RECENTE


def resposta_humana_sem_raiz(seq: int) -> dict[str, Any]:
    """A resposta de desvio do humano ao Goal inteiro (sem raiz), que zera K e M."""
    return {
        "seq": seq,
        "respondido_por": AUTOR_SINTETICO,
        "papel": PapelAutor.HUMANO.value,
        "raiz": None,
        "resposta": RESPOSTA_SINTETICA,
    }


def sobrepor(estado: GrafoEstado, id_goal: str, sobreposicao: Sobreposicao) -> GrafoEstado:
    """Cópia do estado com o plano sintético no Goal e, quando pedido, a `motivada_por` pelo `orienta`."""
    plano = {
        "versao": 1,
        "seq": sobreposicao.seq_do_plano,
        "aprovado_por": AUTOR_SINTETICO,
        "papel": PapelAutor.HUMANO.value,
    }
    nos = dict(estado.nos)
    nos[id_goal] = estado.nos[id_goal].com_propriedades(
        {CAMPO_PLANOS: [plano], CAMPO_RESPOSTAS_DE_DESVIO: [dict(r) for r in sobreposicao.respostas]}
    )
    arestas = dict(estado.arestas)
    if sobreposicao.motivo != EscolhaDoMotivo.NENHUM:
        arestas.update(_motivos_pelo_orienta(estado, sobreposicao.motivo))
    return GrafoEstado(nos=nos, arestas=arestas, versao_log=estado.versao_log)


def _motivos_pelo_orienta(estado: GrafoEstado, escolha: EscolhaDoMotivo) -> dict[str, ArestaGrafo]:
    """Uma `motivada_por` da Task para a Decision que a orienta, segundo a escolha."""
    orientadoras: dict[str, list[str]] = defaultdict(list)
    for aresta in estado.arestas.values():
        if aresta.tipo == TipoAresta.ORIENTA and _decisao_orienta_task(estado, aresta):
            orientadoras[aresta.destino_id].append(aresta.origem_id)
    alcance = Counter(id_decisao for ids in orientadoras.values() for id_decisao in ids)
    motivos: dict[str, ArestaGrafo] = {}
    for id_task, decisoes in orientadoras.items():
        for id_decisao in _escolhidas(estado, decisoes, (escolha, alcance)):
            id_motivo = f"motivada-{id_task}-{id_decisao}"
            motivos[id_motivo] = ArestaGrafo(
                id=id_motivo, origem_id=id_task, destino_id=id_decisao, tipo=TipoAresta.MOTIVADA_POR
            )
    return motivos


def _escolhidas(
    estado: GrafoEstado, decisoes: list[str], criterio: tuple[EscolhaDoMotivo, Mapping[str, int]]
) -> list[str]:
    """As Decisions que viram `motivada_por` da Task: todas, ou a que a escolha elege."""
    escolha, alcance = criterio
    if escolha == EscolhaDoMotivo.TODAS:
        return decisoes
    nascimento = {id_decisao: estado.nos[id_decisao].ordem.seq_criacao for id_decisao in decisoes}
    chaves = {
        EscolhaDoMotivo.MAIS_RECENTE: lambda d: (-nascimento[d], d),
        EscolhaDoMotivo.MAIS_ANTIGA: lambda d: (nascimento[d], d),
        EscolhaDoMotivo.MAIS_ABRANGENTE: lambda d: (-alcance[d], d),
    }
    return [min(decisoes, key=chaves[escolha])]


def _decisao_orienta_task(estado: GrafoEstado, aresta: ArestaGrafo) -> bool:
    """A aresta `orienta` vai de uma Decision a uma Task."""
    origem, destino = estado.nos.get(aresta.origem_id), estado.nos.get(aresta.destino_id)
    return origem is not None and destino is not None and origem.tipo == TipoNo.DECISION and destino.tipo == TipoNo.TASK
