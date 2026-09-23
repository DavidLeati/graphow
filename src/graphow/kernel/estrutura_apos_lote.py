"""Hierarquia e origem conferidas no estado depois do lote, e não na lista de criações.

As duas regras do InvariantGate olhavam só os `add` do lote. Um executor
criava a Note, a `produz` que a pendura e, no mesmo lote, removia essa
`produz`: a Note nascia fora da hierarquia. O mesmo com o Aprendizado e a
`deriva_de` que é a origem dele. E um lote posterior tirava a origem de um
Aprendizado que já existia. Aqui o lote é aplicado inteiro sobre o estado,
criações e remoções, e as regras leem o resultado.

O nó criado no lote precisa estar pendurado ao fim dele, venha de quem vier:
é a regra de forma que já valia na criação. Deixar solto um nó que já existia,
removendo a contenção ou a origem dele, é recusado ao agente. O humano segue
podendo desligar à mão o que quiser, pelo canvas, como antes.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from graphow.core.models import ArestaGrafo, GrafoEstado
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import OperacaoPatch, PropostaPatch
from graphow.kernel.rastreio_projeto import projetar_lote

SEGMENTOS_DE_ELEMENTO_INTEIRO: int = 2


@dataclass(frozen=True)
class EstruturaAposLote:
    """O grafo antes e depois do lote, com o que o lote criou.

    `antes` já contém as criações do lote: é a antevisão que o RoleGate usa.
    `depois` retira dela os nós e arestas removidos, e as arestas que a
    projeção apaga junto com o nó removido.
    """

    antes: GrafoEstado
    depois: GrafoEstado
    criados: frozenset[str]
    desliga_existentes: bool

    @classmethod
    def antever(cls, proposta: PropostaPatch, estado: GrafoEstado) -> "EstruturaAposLote":
        """Aplica o lote inteiro sobre o estado, só para consulta."""
        antes = projetar_lote(proposta.operacoes, estado)
        removidos = _ids_removidos(proposta)
        return cls(
            antes=antes,
            depois=_sem_os_removidos(antes, removidos),
            criados=frozenset(id_no for id_no in antes.nos if id_no not in estado.nos),
            desliga_existentes=proposta.papel != PapelAutor.HUMANO,
        )

    def nos_fora_da_hierarquia(self) -> tuple[str, ...]:
        """Nós que o lote cria, ou de que o agente tira a contenção, e ficam sem pai."""
        desligados = self._pontas_de_arestas_perdidas(ARESTAS_DE_CONTENCAO, destino=True)
        com_pai = {aresta.destino_id for aresta in self._arestas_depois(ARESTAS_DE_CONTENCAO)}
        return self._sobreviventes_sem(self.criados | desligados, com_pai, excluir=TipoNo.PROJETO)

    def aprendizados_sem_origem(self) -> tuple[str, ...]:
        """Aprendizados que o lote cria, ou de que o agente tira a origem, e ficam sem `deriva_de`."""
        derivacao = frozenset({TipoAresta.DERIVA_DE})
        desligados = self._pontas_de_arestas_perdidas(derivacao, destino=False)
        com_origem = {aresta.origem_id for aresta in self._arestas_depois(derivacao)}
        candidatos = {
            id_no for id_no in self.criados | desligados
            if id_no in self.depois.nos and self.depois.nos[id_no].tipo == TipoNo.APRENDIZADO
        }
        return tuple(sorted(candidatos - com_origem))

    def _arestas_depois(self, tipos: frozenset[TipoAresta]) -> Iterable[ArestaGrafo]:
        """Arestas dos tipos informados que existem ao fim do lote."""
        return (aresta for aresta in self.depois.arestas.values() if aresta.tipo in tipos)

    def _pontas_de_arestas_perdidas(self, tipos: frozenset[TipoAresta], *, destino: bool) -> frozenset[str]:
        """A ponta que a aresta sustentava, em cada aresta dos tipos que o lote remove."""
        if not self.desliga_existentes:
            return frozenset()
        perdidas = (
            aresta for id_aresta, aresta in self.antes.arestas.items()
            if aresta.tipo in tipos and id_aresta not in self.depois.arestas
        )
        return frozenset(aresta.destino_id if destino else aresta.origem_id for aresta in perdidas)

    def _sobreviventes_sem(self, candidatos: frozenset[str], sustentados: set[str], *, excluir: TipoNo) -> tuple[str, ...]:
        """Candidatos que seguem no grafo, não são do tipo excluído e não estão sustentados."""
        return tuple(
            id_no for id_no in sorted(candidatos)
            if id_no in self.depois.nos and self.depois.nos[id_no].tipo != excluir and id_no not in sustentados
        )


def _ids_removidos(proposta: PropostaPatch) -> dict[str, frozenset[str]]:
    """Ids de nós e de arestas que o lote remove inteiros, por coleção."""
    removidos: dict[str, set[str]] = {"nos": set(), "arestas": set()}
    for item in proposta.operacoes:
        segmentos = item.path.split("/")[1:]
        if item.op != OperacaoPatch.REMOVE or len(segmentos) != SEGMENTOS_DE_ELEMENTO_INTEIRO:
            continue
        removidos.setdefault(segmentos[0], set()).add(segmentos[1])
    return {colecao: frozenset(ids) for colecao, ids in removidos.items()}


def _sem_os_removidos(antes: GrafoEstado, removidos: dict[str, frozenset[str]]) -> GrafoEstado:
    """O estado sem os nós e arestas removidos, nem as arestas que tocavam um nó removido."""
    nos_removidos = removidos["nos"]
    nos = {id_no: no for id_no, no in antes.nos.items() if id_no not in nos_removidos}
    arestas = {
        id_aresta: aresta
        for id_aresta, aresta in antes.arestas.items()
        if id_aresta not in removidos["arestas"]
        and aresta.origem_id not in nos_removidos
        and aresta.destino_id not in nos_removidos
    }
    return GrafoEstado(nos=nos, arestas=arestas, versao_log=antes.versao_log)
