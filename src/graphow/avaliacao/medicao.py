"""Medição de tokens por tarefa, com e sem o recorte do grafo.

O braço "com grafo" é a vista materializada que o agente de fato recebe. O braço
"sem grafo" é o contrafactual honesto do que ele precisaria ler sem divulgação
progressiva: o subgrafo inteiro da sessão, serializado. A diferença entre os dois
é a única parte da métrica que se mede de forma determinística, sem um modelo
no circuito — e é exatamente a parte que o ADR afirmava sem medir. Ver A-15.

O que esta medição não cobre está declarado em `RelatorioDeAvaliacao.limites`:
taxa de patch rejeitado e sucesso de tarefa dependem de rodar um agente real.
"""

from dataclasses import dataclass
import json

from graphow.avaliacao.tarefas_gravadas import ID_SESSAO, TAREFAS_GRAVADAS, TarefaGravada
from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.token_counter import ContadorTokens
from graphow.core.types import TipoAresta
from graphow.projection.graph_view import GrafoView
from graphow.kernel.write_kernel import WriteKernel

ARESTAS_DE_ALCANCE_DA_SESSAO: frozenset[TipoAresta] = frozenset(
    {TipoAresta.PRODUZ, TipoAresta.DECOMPOE, TipoAresta.CONTEM}
)
PROFUNDIDADE_MAXIMA: int = 8


@dataclass(frozen=True)
class MedicaoDaTarefa:
    """Custo de contexto e esforço humano de uma tarefa gravada."""

    id_tarefa: str
    tokens_com_grafo: int
    tokens_sem_grafo: int
    intervencoes_humanas: int
    concluida: bool

    @property
    def reducao(self) -> float:
        """Fração do contexto poupada pelo recorte, entre 0 e 1."""
        if self.tokens_sem_grafo == 0:
            return 0.0
        poupado = self.tokens_sem_grafo - self.tokens_com_grafo
        return max(0.0, poupado / self.tokens_sem_grafo)


class MedidorDeTarefas:
    """Executa a medição das dez tarefas gravadas sobre um cenário montado."""

    def __init__(self, kernel: WriteKernel, materializador: MaterializadorContexto | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()

    def medir_todas(self) -> tuple[MedicaoDaTarefa, ...]:
        """Mede cada tarefa do corpus contra o mesmo cenário gravado."""
        view = self._kernel.obter_view()
        custo_sem_grafo = self._medir_dump_da_sessao(view)
        return tuple(self._medir(tarefa, view, custo_sem_grafo) for tarefa in TAREFAS_GRAVADAS)

    def _medir(
        self,
        tarefa: TarefaGravada,
        view: GrafoView,
        custo_sem_grafo: int,
    ) -> MedicaoDaTarefa:
        """Compara a vista materializada com o despejo integral da sessão."""
        requisicao = RequisicaoVista(
            id_alvo=tarefa.id, papel=tarefa.papel, orcamento_tokens=tarefa.orcamento_tokens
        )
        vista = self._materializador.materializar(requisicao, view)
        return MedicaoDaTarefa(
            id_tarefa=tarefa.id,
            tokens_com_grafo=vista.tokens_estimados,
            tokens_sem_grafo=custo_sem_grafo,
            intervencoes_humanas=self._contar_intervencoes(tarefa, view),
            concluida=tarefa.concluida,
        )

    def _contar_intervencoes(self, tarefa: TarefaGravada, view: GrafoView) -> int:
        """Conta as dúvidas desta tarefa que exigiram uma resposta humana."""
        bloqueios = view.obter_arestas_entrada(tarefa.id, TipoAresta.BLOQUEIA)
        respondidas = [
            aresta
            for aresta in bloqueios
            if self._tem_resposta_humana(view, aresta.origem_id)
        ]
        return len(respondidas)

    def _tem_resposta_humana(self, view: GrafoView, id_questao: str) -> bool:
        """Uma dúvida só conta como intervenção quando alguém a respondeu."""
        no = view.obter_no(id_questao)
        return no is not None and bool(no.obter_propriedade("respondida_por", ""))

    def _medir_dump_da_sessao(self, view: GrafoView) -> int:
        """Custo de ler o subgrafo inteiro da sessão, sem divulgação progressiva."""
        alcancados = self._coletar_subgrafo_da_sessao(view)
        despejo = [
            {
                "id": no.id,
                "tipo": no.tipo.value,
                "rotulo": no.rotulo,
                "propriedades": dict(sorted(no.propriedades.items())),
            }
            for no in alcancados
        ]
        return ContadorTokens.estimar_texto(json.dumps(despejo, ensure_ascii=False, sort_keys=True))

    def _coletar_subgrafo_da_sessao(self, view: GrafoView) -> tuple:
        """Percorre a sessão em largura, reunindo tudo o que ela alcança."""
        visitados: set[str] = {ID_SESSAO}
        fronteira: list[str] = [ID_SESSAO]
        for _ in range(PROFUNDIDADE_MAXIMA):
            if not fronteira:
                break
            fronteira = self._expandir(fronteira, view, visitados)
        nos = (view.obter_no(id_no) for id_no in sorted(visitados))
        return tuple(no for no in nos if no is not None)

    def _expandir(self, fronteira: list[str], view: GrafoView, visitados: set[str]) -> list[str]:
        """Expande um nível de descendentes da sessão."""
        proxima: list[str] = []
        for id_no in fronteira:
            proxima.extend(self._filhos_novos(id_no, view, visitados))
        return proxima

    def _filhos_novos(self, id_no: str, view: GrafoView, visitados: set[str]) -> tuple[str, ...]:
        """Filhos ainda não visitados, por arestas de composição do trabalho."""
        novos: list[str] = []
        for aresta in view.obter_arestas_saida(id_no):
            if aresta.tipo not in ARESTAS_DE_ALCANCE_DA_SESSAO or aresta.destino_id in visitados:
                continue
            visitados.add(aresta.destino_id)
            novos.append(aresta.destino_id)
        return tuple(novos)
