"""Motor de materialização de vistas de contexto com orçamento de tokens."""

from dataclasses import dataclass, field
from typing import Any

from graphow.context.aprendizados_aplicaveis import IndiceSemantico, IndiceSemanticoNulo
from graphow.context.politicas import (
    PoliticaContexto,
    PoliticaExecutor,
    PoliticaPlanejador,
    PoliticaRevisor,
)
from graphow.context.renderizacao import RenderizadorContexto, TextoRenderizado
from graphow.context.secoes import filtrar_propriedades_de_dominio
from graphow.core.exceptions import ErroEntidadeNaoEncontrada
from graphow.core.types import PapelAutor
from graphow.projection.graph_view import GrafoView
from graphow.projection.working_set import RAIO_PADRAO, EscopoAtivo

ORCAMENTO_TOKENS_PADRAO: int = 1500
TITULO_SECAO_VIZINHOS: str = "Vizinhos a 1 Salto"


@dataclass(frozen=True)
class RequisicaoVista:
    """DTO imutável para solicitação de materialização de contexto.

    `escopo_ativo` é opcional e desligado por padrão. Podar o que está longe do
    trabalho aberto ajuda a tela do humano, que ele reabre quando quiser; para o
    agente, esconder Decision e Evidence por default é o oposto do que esses nós
    existem para fazer — eles são a memória que impede re-decidir. Quem quiser o
    recorte pede por ele.
    """

    id_alvo: str
    papel: PapelAutor
    orcamento_tokens: int = ORCAMENTO_TOKENS_PADRAO
    escopo_ativo: bool = False
    raio_do_escopo: int = RAIO_PADRAO


@dataclass(frozen=True)
class VistaMaterializada:
    """Recorte de contexto imutável materializado com orçamento estrito de tokens."""

    id_alvo: str
    papel: PapelAutor
    conteudo_formatado: str
    tokens_estimados: int
    orcamento_tokens: int
    nos_incluidos: tuple[str, ...] = field(default_factory=tuple)
    vizinhos_expansiveis: tuple[str, ...] = field(default_factory=tuple)


class MaterializadorContexto:
    """Responsável por sintetizar subgrafos em formato ótimo de tokens para agentes."""

    POLITICAS_POR_PAPEL: dict[PapelAutor, PoliticaContexto] = {
        PapelAutor.PLANEJADOR: PoliticaPlanejador(),
        PapelAutor.EXECUTOR: PoliticaExecutor(),
        PapelAutor.REVISOR: PoliticaRevisor(),
        PapelAutor.HUMANO: PoliticaPlanejador(),
    }

    def __init__(
        self,
        renderizador: RenderizadorContexto | None = None,
        indice_semantico: IndiceSemantico | None = None,
    ) -> None:
        self._renderizador: RenderizadorContexto = renderizador or RenderizadorContexto()
        # Injetável e nulo por padrão, como a telemetria: sem configurar, a
        # recuperação semântica não custa nada e não traz dependência.
        self._indice_semantico: IndiceSemantico = indice_semantico or IndiceSemanticoNulo()

    @property
    def indice_semantico(self) -> IndiceSemantico:
        """O índice em uso, para o relatório de avaliação declarar com o que mediu."""
        return self._indice_semantico

    def materializar(self, requisicao: RequisicaoVista, view: GrafoView) -> VistaMaterializada:
        """Gera a vista mais completa que couber no orçamento de tokens do pedido."""
        no_alvo = view.obter_no(requisicao.id_alvo)
        if no_alvo is None:
            raise ErroEntidadeNaoEncontrada(
                f"Nó alvo '{requisicao.id_alvo}' não encontrado", {"id_alvo": requisicao.id_alvo}
            )
        politica = self.POLITICAS_POR_PAPEL.get(requisicao.papel, PoliticaExecutor())
        escopo = self._resolver_escopo(requisicao, view)
        recorte = politica.extrair_recorte(
            requisicao.id_alvo, view, escopo, indice_semantico=self._indice_semantico
        )
        texto = self._renderizador.renderizar(recorte, requisicao.orcamento_tokens)
        return self._montar_vista(requisicao, texto)

    def _resolver_escopo(self, requisicao: RequisicaoVista, view: GrafoView) -> EscopoAtivo | None:
        """Calcula o recorte ativo apenas quando ele foi pedido."""
        if not requisicao.escopo_ativo:
            return None
        return view.calcular_escopo_ativo(requisicao.raio_do_escopo)

    def _montar_vista(self, requisicao: RequisicaoVista, texto: TextoRenderizado) -> VistaMaterializada:
        """Empacota o texto renderizado no DTO de resposta da ferramenta."""
        return VistaMaterializada(
            id_alvo=requisicao.id_alvo,
            papel=requisicao.papel,
            conteudo_formatado=texto.conteudo,
            tokens_estimados=texto.tokens_estimados,
            orcamento_tokens=requisicao.orcamento_tokens,
            nos_incluidos=texto.ids_incluidos,
            vizinhos_expansiveis=self._extrair_vizinhos_citados(texto),
        )

    def _extrair_vizinhos_citados(self, texto: TextoRenderizado) -> tuple[str, ...]:
        """Só anuncia como expansível o que o texto realmente entregou ao agente.

        Antes, a lista vinha preenchida mesmo quando a seção de vizinhos havia sido
        cortada pelo orçamento: a API afirmava uma coisa e o conteúdo mostrava outra.
        """
        for titulo, ids in texto.ids_por_secao.items():
            if TITULO_SECAO_VIZINHOS in titulo:
                return ids
        return ()

    def expandir_no(self, id_no: str, view: GrafoView) -> dict[str, Any]:
        """Expansão detalhada sob demanda de um nó específico."""
        no = view.obter_no(id_no)
        if no is None:
            raise ErroEntidadeNaoEncontrada(f"Nó '{id_no}' não encontrado para expansão", {"id_no": id_no})
        return {
            "id": no.id,
            "tipo": no.tipo.value,
            "rotulo": no.rotulo,
            "criado_em": no.metadados.criado_em,
            "atualizado_em": no.metadados.atualizado_em,
            "seq_criacao": no.ordem.seq_criacao,
            "seq_atualizacao": no.ordem.seq_atualizacao,
            "propriedades": filtrar_propriedades_de_dominio(no.propriedades),
            "arestas_saida": [
                {"id": a.id, "destino": a.destino_id, "tipo": a.tipo.value}
                for a in view.obter_arestas_saida(id_no)
            ],
            "arestas_entrada": [
                {"id": a.id, "origem": a.origem_id, "tipo": a.tipo.value}
                for a in view.obter_arestas_entrada(id_no)
            ],
        }
