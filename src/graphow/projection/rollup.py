"""Resumo agregado de cada subárvore de contenção, calculado uma vez por commit.

Descer a hierarquia para descobrir onde há trabalho aberto custava uma vista por
contêiner: no grafo de 191 nós isso eram 8.819 tokens e onze chamadas, e ao fim
delas o agente sabia o que já poderia ter lido em uma linha por setor. O índice
abaixo responde a mesma pergunta em ~100 tokens.

Ele é recalculado inteiro a cada commit, não mantido incrementalmente. Medido:
0,53 ms para 191 nós e 318 arestas. Manutenção incremental exigiria invalidar
subárvores a cada aresta removida e a cada cascata de remoção de nó, o que é
complexidade real contra meio milissegundo — e arriscaria o invariante de que a
projeção é uma dobra determinística do log.

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
    """Resumo de cada subárvore de contenção do grafo, pronto para consulta."""

    def __init__(
        self,
        resumos: Mapping[str, ResumoDeSubarvore],
        orfaos: tuple[str, ...] = (),
    ) -> None:
        self._resumos: Mapping[str, ResumoDeSubarvore] = dict(resumos)
        self._orfaos: tuple[str, ...] = orfaos

    @classmethod
    def calcular(cls, estado: GrafoEstado) -> "IndiceDeRollup":
        """Dobra o estado inteiro em um resumo por contêiner, em uma passada."""
        filhos = _mapear_filhos(estado)
        alcances = _MotorDeAlcance(estado, filhos).resolver_todos()
        substituidas = decisoes_substituidas(estado)
        resumos = {
            id_no: _resumir(id_no, _nos_alcancados(alcances[id_no], estado), substituidas)
            for id_no in filhos
            if id_no in estado.nos
        }
        return cls(resumos=resumos, orfaos=_detectar_orfaos(estado))

    def obter(self, id_no: str) -> ResumoDeSubarvore | None:
        """Resumo da subárvore do nó, ou None quando ele não contém nada."""
        return self._resumos.get(id_no)

    def eh_container(self, id_no: str) -> bool:
        """Indica se o nó tem ao menos um filho por contenção."""
        return id_no in self._resumos

    @property
    def nos_orfaos(self) -> tuple[str, ...]:
        """Nós fora de qualquer hierarquia, que sumiriam calados na tela colapsada."""
        return self._orfaos

    @property
    def total_de_containers(self) -> int:
        """Quantos nós do grafo têm subárvore resumida."""
        return len(self._resumos)


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


class _MotorDeAlcance:
    """Resolve, para cada nó, o conjunto de identificadores da sua subárvore.

    A travessia é iterativa e em duas fases (descer, depois combinar) porque a
    contenção admite ciclo: um `decompoe` circular estouraria a pilha de uma
    recursão ingênua. Um filho ainda em progresso é um ancestral na própria
    pilha, e é justamente aí que o ciclo se corta.
    """

    def __init__(self, estado: GrafoEstado, filhos: Mapping[str, tuple[str, ...]]) -> None:
        self._estado: GrafoEstado = estado
        self._filhos: Mapping[str, tuple[str, ...]] = filhos
        self._memo: dict[str, frozenset[str]] = {}
        self._em_progresso: set[str] = set()

    def resolver_todos(self) -> Mapping[str, frozenset[str]]:
        """Alcance de cada nó do grafo, incluindo ele mesmo."""
        for id_no in self._estado.nos:
            self._resolver(id_no)
        return self._memo

    def _resolver(self, raiz: str) -> None:
        """Percorre a subárvore da raiz com pilha explícita, sem recursão."""
        pilha: list[tuple[str, bool]] = [(raiz, False)]
        while pilha:
            id_no, combinar = pilha.pop()
            self._processar(id_no, combinar, pilha)

    def _processar(self, id_no: str, combinar: bool, pilha: list[tuple[str, bool]]) -> None:
        """Empilha os filhos na descida e une os alcances na volta."""
        if combinar:
            self._memo[id_no] = self._unir(id_no)
            self._em_progresso.discard(id_no)
            return
        if id_no in self._memo or id_no in self._em_progresso:
            return
        self._em_progresso.add(id_no)
        pilha.append((id_no, True))
        pilha.extend((filho, False) for filho in self._filhos.get(id_no, ()))

    def _unir(self, id_no: str) -> frozenset[str]:
        """Junta o próprio nó aos alcances já resolvidos dos seus filhos."""
        alcancado: set[str] = {id_no}
        for filho in self._filhos.get(id_no, ()):
            alcancado.update(self._memo.get(filho, frozenset()))
        return frozenset(alcancado)
