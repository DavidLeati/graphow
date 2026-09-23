"""Resumo agregado de cada subárvore de contenção, calculado uma vez por commit.

Descer a hierarquia para descobrir onde há trabalho aberto custava uma vista por
contêiner: no grafo de 191 nós isso eram 8.819 tokens e onze chamadas, e ao fim
delas o agente sabia o que já poderia ter lido em uma linha por setor. O índice
abaixo responde a mesma pergunta em ~100 tokens.

O commit só mapeia filhos e órfãos, em tempo linear; o resumo de cada
contêiner é calculado na primeira consulta e guardado. O índice resolvia de
saída o alcance de todo nó do grafo, e esse custo é a soma dos tamanhos de
subárvore: numa cadeia de `decompoe` com 5.000 Tasks, 11,5 s por commit para
resumos que ninguém pediu. Manutenção incremental exigiria invalidar subárvores
a cada aresta removida e a cada cascata de remoção de nó, e arriscaria o
invariante de que a projeção é uma dobra determinística do log.

A agregação une conjuntos de identificadores em vez de somar contagens porque a
contenção é um DAG, não uma árvore: um nó alcançável por dois pais seria contado
duas vezes numa soma. O custo é memória proporcional à soma dos tamanhos de
subárvore, aceitável na ordem de grandeza que o substrato atende.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import StatusQuestion, StatusTask, TipoNo
from graphow.projection.fechamento import (
    FechamentoDeSubarvore,
    calcular_fechamento,
    decisoes_substituidas,
)

# Uma tarefa nestes estados não pede mais nada de ninguém.
STATUS_TERMINAIS_DE_TAREFA: frozenset[str] = frozenset({StatusTask.CONCLUIDO.value})


@dataclass(frozen=True)
class ResumoDeSubarvore:
    """O que existe sob um contêiner, sem precisar abri-lo."""

    id: str
    total_nos: int
    tarefas_por_status: Mapping[str, int] = field(default_factory=dict)
    questoes_abertas: int = 0
    seq_ultimo_toque: int = 0
    # O esqueleto do fechamento viaja com o resumo porque é derivado do mesmo
    # conjunto alcançado: calculá-lo à parte abriria a janela em que discordam.
    fechamento: FechamentoDeSubarvore = field(default_factory=FechamentoDeSubarvore)

    @property
    def tarefas_totais(self) -> int:
        """Quantas Tasks a subárvore contém, em qualquer estado."""
        return sum(self.tarefas_por_status.values())

    @property
    def tarefas_concluidas(self) -> int:
        """Quantas dessas Tasks já chegaram a um estado terminal."""
        return sum(
            total
            for status, total in self.tarefas_por_status.items()
            if status in STATUS_TERMINAIS_DE_TAREFA
        )

    @property
    def tarefas_abertas(self) -> int:
        """Quantas Tasks ainda pedem trabalho de alguém."""
        return self.tarefas_totais - self.tarefas_concluidas

    @property
    def tem_trabalho_aberto(self) -> bool:
        """Indica se vale a pena descer neste contêiner."""
        return self.tarefas_abertas > 0 or self.questoes_abertas > 0

    def descrever(self) -> str:
        """Linha compacta de panorama, na casa de dez tokens."""
        partes = [f"{self.tarefas_concluidas}/{self.tarefas_totais} tarefas concluidas"]
        if self.tarefas_abertas:
            partes.append(f"{self.tarefas_abertas} abertas")
        if self.questoes_abertas:
            partes.append(f"{self.questoes_abertas} duvidas abertas")
        partes.append(f"{self.total_nos} nos")
        return ", ".join(partes)

    def em_dicionario(self) -> dict[str, object]:
        """Forma serializável para o canvas e para as respostas REST."""
        return {
            "total_nos": self.total_nos,
            "tarefas_totais": self.tarefas_totais,
            "tarefas_concluidas": self.tarefas_concluidas,
            "tarefas_abertas": self.tarefas_abertas,
            "tarefas_por_status": dict(self.tarefas_por_status),
            "questoes_abertas": self.questoes_abertas,
            "seq_ultimo_toque": self.seq_ultimo_toque,
            "fechamento": self.fechamento.em_dicionario(),
        }


class IndiceDeRollup:
    """Resumo de cada subárvore de contenção do grafo, calculado quando pedido."""

    def __init__(self, estado: GrafoEstado, filhos: Mapping[str, tuple[str, ...]]) -> None:
        self._estado: GrafoEstado = estado
        self._filhos: Mapping[str, tuple[str, ...]] = filhos
        self._resumos: dict[str, ResumoDeSubarvore] = {}
        self._substituidas: frozenset[str] | None = None
        self._orfaos: tuple[str, ...] = _detectar_orfaos(estado)

    @classmethod
    def calcular(cls, estado: GrafoEstado) -> "IndiceDeRollup":
        """Mapeia a contenção do estado; os resumos saem sob demanda."""
        return cls(estado, _mapear_filhos(estado))

    def obter(self, id_no: str) -> ResumoDeSubarvore | None:
        """Resumo da subárvore do nó, ou None quando ele não contém nada."""
        if not self.eh_container(id_no):
            return None
        if id_no not in self._resumos:
            self._resumos[id_no] = self._resumir(id_no)
        return self._resumos[id_no]

    def eh_container(self, id_no: str) -> bool:
        """Indica se o nó tem ao menos um filho por contenção."""
        return id_no in self._filhos and id_no in self._estado.nos

    @property
    def nos_orfaos(self) -> tuple[str, ...]:
        """Nós fora de qualquer hierarquia, que sumiriam calados na tela colapsada."""
        return self._orfaos

    @property
    def total_de_containers(self) -> int:
        """Quantos nós do grafo têm subárvore resumida."""
        return sum(1 for id_no in self._filhos if id_no in self._estado.nos)

    def _resumir(self, id_no: str) -> ResumoDeSubarvore:
        """Percorre a subárvore do nó uma vez e conta o que ela contém."""
        if self._substituidas is None:
            self._substituidas = decisoes_substituidas(self._estado)
        alcancados = _alcance(id_no, self._filhos)
        return _resumir(id_no, _nos_alcancados(alcancados, self._estado), self._substituidas)


def _mapear_filhos(estado: GrafoEstado) -> dict[str, tuple[str, ...]]:
    """Lista, por nó, os filhos alcançados por arestas de contenção."""
    acumulado: dict[str, list[str]] = {}
    for aresta in estado.arestas.values():
        if aresta.tipo not in ARESTAS_DE_CONTENCAO:
            continue
        acumulado.setdefault(aresta.origem_id, []).append(aresta.destino_id)
    return {origem: tuple(dict.fromkeys(destinos)) for origem, destinos in acumulado.items()}


def _detectar_orfaos(estado: GrafoEstado) -> tuple[str, ...]:
    """Nós sem pai por contenção, excluídos os Projetos, que são raízes legítimas."""
    com_pai = {
        aresta.destino_id
        for aresta in estado.arestas.values()
        if aresta.tipo in ARESTAS_DE_CONTENCAO
    }
    return tuple(
        sorted(
            id_no
            for id_no, no in estado.nos.items()
            if id_no not in com_pai and no.tipo != TipoNo.PROJETO
        )
    )


def _nos_alcancados(ids_alcancados: frozenset[str], estado: GrafoEstado) -> tuple[NoGrafo, ...]:
    """Resolve os identificadores alcançados nos nós da projeção, em ordem estável."""
    return tuple(estado.nos[id_no] for id_no in sorted(ids_alcancados) if id_no in estado.nos)


def _resumir(
    id_no: str,
    nos: tuple[NoGrafo, ...],
    substituidas: frozenset[str],
) -> ResumoDeSubarvore:
    """Conta uma vez, ao final, o que o conjunto alcançado contém."""
    return ResumoDeSubarvore(
        id=id_no,
        total_nos=len(nos),
        tarefas_por_status=_contar_tarefas_por_status(nos),
        questoes_abertas=sum(1 for no in nos if _eh_questao_aberta(no)),
        seq_ultimo_toque=max((no.ordem.seq_atualizacao for no in nos), default=0),
        fechamento=calcular_fechamento(nos, substituidas),
    )


def _contar_tarefas_por_status(nos: tuple[NoGrafo, ...]) -> dict[str, int]:
    """Distribuição das Tasks da subárvore pelos estados do ciclo de vida."""
    contagem: dict[str, int] = {}
    for no in nos:
        if no.tipo != TipoNo.TASK:
            continue
        status = str(no.obter_propriedade("status", StatusTask.PENDENTE.value))
        contagem[status] = contagem.get(status, 0) + 1
    return contagem


def _eh_questao_aberta(no: NoGrafo) -> bool:
    """Uma Question sem resposta é o que trava a subárvore e precisa do humano."""
    if no.tipo != TipoNo.QUESTION:
        return False
    return no.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value


def _alcance(raiz: str, filhos: Mapping[str, tuple[str, ...]]) -> frozenset[str]:
    """A raiz e tudo o que ela contém, por pilha explícita.

    O conjunto de visitados corta ciclos: um `decompoe` circular não trava a
    travessia nem estoura a pilha, e cada nó do ciclo alcança os demais.
    """
    alcancados: set[str] = {raiz}
    pilha: list[str] = [raiz]
    while pilha:
        ineditos = [filho for filho in filhos.get(pilha.pop(), ()) if filho not in alcancados]
        alcancados.update(ineditos)
        pilha.extend(ineditos)
    return frozenset(alcancados)
