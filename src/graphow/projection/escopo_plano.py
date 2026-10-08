"""O plano aprovado de um Goal lido do grafo: versões, referência, conjunto de Tasks e Goal de uma Task.

O plano mora em `Goal.planos`, uma lista que só cresce. Cada versão guarda o
`seq` do log em que foi aprovada, e o conjunto de Tasks do plano é o que estava
sob o Goal por `decompoe` até esse `seq`. O kernel, a fila e o placar leem o
plano só por aqui, para não haver duas leituras que divergem. A leitura é
tolerante: campo ausente ou malformado quer dizer "sem plano", nunca erro.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.projection.graph_view import GrafoView

PAPEIS_QUE_APROVAM_PLANO: frozenset[str] = frozenset(
    {PapelAutor.HUMANO.value, PapelAutor.ARBITRO.value}
)
PROFUNDIDADE_MAXIMA_DA_DECOMPOSICAO: int = 64


@dataclass(frozen=True)
class VersaoDoPlano:
    """Uma aprovação do plano: qual versão, em que ponto do log e por quem."""

    versao: int
    seq: int
    aprovado_por: str
    papel: str

    @property
    def eh_humano(self) -> bool:
        """Só a aprovação humana serve de referência do desvio."""
        return self.papel == PapelAutor.HUMANO.value


class IndiceDeDecomposicao:
    """Pais e filhos por `decompoe`, indexados uma vez para as travessias não varrerem as arestas."""

    def __init__(self, view: GrafoView) -> None:
        self._filhos: dict[str, list[str]] = defaultdict(list)
        self._pais: dict[str, list[str]] = defaultdict(list)
        for aresta in view.listar_todas_as_arestas():
            if aresta.tipo == TipoAresta.DECOMPOE:
                self._filhos[aresta.origem_id].append(aresta.destino_id)
                self._pais[aresta.destino_id].append(aresta.origem_id)

    def filhos(self, id_no: str) -> tuple[str, ...]:
        """Os destinos de `decompoe` que saem do nó, em ordem de identificador."""
        return tuple(sorted(set(self._filhos.get(id_no, ()))))

    def pais(self, id_no: str) -> tuple[str, ...]:
        """As origens de `decompoe` que chegam ao nó, em ordem de identificador."""
        return tuple(sorted(set(self._pais.get(id_no, ()))))


def planos_do_goal(view: GrafoView, id_goal: str) -> tuple[VersaoDoPlano, ...]:
    """As versões bem formadas de `Goal.planos`, da mais antiga à mais nova; vazio sem plano."""
    no = view.obter_no(id_goal)
    bruto = no.obter_propriedade(CAMPO_PLANOS) if no is not None else None
    if not isinstance(bruto, (list, tuple)):
        return ()
    versoes = (_ler_versao(item) for item in bruto)
    return tuple(sorted((v for v in versoes if v is not None), key=lambda v: (v.versao, v.seq)))


def plano_vigente(view: GrafoView, id_goal: str) -> VersaoDoPlano | None:
    """A última versão aprovada, de qualquer papel; None quando o Goal não tem plano."""
    planos = planos_do_goal(view, id_goal)
    return planos[-1] if planos else None


def plano_de_referencia(view: GrafoView, id_goal: str) -> VersaoDoPlano | None:
    """A última versão aprovada por humano; None faz toda Task contar como emergente."""
    humanos = [plano for plano in planos_do_goal(view, id_goal) if plano.eh_humano]
    return humanos[-1] if humanos else None


def tasks_do_plano(
    view: GrafoView,
    id_goal: str,
    versao: VersaoDoPlano,
    *,
    indice: IndiceDeDecomposicao | None = None,
) -> frozenset[str]:
    """As Tasks alcançáveis do Goal por `decompoe`, nascidas até o `seq` da versão.

    A travessia só atravessa Task do plano: uma Task nascida depois não puxa
    as filhas para dentro, que são subdivisão dela e não do plano.
    """
    indice = indice or IndiceDeDecomposicao(view)
    no_plano: set[str] = set()
    fronteira = [id_goal]
    for _ in range(PROFUNDIDADE_MAXIMA_DA_DECOMPOSICAO):
        filhos = {filho for id_no in fronteira for filho in indice.filhos(id_no)}
        fronteira = sorted(f for f in filhos - no_plano if _nasceu_ate(view, f, versao.seq))
        no_plano.update(fronteira)
        if not fronteira:
            break
    return frozenset(no_plano)


def goal_da_task(
    view: GrafoView,
    id_task: str,
    *,
    indice: IndiceDeDecomposicao | None = None,
) -> str | None:
    """O Goal mais próximo acima da Task por `decompoe`; None quando nenhum a contém.

    Com mais de um caminho vale o Goal de menor distância e, no empate, o de
    menor identificador: a resposta não depende da ordem das arestas.
    """
    indice = indice or IndiceDeDecomposicao(view)
    visitados = {id_task}
    nivel = [id_task]
    for _ in range(PROFUNDIDADE_MAXIMA_DA_DECOMPOSICAO):
        nivel = sorted({pai for id_no in nivel for pai in indice.pais(id_no) if pai not in visitados})
        visitados.update(nivel)
        goals = [id_no for id_no in nivel if _eh_do_tipo(view, id_no, TipoNo.GOAL)]
        if goals:
            return goals[0]
        if not nivel:
            return None
    return None


def seq_do_ultimo_zero(view: GrafoView, id_goal: str) -> int:
    """O `seq` em que o contador M zerou pela última vez; 0 quando nunca zerou.

    Zeram o contador só a aprovação de plano e a resposta de desvio feitas por
    humano, os dois gestos que mostram o placar.
    """
    seqs = [plano.seq for plano in planos_do_goal(view, id_goal) if plano.eh_humano]
    seqs.extend(_seqs_de_respostas_humanas(view, id_goal))
    return max(seqs, default=0)


def _seqs_de_respostas_humanas(view: GrafoView, id_goal: str) -> list[int]:
    """Os `seq` das respostas de desvio dadas por humano, ignorando entrada malformada."""
    no = view.obter_no(id_goal)
    bruto = no.obter_propriedade(CAMPO_RESPOSTAS_DE_DESVIO) if no is not None else None
    if not isinstance(bruto, (list, tuple)):
        return []
    humanas = (
        item for item in bruto if isinstance(item, Mapping) and item.get("papel") == PapelAutor.HUMANO.value
    )
    return [seq for seq in (_ler_inteiro(item.get("seq")) for item in humanas) if seq is not None]


def _ler_versao(item: Any) -> VersaoDoPlano | None:
    """Uma entrada de `planos` como versão, ou None quando falta campo ou o tipo não serve."""
    if not isinstance(item, Mapping):
        return None
    versao, seq = _ler_inteiro(item.get("versao")), _ler_inteiro(item.get("seq"))
    papel = item.get("papel")
    if versao is None or seq is None or papel not in PAPEIS_QUE_APROVAM_PLANO:
        return None
    return VersaoDoPlano(versao=versao, seq=seq, aprovado_por=str(item.get("aprovado_por", "")), papel=papel)


def _ler_inteiro(valor: Any) -> int | None:
    """O valor como inteiro, recusando booleano e o que não for número inteiro."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _nasceu_ate(view: GrafoView, id_no: str, seq: int) -> bool:
    """O nó é Task e foi criado até o `seq` dado."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == TipoNo.TASK and no.ordem.seq_criacao <= seq


def _eh_do_tipo(view: GrafoView, id_no: str, tipo: TipoNo) -> bool:
    """O nó existe e é do tipo pedido."""
    no = view.obter_no(id_no)
    return no is not None and no.tipo == tipo
