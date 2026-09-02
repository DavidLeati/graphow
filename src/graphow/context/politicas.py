"""Políticas de extração de subgrafo por papel (Behavior-Guided Progressive Disclosure).

Cada política parte do nó alvo e caminha pelo grafo. Nenhuma devolve "todos os nós
de um tipo": esse era o comportamento que consumia o orçamento com material sem
relação alguma com a tarefa em mãos. Ver auditoria F-08.
"""

from abc import ABC, abstractmethod

from graphow.core.models import NoGrafo
from graphow.core.types import StatusQuestion, TipoAresta, TipoNo
from graphow.context.exploracao import DirecaoTravessia, ExploradorSubgrafo, PedidoExploracao
from graphow.context.secoes import (
    PrioridadeRetencao,
    RecorteContexto,
    SecaoContexto,
    formatar_no_com_propriedades,
    montar_secao_de_nos,
)
from graphow.context.substituicao import montar_secao_de_decisoes
from graphow.context.vizinhanca import montar_secao_de_vizinhos
from graphow.projection.graph_view import GrafoView

ARESTAS_DE_HIERARQUIA: frozenset[TipoAresta] = frozenset({TipoAresta.DECOMPOE, TipoAresta.PRODUZ})
ARESTAS_DE_PROVENIENCIA: frozenset[TipoAresta] = frozenset(
    {TipoAresta.DERIVA_DE, TipoAresta.SUBSTITUI, TipoAresta.JUSTIFICA}
)


class PoliticaContexto(ABC):
    """Contrato abstrato para políticas de seleção de contexto."""

    @abstractmethod
    def extrair_recorte(self, id_alvo: str, view: GrafoView) -> RecorteContexto:
        """Monta o recorte de contexto centrado no nó alvo."""
        raise NotImplementedError


class PoliticaBase(PoliticaContexto):
    """Peças comuns a todas as políticas: restrições, bloqueios e vizinhança."""

    def extrair_recorte(self, id_alvo: str, view: GrafoView) -> RecorteContexto:
        """Monta o recorte combinando as seções universais com as do papel."""
        alvo = view.obter_no(id_alvo)
        if alvo is None:
            raise KeyError(id_alvo)
        explorador = ExploradorSubgrafo(view)
        secoes = self._secoes_universais(alvo, view, explorador) + self._secoes_do_papel(
            alvo, view, explorador
        )
        return RecorteContexto(alvo=alvo, secoes=secoes)

    @abstractmethod
    def _secoes_do_papel(
        self,
        alvo: NoGrafo,
        view: GrafoView,
        explorador: ExploradorSubgrafo,
    ) -> tuple[SecaoContexto, ...]:
        """Seções específicas do papel que a política representa."""
        raise NotImplementedError

    def _secoes_universais(
        self,
        alvo: NoGrafo,
        view: GrafoView,
        explorador: ExploradorSubgrafo,
    ) -> tuple[SecaoContexto, ...]:
        """Restrições que escopam o alvo, dúvidas que o travam e vizinhos expansíveis."""
        return (
            self._secao_restricoes(alvo, explorador),
            self._secao_bloqueios(alvo, view),
            self._secao_vizinhos(alvo, view),
        )

    def _secao_restricoes(self, alvo: NoGrafo, explorador: ExploradorSubgrafo) -> SecaoContexto:
        """Constraints que escopam o alvo ou algum de seus ancestrais hierárquicos."""
        restricoes = self._coletar_restricoes(alvo, explorador)
        return SecaoContexto(
            titulo="Restricoes Inviolaveis",
            linhas=tuple(formatar_no_com_propriedades(no) for no in restricoes),
            ordem_exibicao=1,
            prioridade_retencao=PrioridadeRetencao.RESTRICOES,
            ids_incluidos=tuple(no.id for no in restricoes),
        )

    def _coletar_restricoes(self, alvo: NoGrafo, explorador: ExploradorSubgrafo) -> tuple[NoGrafo, ...]:
        """Reúne as constraints do alvo e as herdadas dos ancestrais."""
        ancestrais = explorador.coletar_alcancaveis(
            PedidoExploracao(
                id_alvo=alvo.id,
                tipos_de_aresta=ARESTAS_DE_HIERARQUIA,
                direcao=DirecaoTravessia.ENTRADA,
            )
        )
        alvos_de_escopo = (alvo,) + ancestrais
        encontradas = [
            restricao
            for no in alvos_de_escopo
            for restricao in explorador.coletar_origens_diretas(no.id, TipoAresta.ESCOPA)
        ]
        return self._sem_repeticao(encontradas)

    def _secao_bloqueios(self, alvo: NoGrafo, view: GrafoView) -> SecaoContexto:
        """Questions abertas que impedem a conclusão do alvo."""
        bloqueantes = view.obter_questoes_bloqueantes(alvo.id)
        return montar_secao_de_nos(
            "Duvidas Abertas Que Bloqueiam Este No",
            bloqueantes,
            (2, PrioridadeRetencao.BLOQUEIOS),
        )

    def _secao_vizinhos(self, alvo: NoGrafo, view: GrafoView) -> SecaoContexto:
        """Vizinhos a um salto, ordenados por relevância e cortáveis por tipo."""
        return montar_secao_de_vizinhos(view.obter_vizinhos_1_salto(alvo.id))

    def _sem_repeticao(self, nos: list[NoGrafo]) -> tuple[NoGrafo, ...]:
        """Remove duplicatas preservando a ordem de descoberta."""
        vistos: dict[str, NoGrafo] = {}
        for no in nos:
            vistos.setdefault(no.id, no)
        return tuple(vistos.values())

    def _filtrar_por_tipo(self, nos: tuple[NoGrafo, ...], tipo: TipoNo) -> tuple[NoGrafo, ...]:
        """Seleciona apenas os nós do tipo informado."""
        return tuple(no for no in nos if no.tipo == tipo)


class PoliticaExecutor(PoliticaBase):
    """Executor: a tarefa em mãos, as decisões que a governam e as evidências delas."""

    def _secoes_do_papel(
        self,
        alvo: NoGrafo,
        view: GrafoView,
        explorador: ExploradorSubgrafo,
    ) -> tuple[SecaoContexto, ...]:
        """Decisões e evidências alcançáveis pela proveniência do alvo."""
        vizinhanca = explorador.coletar_alcancaveis(
            PedidoExploracao(
                id_alvo=alvo.id,
                tipos_de_aresta=ARESTAS_DE_PROVENIENCIA | ARESTAS_DE_HIERARQUIA,
                direcao=DirecaoTravessia.AMBAS,
                saltos_maximos=2,
            )
        )
        return (
            montar_secao_de_decisoes(
                self._filtrar_por_tipo(vizinhanca, TipoNo.DECISION),
                view,
                (3, PrioridadeRetencao.DECISOES),
            ),
            montar_secao_de_nos(
                "Evidencias Relacionadas",
                self._filtrar_por_tipo(vizinhanca, TipoNo.EVIDENCE),
                (4, PrioridadeRetencao.APOIO),
            ),
        )


class PoliticaPlanejador(PoliticaBase):
    """Planejador: a decomposição do alvo e as dúvidas abertas dentro dela."""

    def _secoes_do_papel(
        self,
        alvo: NoGrafo,
        view: GrafoView,
        explorador: ExploradorSubgrafo,
    ) -> tuple[SecaoContexto, ...]:
        """Subárvore de decomposição do alvo, com decisões e pendências locais."""
        descendentes = explorador.coletar_alcancaveis(
            PedidoExploracao(
                id_alvo=alvo.id,
                tipos_de_aresta=ARESTAS_DE_HIERARQUIA,
                direcao=DirecaoTravessia.SAIDA,
            )
        )
        return (
            montar_secao_de_nos(
                "Decomposicao Deste Objetivo",
                self._filtrar_por_tipo(descendentes, TipoNo.TASK),
                (3, PrioridadeRetencao.DECISOES),
            ),
            montar_secao_de_nos(
                "Duvidas Abertas Na Decomposicao",
                self._questoes_abertas(descendentes),
                (4, PrioridadeRetencao.BLOQUEIOS),
            ),
        )

    def _questoes_abertas(self, nos: tuple[NoGrafo, ...]) -> tuple[NoGrafo, ...]:
        """Filtra as Questions que seguem sem resposta."""
        return tuple(
            no
            for no in self._filtrar_por_tipo(nos, TipoNo.QUESTION)
            if no.obter_propriedade("status", StatusQuestion.ABERTA.value) == StatusQuestion.ABERTA.value
        )


class PoliticaRevisor(PoliticaBase):
    """Revisor: os artefatos derivados do alvo e as evidências que os sustentam."""

    def _secoes_do_papel(
        self,
        alvo: NoGrafo,
        view: GrafoView,
        explorador: ExploradorSubgrafo,
    ) -> tuple[SecaoContexto, ...]:
        """Artefatos e evidências ligados ao alvo por proveniência."""
        vizinhanca = explorador.coletar_alcancaveis(
            PedidoExploracao(
                id_alvo=alvo.id,
                tipos_de_aresta=ARESTAS_DE_PROVENIENCIA | frozenset({TipoAresta.CONTRADIZ}),
                direcao=DirecaoTravessia.AMBAS,
                saltos_maximos=2,
            )
        )
        return (
            montar_secao_de_nos(
                "Artefatos Sob Revisao",
                self._filtrar_por_tipo(vizinhanca, TipoNo.ARTIFACT),
                (3, PrioridadeRetencao.DECISOES),
            ),
            montar_secao_de_nos(
                "Evidencias Disponiveis",
                self._filtrar_por_tipo(vizinhanca, TipoNo.EVIDENCE),
                (4, PrioridadeRetencao.APOIO),
            ),
        )
