"""Caminho crítico: quem trava quem, e quanto cada gargalo destrava.

A vista esconde tudo que não participa de uma relação de dependência e ordena o
que sobra por quantas tarefas cada nó libera ao ser concluído. É a vista de
desempate quando há fila — não a de leitura do projeto.

O valor dela depende inteiramente de as dependências estarem declaradas. Medido
no grafo real: só 20 das 318 arestas são `depende_de` ou `bloqueia`, tocando 24
nós, e cinco das oito tarefas pendentes não declaram pré-requisito algum. Num
grafo assim a vista mostra pouco, e `total_de_arestas_de_dependencia` existe
justamente para a interface poder dizer isso em vez de exibir uma tela vazia
como se fosse resposta.
"""

from dataclasses import dataclass, field

from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import StatusTask, TipoAresta, TipoNo

# As duas formas de uma coisa travar outra: pré-requisito declarado e dúvida aberta.
ARESTAS_DE_DEPENDENCIA: frozenset[TipoAresta] = frozenset(
    {TipoAresta.DEPENDE_DE, TipoAresta.BLOQUEIA}
)
PROFUNDIDADE_MAXIMA: int = 32


@dataclass(frozen=True)
class Gargalo:
    """Um nó que trava outros, com o tamanho do que ele segura."""

    id: str
    rotulo: str
    tipo: str
    status: str
    desbloqueia_diretamente: int
    desbloqueia_no_total: int

    def em_dicionario(self) -> dict[str, object]:
        """Forma serializável para a resposta REST e para a ferramenta MCP."""
        return {
            "id": self.id,
            "rotulo": self.rotulo,
            "tipo": self.tipo,
            "status": self.status,
            "desbloqueia_diretamente": self.desbloqueia_diretamente,
            "desbloqueia_no_total": self.desbloqueia_no_total,
        }


@dataclass(frozen=True)
class CaminhoCritico:
    """Subgrafo de dependências e os gargalos que o ordenam."""

    ids: frozenset[str] = field(default_factory=frozenset)
    gargalos: tuple[Gargalo, ...] = field(default_factory=tuple)
    total_de_arestas_de_dependencia: int = 0
    tarefas_sem_dependencia_declarada: tuple[str, ...] = field(default_factory=tuple)

    @property
    def esta_vazio(self) -> bool:
        """Sem aresta de dependência não há caminho crítico a mostrar."""
        return self.total_de_arestas_de_dependencia == 0

    def contem(self, id_no: str) -> bool:
        """Indica se o nó participa de alguma relação de dependência."""
        return id_no in self.ids

    def em_dicionario(self) -> dict[str, object]:
        """Resumo serializável, com o que a interface precisa para se explicar."""
        return {
            "nos_no_caminho": len(self.ids),
            "arestas_de_dependencia": self.total_de_arestas_de_dependencia,
            "gargalos": [gargalo.em_dicionario() for gargalo in self.gargalos],
            "tarefas_sem_dependencia_declarada": list(self.tarefas_sem_dependencia_declarada),
        }


class CalculadoraDeCaminhoCritico:
    """Extrai o subgrafo de dependências e mede o alcance de cada gargalo."""

    def __init__(self, estado: GrafoEstado) -> None:
        self._estado: GrafoEstado = estado
        self._dependentes: dict[str, set[str]] = _montar_dependentes(estado)

    def calcular(self) -> CaminhoCritico:
        """Monta o caminho com os nós participantes e os gargalos ordenados."""
        arestas = _arestas_de_dependencia(self._estado)
        participantes = {aresta.origem_id for aresta in arestas} | {
            aresta.destino_id for aresta in arestas
        }
        return CaminhoCritico(
            ids=frozenset(participantes | set(self._tarefas_abertas())),
            gargalos=self._ordenar_gargalos(participantes),
            total_de_arestas_de_dependencia=len(arestas),
            tarefas_sem_dependencia_declarada=self._tarefas_soltas(participantes),
        )

    def _ordenar_gargalos(self, participantes: set[str]) -> tuple[Gargalo, ...]:
        """Quem segura mais gente aparece primeiro; o identificador desempata."""
        gargalos = [
            self._descrever(id_no)
            for id_no in participantes
            if id_no in self._estado.nos and self._dependentes.get(id_no)
        ]
        return tuple(
            sorted(gargalos, key=lambda g: (-g.desbloqueia_no_total, -g.desbloqueia_diretamente, g.id))
        )

    def _descrever(self, id_no: str) -> Gargalo:
        """Projeta o nó com a contagem direta e a transitiva do que ele trava."""
        no = self._estado.nos[id_no]
        return Gargalo(
            id=no.id,
            rotulo=no.rotulo,
            tipo=no.tipo.value,
            status=str(no.obter_propriedade("status", "")),
            desbloqueia_diretamente=len(self._dependentes.get(id_no, set())),
            desbloqueia_no_total=len(self._alcance_transitivo(id_no)),
        )

    def _alcance_transitivo(self, id_no: str) -> set[str]:
        """Tudo que destrava, direta ou indiretamente, quando este nó sai da frente."""
        alcancados: set[str] = set()
        fronteira: set[str] = set(self._dependentes.get(id_no, set()))
        for _ in range(PROFUNDIDADE_MAXIMA):
            fronteira = self._proximo_nivel(fronteira, alcancados | {id_no})
            if not fronteira:
                break
            alcancados |= fronteira
        return alcancados | set(self._dependentes.get(id_no, set()))

    def _proximo_nivel(self, fronteira: set[str], vistos: set[str]) -> set[str]:
        """Dependentes ainda não alcançados a partir da fronteira atual."""
        descobertos: set[str] = set()
        for id_no in fronteira:
            descobertos |= self._dependentes.get(id_no, set())
        return descobertos - vistos - fronteira

    def _tarefas_abertas(self) -> tuple[str, ...]:
        """Tasks não concluídas: elas entram no caminho mesmo sem dependência."""
        return tuple(
            id_no for id_no, no in self._estado.nos.items() if _eh_tarefa_aberta(no)
        )

    def _tarefas_soltas(self, participantes: set[str]) -> tuple[str, ...]:
        """Tarefas abertas fora de qualquer dependência declarada, em ordem estável."""
        return tuple(
            sorted(id_no for id_no in self._tarefas_abertas() if id_no not in participantes)
        )


def _arestas_de_dependencia(estado: GrafoEstado) -> tuple[object, ...]:
    """Arestas que expressam alguém travando alguém."""
    return tuple(
        aresta for aresta in estado.arestas.values() if aresta.tipo in ARESTAS_DE_DEPENDENCIA
    )


def _montar_dependentes(estado: GrafoEstado) -> dict[str, set[str]]:
    """Para cada nó, quem fica livre quando ele sai da frente.

    `A depende_de B` sai de A e chega em B, então B destrava A: a aresta é lida
    ao contrário. `Q bloqueia T` já sai do bloqueador, e é lida como está.
    """
    dependentes: dict[str, set[str]] = {}
    for aresta in estado.arestas.values():
        if aresta.tipo == TipoAresta.DEPENDE_DE:
            dependentes.setdefault(aresta.destino_id, set()).add(aresta.origem_id)
        if aresta.tipo == TipoAresta.BLOQUEIA:
            dependentes.setdefault(aresta.origem_id, set()).add(aresta.destino_id)
    return dependentes


def _eh_tarefa_aberta(no: NoGrafo) -> bool:
    """Uma Task fora do estado concluído segue na fila."""
    if no.tipo != TipoNo.TASK:
        return False
    return str(no.obter_propriedade("status", StatusTask.PENDENTE.value)) != StatusTask.CONCLUIDO.value
