"""Braço de retomada: quanto custa recuperar decisões e achados de uma sessão encerrada.

Com o grafo, o agente lê a abertura da vista da sessão: o fechamento
determinístico e a condensação em prosa, que é o que responde "o que ficou
decidido e por quê". Sem ele, o contrafactual honesto é o que restava ao agente
quando a vista cortava 33 Evidence com "use buscar": expandir a sessão para
descobrir o que ela produziu e depois expandir cada Decision e cada Evidence,
uma chamada por nó. A medição também confere se a abertura entregou de fato o
que promete: toda decisão vigente e a condensação.
"""

from dataclasses import dataclass

from graphow.avaliacao.tarefas_gravadas import ID_SESSAO
from graphow.context.fechamento import localizar_condensacao, montar_secao_de_fechamento
from graphow.context.materializer import MaterializadorContexto
from graphow.context.renderizacao import RenderizadorContexto, TextoRenderizado
from graphow.context.secoes import RecorteContexto
from graphow.context.token_counter import ContadorTokens
from graphow.core.exceptions import ErroEntidadeNaoEncontrada
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.graph_view import GrafoView

ORCAMENTO_DA_RETOMADA: int = 1500
PAPEL_DA_MEDICAO: PapelAutor = PapelAutor.PLANEJADOR
TIPOS_DE_CONHECIMENTO: frozenset[TipoNo] = frozenset({TipoNo.DECISION, TipoNo.EVIDENCE})


@dataclass(frozen=True)
class MedicaoDeRetomada:
    """Custo de retomar uma sessão encerrada, pela abertura da vista e nó a nó."""

    id_sessao: str
    tokens_pela_vista: int
    tokens_no_a_no: int
    nos_lidos_um_a_um: int
    decisoes_vigentes: int
    decisoes_entregues: int
    condensacao_entregue: bool

    @property
    def reducao(self) -> float:
        """Fração do contexto poupada pela abertura da vista, entre 0 e 1."""
        if self.tokens_no_a_no == 0:
            return 0.0
        return max(0.0, (self.tokens_no_a_no - self.tokens_pela_vista) / self.tokens_no_a_no)

    @property
    def cobertura_completa(self) -> bool:
        """A abertura só vale o que economiza se entregar toda decisão vigente e a condensação."""
        return self.decisoes_entregues == self.decisoes_vigentes and self.condensacao_entregue


class MedidorDeRetomada:
    """Compara a abertura da vista da sessão encerrada com a leitura nó a nó."""

    def __init__(self, kernel: WriteKernel, materializador: MaterializadorContexto | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()
        self._renderizador: RenderizadorContexto = RenderizadorContexto()

    def medir(self, id_sessao: str = ID_SESSAO, orcamento: int = ORCAMENTO_DA_RETOMADA) -> MedicaoDeRetomada:
        """Mede os dois braços sobre a mesma projeção."""
        view = self._kernel.obter_view()
        sessao = view.obter_no(id_sessao)
        if sessao is None:
            raise ErroEntidadeNaoEncontrada(f"Sessao '{id_sessao}' nao existe", {"id_sessao": id_sessao})
        abertura = self._renderizar_abertura(sessao, view, orcamento)
        vigentes = self._decisoes_vigentes(id_sessao, view)
        condensacao = localizar_condensacao(id_sessao, view)
        nos = self._nos_de_conhecimento(id_sessao, view)
        return MedicaoDeRetomada(
            id_sessao=id_sessao,
            tokens_pela_vista=abertura.tokens_estimados,
            tokens_no_a_no=self._custo_no_a_no(id_sessao, nos, view),
            nos_lidos_um_a_um=len(nos),
            decisoes_vigentes=len(vigentes),
            decisoes_entregues=sum(1 for id_decisao in vigentes if id_decisao in abertura.ids_incluidos),
            condensacao_entregue=condensacao is not None and condensacao.id in abertura.ids_incluidos,
        )

    def _renderizar_abertura(self, sessao: NoGrafo, view: GrafoView, orcamento: int) -> TextoRenderizado:
        """O cabeçalho da vista e a seção de fechamento: o que o agente lê para retomar."""
        recorte = RecorteContexto(alvo=sessao, secoes=(montar_secao_de_fechamento(sessao, view),))
        return self._renderizador.renderizar(recorte, orcamento)

    def _decisoes_vigentes(self, id_sessao: str, view: GrafoView) -> tuple[str, ...]:
        """As decisões que o fechamento determinístico declara em vigor."""
        resumo = view.obter_resumo(id_sessao)
        return resumo.fechamento.decisoes_vigentes if resumo is not None else ()

    def _custo_no_a_no(self, id_sessao: str, nos: tuple[NoGrafo, ...], view: GrafoView) -> int:
        """Expandir a sessão para descobrir os nós e depois cada Decision e Evidence.

        A expansão da sessão entra na conta porque sem a abertura da vista o
        agente não sabe quais identificadores pedir: descobrir custa tokens.
        """
        descoberta = ContadorTokens.estimar_objeto(self._materializador.expandir_no(id_sessao, view))
        leituras = sum(
            ContadorTokens.estimar_objeto(self._materializador.expandir_no(no.id, view)) for no in nos
        )
        return descoberta + leituras

    def _nos_de_conhecimento(self, id_sessao: str, view: GrafoView) -> tuple[NoGrafo, ...]:
        """Decisions e Evidences produzidas pela sessão, em ordem estável."""
        produzidos = (
            view.obter_no(aresta.destino_id)
            for aresta in view.obter_arestas_saida(id_sessao, TipoAresta.PRODUZ)
        )
        selecionados = [no for no in produzidos if no is not None and no.tipo in TIPOS_DE_CONHECIMENTO]
        return tuple(sorted(selecionados, key=lambda no: no.id))
