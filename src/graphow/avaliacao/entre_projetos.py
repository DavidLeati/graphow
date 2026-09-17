"""Braço entre projetos: um aprendizado do primeiro projeto chega à tarefa do segundo, e a que custo.

Com o grafo, a tarefa do segundo projeto recebe a seção de aprendizados na
própria vista, sem que o agente conheça a palavra certa. Os contrafactuais são
os dois caminhos que restariam sem ela: despejar o primeiro projeto inteiro, ou
buscar às cegas com a primeira palavra do título da tarefa. A taxa de acerto
diz, por mecanismo, o que herança e léxico alcançam e o que só um índice
semântico alcançaria.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import json

from graphow.avaliacao.cenario_entre_projetos import TAREFAS_ENTRE_PROJETOS, TarefaEntreProjetos
from graphow.avaliacao.tarefas_gravadas import ID_PROJETO
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.token_counter import ContadorTokens
from graphow.core.ontologia import ARESTAS_DE_CONTENCAO
from graphow.core.types import PapelAutor
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import (
    LIMITE_MAXIMO_DE_RESULTADOS,
    CriterioBusca,
    palavras_significativas,
)

ORCAMENTO_ENTRE_PROJETOS: int = 1500
PROFUNDIDADE_MAXIMA: int = 8


@dataclass(frozen=True)
class MedicaoEntreProjetos:
    """Uma tarefa do segundo projeto: o aprendizado chegou, e a que custo em cada braço."""

    id_tarefa: str
    id_aprendizado_esperado: str
    mecanismo_esperado: str
    chegou: bool
    tokens_pela_vista: int
    tokens_despejo_do_primeiro_projeto: int
    tokens_busca_cega: int


@dataclass(frozen=True)
class RelatorioEntreProjetos:
    """As medições do braço e o índice semântico com que foram feitas."""

    medicoes: tuple[MedicaoEntreProjetos, ...]
    indice_semantico: str

    @property
    def acertos(self) -> int:
        """Quantas tarefas receberam o aprendizado de que dependiam."""
        return sum(1 for medicao in self.medicoes if medicao.chegou)

    @property
    def taxa_de_acerto(self) -> float:
        """Fração de tarefas atendidas, entre 0 e 1."""
        return self.acertos / len(self.medicoes) if self.medicoes else 0.0

    def formatar(self) -> tuple[str, ...]:
        """Linhas legíveis do braço, prontas para o console."""
        cabecalho = (
            "",
            "=== ENTRE PROJETOS: O APRENDIZADO CHEGA A TAREFA DO OUTRO PROJETO? ===",
            f"Indice semantico: {self.indice_semantico}",
        )
        linhas = tuple(
            f"  [{medicao.id_tarefa}] esperado={medicao.id_aprendizado_esperado} ({medicao.mecanismo_esperado}) "
            f"chegou={'sim' if medicao.chegou else 'nao'} | vista={medicao.tokens_pela_vista} tokens | "
            f"despejo do primeiro projeto={medicao.tokens_despejo_do_primeiro_projeto} | "
            f"busca cega={medicao.tokens_busca_cega}"
            for medicao in self.medicoes
        )
        rodape = (f"Taxa de acerto: {self.acertos}/{len(self.medicoes)} ({self.taxa_de_acerto * 100:.1f}%)",)
        return cabecalho + linhas + rodape


class MedidorEntreProjetos:
    """Mede, por tarefa do segundo projeto, a vista contra o despejo e a busca cega."""

    def __init__(self, kernel: WriteKernel, materializador: MaterializadorContexto | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()

    def medir_todas(self, tarefas: Sequence[TarefaEntreProjetos] = TAREFAS_ENTRE_PROJETOS) -> RelatorioEntreProjetos:
        """Mede cada tarefa gravada do segundo projeto sobre a mesma projeção."""
        view = self._kernel.obter_view()
        despejo = self._custo_do_despejo(ID_PROJETO, view)
        return RelatorioEntreProjetos(
            medicoes=tuple(self._medir(tarefa, view, despejo) for tarefa in tarefas),
            indice_semantico=self._materializador.indice_semantico.descrever(),
        )

    def _medir(self, tarefa: TarefaEntreProjetos, view: GrafoView, despejo: int) -> MedicaoEntreProjetos:
        """A vista da tarefa entregou o aprendizado esperado, e quanto custou cada caminho."""
        requisicao = RequisicaoVista(
            id_alvo=tarefa.id, papel=PapelAutor.PLANEJADOR, orcamento_tokens=ORCAMENTO_ENTRE_PROJETOS
        )
        vista = self._materializador.materializar(requisicao, view)
        return MedicaoEntreProjetos(
            id_tarefa=tarefa.id,
            id_aprendizado_esperado=tarefa.id_aprendizado_esperado,
            mecanismo_esperado=tarefa.mecanismo_esperado,
            chegou=tarefa.id_aprendizado_esperado in vista.nos_incluidos,
            tokens_pela_vista=vista.tokens_estimados,
            tokens_despejo_do_primeiro_projeto=despejo,
            tokens_busca_cega=self._custo_da_busca_cega(tarefa, view),
        )

    def _custo_da_busca_cega(self, tarefa: TarefaEntreProjetos, view: GrafoView) -> int:
        """Buscar com a primeira palavra significativa do título, sem limite: o que o agente faria às cegas."""
        palavras = sorted(palavras_significativas(tarefa.titulo))
        termo = palavras[0] if palavras else tarefa.titulo
        resultado = view.buscar_ranqueado(CriterioBusca(termo=termo, limite=LIMITE_MAXIMO_DE_RESULTADOS))
        return ContadorTokens.estimar_objeto(resultado.em_dicionario())

    def _custo_do_despejo(self, id_projeto: str, view: GrafoView) -> int:
        """Custo de ler o primeiro projeto inteiro, serializado, sem divulgação progressiva."""
        ids = self._coletar_subgrafo(id_projeto, view)
        despejo = [
            {
                "id": no.id,
                "tipo": no.tipo.value,
                "rotulo": no.rotulo,
                "propriedades": dict(sorted(no.propriedades.items())),
            }
            for no in (view.obter_no(id_no) for id_no in ids)
            if no is not None
        ]
        return ContadorTokens.estimar_texto(json.dumps(despejo, ensure_ascii=False, sort_keys=True))

    def _coletar_subgrafo(self, raiz: str, view: GrafoView) -> tuple[str, ...]:
        """Tudo que pende da raiz por contenção, em ordem estável."""
        visitados: set[str] = {raiz}
        fronteira: list[str] = [raiz]
        for _ in range(PROFUNDIDADE_MAXIMA):
            if not fronteira:
                break
            fronteira = self._expandir(fronteira, view, visitados)
        return tuple(sorted(visitados))

    def _expandir(self, fronteira: list[str], view: GrafoView, visitados: set[str]) -> list[str]:
        """Um nível de descendentes por arestas de contenção."""
        proxima: list[str] = []
        for id_no in fronteira:
            proxima.extend(self._filhos_novos(id_no, view, visitados))
        return proxima

    def _filhos_novos(self, id_no: str, view: GrafoView, visitados: set[str]) -> tuple[str, ...]:
        """Filhos por contenção ainda não visitados, marcando-os como vistos."""
        novos: list[str] = []
        for aresta in view.obter_arestas_saida(id_no):
            if aresta.tipo not in ARESTAS_DE_CONTENCAO or aresta.destino_id in visitados:
                continue
            visitados.add(aresta.destino_id)
            novos.append(aresta.destino_id)
        return tuple(novos)
