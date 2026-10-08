"""A cobertura de origem (D): quantas Tasks do histórico o kernel 1.5.0 aceitaria ou recusaria.

Depois do plano aprovado, o kernel recusa a Task sem ligação estrutural
(`ligacao_de_escopo_ausente`). Aqui o classificador real lê o estado final do
corpus com o plano sintético e SEM a `motivada_por` injetada: o que ele não
reconhece como subdivisão, correção, acompanhamento, integração, reversão ou
emergente com critério é o que o kernel recusaria. O log pré-1.5.0 não tem
`atende_criterio`, `acompanha`, `integra` nem `desfaz`, então só a subdivisão e a
correção (`corrige` para uma Evidence rejeitada) têm como ser reconhecidas.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from graphow.avaliacao.corpus_escopo import CorpusEscopo
from graphow.avaliacao.escopo_historia import HistoriaDoGoal
from graphow.avaliacao.escopo_sintetico import EscolhaDoMotivo, Sobreposicao, sobrepor
from graphow.avaliacao.escopo_vista import VistaIndexada
from graphow.projection.classificacao_escopo import BaseDoPlano, ClasseDeEscopo, ClassificadorDeEscopo


@dataclass(frozen=True)
class CoberturaDoGoal:
    """As Tasks criadas depois do plano, por classe que o classificador real lhes dá."""

    id_goal: str
    por_classe: Mapping[str, int]
    de_agente: int
    recusadas_de_agente: int

    @property
    def depois_do_plano(self) -> int:
        """Quantas Tasks nasceram depois do plano."""
        return sum(self.por_classe.values())

    @property
    def recusadas(self) -> int:
        """As que o kernel 1.5.0 recusaria com `ligacao_de_escopo_ausente`."""
        return self.por_classe.get(ClasseDeEscopo.SEM_LIGACAO.value, 0)

    @property
    def aceitas(self) -> int:
        """As que têm ligação estrutural válida."""
        return self.depois_do_plano - self.recusadas


def medir_cobertura(corpus: CorpusEscopo, historia: HistoriaDoGoal) -> CoberturaDoGoal:
    """Classifica pelo kernel real, no estado final, cada Task criada depois do plano."""
    sobreposicao = Sobreposicao(historia.seq_do_plano, motivo=EscolhaDoMotivo.NENHUM)
    view = VistaIndexada(sobrepor(corpus.estado, historia.id_goal, sobreposicao))
    classificador = ClassificadorDeEscopo(view, BaseDoPlano.VIGENTE)
    classes = {task.id: classificador.classe_da(task.id) for task in historia.depois_do_plano}
    de_agente = [task.id for task in historia.depois_do_plano if task.papel != "humano"]
    sem_ligacao = ClasseDeEscopo.SEM_LIGACAO
    return CoberturaDoGoal(
        id_goal=historia.id_goal,
        por_classe=dict(sorted(Counter(classe.value for classe in classes.values()).items())),
        de_agente=len(de_agente),
        recusadas_de_agente=sum(1 for id_task in de_agente if classes[id_task] == sem_ligacao),
    )
