"""Escopo ativo: o que está perto do trabalho que ainda não terminou.

Filtrar por estado terminal não resolve neste substrato. Medido no grafo real,
só 24% dos nós estão num estado terminal e 66% não têm estado nenhum — Artifact,
Evidence, Note e Decision não têm ciclo de vida. Um filtro por status ou esconde
esses 66%, apagando a memória que impede re-decidir, ou não esconde nada.

O eixo que funciona é a distância até o trabalho aberto. As sementes são as Tasks
não concluídas e as Questions sem resposta; o alcance sai delas por arestas de
trabalho, num raio curto. Medido no grafo real, já contando os contêineres:
raio 1 devolve 27 dos 191 nós, raio 2 devolve 74. O padrão é 1 justamente porque
o raio 2 traz quase 40% do grafo de volta e desfaz o efeito.

`contem` fica fora das arestas percorridas: ela liga Projeto a Setor a Sessão, e
percorrê-la traria o projeto inteiro em dois saltos. Os contêineres entram por
outro caminho — como ancestrais do que foi alcançado, para que nada apareça
solto, sem a sessão a que pertence.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import StatusQuestion, StatusTask, TipoAresta, TipoNo

RAIO_PADRAO: int = 1
RAIO_MAXIMO: int = 6

# Toda aresta que liga trabalho a trabalho. Fora ficam `contem`, que é navegação
# pura, e `ocorreu_em`, que só amarra execuções ao lugar onde rodaram.
ARESTAS_DE_TRABALHO: frozenset[TipoAresta] = frozenset(
    {
        TipoAresta.PRODUZ,
        TipoAresta.DECOMPOE,
        TipoAresta.DEPENDE_DE,
        TipoAresta.BLOQUEIA,
        TipoAresta.JUSTIFICA,
        TipoAresta.CONTRADIZ,
        TipoAresta.SUBSTITUI,
        TipoAresta.ESCOPA,
        TipoAresta.DERIVA_DE,
        TipoAresta.ORIENTA,
    }
)


@dataclass(frozen=True)
class EscopoAtivo:
    """Conjunto de nós próximos ao trabalho aberto, com a semente que os trouxe."""

    ids: frozenset[str] = field(default_factory=frozenset)
    sementes: frozenset[str] = field(default_factory=frozenset)
    raio: int = RAIO_PADRAO

    def contem(self, id_no: str) -> bool:
        """Indica se o nó pertence ao escopo ativo."""
        return id_no in self.ids

    @property
    def esta_vazio(self) -> bool:
        """Sem trabalho aberto não há escopo ativo: a tela deve mostrar tudo."""
        return not self.sementes

    def em_dicionario(self) -> dict[str, object]:
        """Resumo serializável do recorte, para o canvas explicar o que escondeu."""
        return {
            "raio": self.raio,
            "sementes": len(self.sementes),
            "nos_no_escopo": len(self.ids),
        }


class CalculadoraDeEscopoAtivo:
    """Percorre o grafo a partir do trabalho aberto até o raio pedido."""

    def __init__(self, estado: GrafoEstado) -> None:
        self._estado: GrafoEstado = estado
        self._adjacencia: dict[str, set[str]] = _montar_adjacencia(estado, ARESTAS_DE_TRABALHO)

    def calcular(self, raio: int = RAIO_PADRAO) -> EscopoAtivo:
        """Monta o escopo: sementes, alcance no raio e os contêineres de tudo isso."""
        sementes = self._coletar_sementes()
        if not sementes:
            return EscopoAtivo(raio=_sanear_raio(raio))
        raio_efetivo = _sanear_raio(raio)
        alcancados = self._expandir(sementes, raio_efetivo)
        completos = alcancados | self._ancestrais_por_contencao(alcancados)
        return EscopoAtivo(ids=frozenset(completos), sementes=frozenset(sementes), raio=raio_efetivo)

    def _coletar_sementes(self) -> set[str]:
        """Tasks que ainda pedem trabalho e Questions que ainda esperam resposta."""
        return {
            id_no
            for id_no, no in self._estado.nos.items()
            if _eh_tarefa_aberta(no) or _eh_questao_aberta(no)
        }

    def _expandir(self, sementes: set[str], raio: int) -> set[str]:
        """Busca em largura não-direcionada sobre as arestas de trabalho."""
        alcancados: set[str] = set(sementes)
        fronteira: set[str] = set(sementes)
        for _ in range(raio):
            fronteira = self._proximo_nivel(fronteira, alcancados)
            alcancados |= fronteira
        return alcancados

    def _proximo_nivel(self, fronteira: set[str], vistos: set[str]) -> set[str]:
        """Vizinhos ainda não alcançados a partir da fronteira atual."""
        descobertos: set[str] = set()
        for id_no in fronteira:
            descobertos |= self._adjacencia.get(id_no, set())
        return descobertos - vistos

    def _ancestrais_por_contencao(self, ids: set[str]) -> set[str]:
        """Contêineres acima do que foi alcançado, para nada aparecer solto na tela."""
        pais = _montar_pais_por_contencao(self._estado)
        ancestrais: set[str] = set()
        fronteira = set(ids)
        for _ in range(RAIO_MAXIMO):
            fronteira = {pai for filho in fronteira for pai in pais.get(filho, ())} - ancestrais - ids
            ancestrais |= fronteira
        return ancestrais


def filtrar_por_escopo(ids: Sequence[str], escopo: EscopoAtivo) -> tuple[str, ...]:
    """Mantém apenas o que está no escopo; um escopo vazio não filtra nada."""
    if escopo.esta_vazio:
        return tuple(ids)
    return tuple(id_no for id_no in ids if escopo.contem(id_no))


def _sanear_raio(raio: int) -> int:
    """Raio dentro dos limites: nunca negativo, nunca maior que o teto."""
    return max(0, min(raio, RAIO_MAXIMO))


def _montar_adjacencia(estado: GrafoEstado, tipos: frozenset[TipoAresta]) -> dict[str, set[str]]:
    """Vizinhança não-direcionada restrita aos tipos de aresta informados."""
    adjacencia: dict[str, set[str]] = {}
    for aresta in estado.arestas.values():
        if aresta.tipo not in tipos:
            continue
        adjacencia.setdefault(aresta.origem_id, set()).add(aresta.destino_id)
        adjacencia.setdefault(aresta.destino_id, set()).add(aresta.origem_id)
    return adjacencia


def _montar_pais_por_contencao(estado: GrafoEstado) -> dict[str, set[str]]:
    """Para cada nó, quem o contém diretamente."""
    pais: dict[str, set[str]] = {}
    for aresta in estado.arestas.values():
        if aresta.tipo not in ARESTAS_DE_CONTENCAO:
            continue
        pais.setdefault(aresta.destino_id, set()).add(aresta.origem_id)
    return pais


def _eh_tarefa_aberta(no: NoGrafo) -> bool:
    """Uma Task fora do estado concluído segue pedindo trabalho de alguém."""
    if no.tipo != TipoNo.TASK:
        return False
    return str(no.obter_propriedade("status", StatusTask.PENDENTE.value)) != StatusTask.CONCLUIDO.value


def _eh_questao_aberta(no: NoGrafo) -> bool:
    """Uma Question sem resposta trava trabalho e é semente do escopo ativo."""
    if no.tipo != TipoNo.QUESTION:
        return False
    return no.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value
