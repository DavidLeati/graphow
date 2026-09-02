"""Montagem da seção de vizinhos: ordem por relevância e corte por tipo.

A seção de vizinhos é a afordância de expansão — sem ela o agente não sabe o que
pedir a seguir. Ela era ordenada por identificador, sem status, e sumia inteira
sob pressão de orçamento: numa sessão de 60 tarefas, a 800 tokens, a vista tinha
37 tokens e zero vizinhos expansíveis. Agora ela encolhe por dentro, N por tipo,
e o que sobrou é anunciado em uma linha. Ver achados A-07 e A-08.
"""

from collections.abc import Mapping, Sequence

from graphow.context.secoes import GrupoDeLinhas, PrioridadeRetencao, SecaoContexto
from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, StatusTask

TITULO_VIZINHOS: str = "Vizinhos a 1 Salto (use expandir_no para aprofundar)"
ORDEM_DE_EXIBICAO_DOS_VIZINHOS: int = 9

# O que trava alguém aparece primeiro; o que já acabou aparece por último.
RELEVANCIA_POR_STATUS: Mapping[str, int] = {
    StatusTask.BLOQUEADO.value: 0,
    StatusQuestion.ABERTA.value: 0,
    StatusTask.EM_ANDAMENTO.value: 1,
    StatusTask.PRONTO_PARA_REVISAO.value: 2,
    StatusTask.PENDENTE.value: 3,
    StatusTask.CONCLUIDO.value: 5,
}
RELEVANCIA_DE_NO_SEM_STATUS: int = 4


def ordenar_por_relevancia(nos: Sequence[NoGrafo]) -> tuple[NoGrafo, ...]:
    """Ordena vizinhos por urgência do status e, em empate, por identificador."""
    return tuple(sorted(nos, key=_chave_de_relevancia))


def _chave_de_relevancia(no: NoGrafo) -> tuple[int, str]:
    """Chave estável de ordenação: faixa de relevância e identificador."""
    status = no.obter_propriedade("status")
    if status is None:
        return (RELEVANCIA_DE_NO_SEM_STATUS, no.id)
    return (RELEVANCIA_POR_STATUS.get(str(status), RELEVANCIA_DE_NO_SEM_STATUS), no.id)


def formatar_vizinho(no: NoGrafo) -> str:
    """Descreve o vizinho em uma linha, com o status quando ele existir."""
    status = no.obter_propriedade("status")
    sufixo = f" [{status}]" if status is not None else ""
    return f"- [{no.id}] ({no.tipo.value}): {no.rotulo}{sufixo}"


def montar_secao_de_vizinhos(nos: Sequence[NoGrafo]) -> SecaoContexto:
    """Monta a seção agrupada por tipo, pronta para encolher sob orçamento."""
    grupos = _agrupar_por_tipo(ordenar_por_relevancia(nos))
    return SecaoContexto(
        titulo=TITULO_VIZINHOS,
        linhas=tuple(linha for grupo in grupos for linha in grupo.linhas),
        ordem_exibicao=ORDEM_DE_EXIBICAO_DOS_VIZINHOS,
        prioridade_retencao=PrioridadeRetencao.NAVEGACAO,
        ids_incluidos=tuple(id_no for grupo in grupos for id_no in grupo.ids),
        grupos=grupos,
    )


def _agrupar_por_tipo(nos: Sequence[NoGrafo]) -> tuple[GrupoDeLinhas, ...]:
    """Reparte os vizinhos por tipo da ontologia, preservando a ordem interna."""
    por_tipo: dict[str, list[NoGrafo]] = {}
    for no in nos:
        por_tipo.setdefault(no.tipo.value, []).append(no)
    return tuple(
        GrupoDeLinhas(
            rotulo=tipo,
            linhas=tuple(formatar_vizinho(no) for no in membros),
            ids=tuple(no.id for no in membros),
        )
        for tipo, membros in sorted(por_tipo.items())
    )
