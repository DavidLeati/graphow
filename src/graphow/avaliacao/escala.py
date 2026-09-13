"""Medição de escala sobre o grafo que estiver aberto, não sobre um cenário gravado.

O corpus de `tarefas_gravadas` é hermético de propósito: ele monta o próprio
grafo para que a métrica de tokens por tarefa seja comparável entre execuções.
Esta medição responde outra pergunta — "o meu grafo, do tamanho que ele está
hoje, cabe na tela e no orçamento?" — e por isso corre contra o banco real.

Ela existe para que a decisão de recortar tenha número antes e depois, em vez de
impressão. Os três eixos são os que doíam: o tamanho do payload do canvas, o
custo de descobrir onde há trabalho aberto, e o custo de uma busca sem limite.
"""

from dataclasses import dataclass, field
import json

from graphow.context.materializer import MaterializadorContexto, RequisicaoVista
from graphow.context.token_counter import ContadorTokens
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoNo
from graphow.projection.graph_view import GrafoView
from graphow.projection.ranking_busca import CriterioBusca
from graphow.kernel.write_kernel import WriteKernel
from graphow.web.colapso_visual import OpcoesDeRecorteVisual
from graphow.web.conversao_requisicoes import serializar_canvas
from graphow.web.dto import DadosCanvasVisual
from graphow.web.rest_canvas_controller import CanvasWebController

ORCAMENTO_DA_MEDICAO: int = 1500
PROFUNDIDADE_MAXIMA_DA_DESCIDA: int = 8
TERMOS_DE_SONDAGEM: tuple[str, ...] = ("dados", "modelo", "a")
TIPOS_DE_CONTAINER: tuple[TipoNo, ...] = (TipoNo.PROJETO, TipoNo.SETOR, TipoNo.SESSAO)


@dataclass(frozen=True)
class MedidaDeCanvas:
    """Peso do payload do canvas sob um recorte."""

    rotulo: str
    nos: int
    kilobytes: float


@dataclass(frozen=True)
class MedidaDeBusca:
    """Custo de uma busca, com e sem o limite de resultados."""

    termo: str
    total_encontrado: int
    tokens_sem_limite: int
    tokens_com_limite: int


@dataclass(frozen=True)
class RelatorioDeEscala:
    """Consolidação das três medidas que decidem se o grafo ainda cabe."""

    total_nos: int
    total_arestas: int
    canvas: tuple[MedidaDeCanvas, ...] = field(default_factory=tuple)
    tokens_da_varredura: int = 0
    tokens_do_caminho_guiado: int = 0
    passos_do_caminho_guiado: tuple[str, ...] = field(default_factory=tuple)
    buscas: tuple[MedidaDeBusca, ...] = field(default_factory=tuple)
    nos_orfaos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fator_de_reducao_da_navegacao(self) -> float:
        """Quantas vezes o caminho guiado é mais barato que a varredura cega."""
        if self.tokens_do_caminho_guiado == 0:
            return 0.0
        return self.tokens_da_varredura / self.tokens_do_caminho_guiado

    def formatar(self) -> tuple[str, ...]:
        """Linhas legíveis do relatório, prontas para o console."""
        return self._cabecalho() + self._linhas_de_canvas() + self._linhas_de_navegacao() + self._linhas_de_busca()

    def _cabecalho(self) -> tuple[str, ...]:
        """Tamanho do grafo e o que ficou fora de qualquer hierarquia."""
        return (
            "=== ESCALA DO GRAFO ABERTO ===",
            f"Nos: {self.total_nos} | Arestas: {self.total_arestas}",
            f"Nos fora de qualquer hierarquia: {len(self.nos_orfaos)}",
            "",
            "Payload do canvas por recorte:",
        )

    def _linhas_de_canvas(self) -> tuple[str, ...]:
        """Uma linha por recorte, com o peso que ele entrega ao navegador."""
        return tuple(
            f"  {medida.rotulo:26s} {medida.nos:4d} nos  {medida.kilobytes:8.1f} KB"
            for medida in self.canvas
        )

    def _linhas_de_navegacao(self) -> tuple[str, ...]:
        """Comparação entre varrer a hierarquia e descer guiado pelo rollup."""
        return (
            "",
            "Descobrir onde ha trabalho aberto:",
            f"  varredura de todos os conteineres  {self.tokens_da_varredura:6d} tokens",
            f"  caminho guiado pelo rollup         {self.tokens_do_caminho_guiado:6d} tokens"
            f"  ({self.fator_de_reducao_da_navegacao:.1f}x)",
            f"  passos: {' -> '.join(self.passos_do_caminho_guiado) or '(nenhum)'}",
            "",
            "Busca (termo: encontrados | tokens sem limite -> com limite):",
        )

    def _linhas_de_busca(self) -> tuple[str, ...]:
        """Uma linha por termo sondado, com o custo antes e depois do corte."""
        return tuple(
            f"  {busca.termo:10s} {busca.total_encontrado:4d} achados | "
            f"{busca.tokens_sem_limite:6d} -> {busca.tokens_com_limite:5d} tokens"
            for busca in self.buscas
        )


class MedidorDeEscala:
    """Roda as três medidas sobre a projeção do ramo informado."""

    def __init__(self, kernel: WriteKernel, materializador: MaterializadorContexto | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._materializador: MaterializadorContexto = materializador or MaterializadorContexto()

    def medir(self, ramo_id: str = "main") -> RelatorioDeEscala:
        """Consolida o relatório de escala do ramo."""
        view = self._kernel.obter_view(ramo_id)
        guiado, passos = self._medir_caminho_guiado(view)
        return RelatorioDeEscala(
            total_nos=view.total_nos,
            total_arestas=view.total_arestas,
            canvas=self._medir_canvas(ramo_id),
            tokens_da_varredura=self._medir_varredura(view),
            tokens_do_caminho_guiado=guiado,
            passos_do_caminho_guiado=passos,
            buscas=self._medir_buscas(view),
            nos_orfaos=view.indice_de_rollup.nos_orfaos,
        )

    def _medir_canvas(self, ramo_id: str) -> tuple[MedidaDeCanvas, ...]:
        """Pesa o payload do canvas sob cada recorte que a interface oferece."""
        controlador = CanvasWebController(self._kernel)
        recortes = (
            ("sem recorte", OpcoesDeRecorteVisual()),
            ("colapsado em setor", OpcoesDeRecorteVisual(colapsar_em="setor")),
            ("colapsado em sessao", OpcoesDeRecorteVisual(colapsar_em="sessao")),
            ("escopo ativo (raio 1)", OpcoesDeRecorteVisual(escopo_ativo=True, raio=1)),
            ("caminho critico", OpcoesDeRecorteVisual(caminho_critico=True)),
        )
        return tuple(
            self._pesar_canvas(rotulo, controlador.obter_canvas(ramo_id, opcoes=opcoes))
            for rotulo, opcoes in recortes
        )

    def _pesar_canvas(self, rotulo: str, dados: DadosCanvasVisual) -> MedidaDeCanvas:
        """Serializa o payload e mede o que de fato atravessaria a rede."""
        texto = json.dumps(serializar_canvas(dados), ensure_ascii=False)
        return MedidaDeCanvas(
            rotulo=rotulo,
            nos=dados.total_nos,
            kilobytes=len(texto.encode("utf-8")) / 1024,
        )

    def _medir_varredura(self, view: GrafoView) -> int:
        """Custo de abrir a vista de todo contêiner do grafo, sem orientação."""
        return sum(
            self._tokens_da_vista(view, no.id) for no in self._listar_containers(view)
        )

    def _medir_caminho_guiado(self, view: GrafoView) -> tuple[int, tuple[str, ...]]:
        """Custo de descer só onde o rollup aponta trabalho aberto."""
        atual = self._encontrar_raiz(view)
        if atual is None:
            return (0, ())
        total = 0
        passos: list[str] = []
        for _ in range(PROFUNDIDADE_MAXIMA_DA_DESCIDA):
            if atual is None:
                break
            total += self._tokens_da_vista(view, atual)
            passos.append(atual)
            atual = self._proximo_filho_com_trabalho(view, atual)
        return (total, tuple(passos))

    def _proximo_filho_com_trabalho(self, view: GrafoView, id_no: str) -> str | None:
        """Primeiro filho cujo resumo declara trabalho aberto, se houver algum."""
        for filho in view.obter_filhos_por_contencao(id_no):
            resumo = view.obter_resumo(filho.id)
            if resumo is not None and resumo.tem_trabalho_aberto:
                return filho.id
        return None

    def _encontrar_raiz(self, view: GrafoView) -> str | None:
        """Projeto raiz do grafo, ponto de partida de qualquer descida."""
        projetos = view.listar_nos_por_tipo(TipoNo.PROJETO)
        return projetos[0].id if projetos else None

    def _listar_containers(self, view: GrafoView) -> tuple[NoGrafo, ...]:
        """Todos os nós da camada de navegação, na ordem da projeção."""
        return tuple(no for no in view.listar_todos_os_nos() if no.tipo in TIPOS_DE_CONTAINER)

    def _tokens_da_vista(self, view: GrafoView, id_alvo: str) -> int:
        """Tamanho da vista materializada do nó, no orçamento padrão."""
        requisicao = RequisicaoVista(
            id_alvo=id_alvo, papel=PapelAutor.PLANEJADOR, orcamento_tokens=ORCAMENTO_DA_MEDICAO
        )
        return self._materializador.materializar(requisicao, view).tokens_estimados

    def _medir_buscas(self, view: GrafoView) -> tuple[MedidaDeBusca, ...]:
        """Sonda alguns termos, comparando a resposta inteira com a cortada."""
        return tuple(self._medir_uma_busca(view, termo) for termo in TERMOS_DE_SONDAGEM)

    def _medir_uma_busca(self, view: GrafoView, termo: str) -> MedidaDeBusca:
        """Mede o mesmo termo com o limite no teto e no padrão da ferramenta."""
        inteira = view.buscar_ranqueado(CriterioBusca(termo=termo, limite=999))
        cortada = view.buscar_ranqueado(CriterioBusca(termo=termo))
        return MedidaDeBusca(
            termo=termo,
            total_encontrado=inteira.total_encontrado,
            tokens_sem_limite=ContadorTokens.estimar_objeto(inteira.em_dicionario()),
            tokens_com_limite=ContadorTokens.estimar_objeto(cortada.em_dicionario()),
        )


def medir_escala(kernel: WriteKernel, ramo_id: str = "main") -> RelatorioDeEscala:
    """Ponto de entrada da medição de escala sobre um kernel já montado."""
    return MedidorDeEscala(kernel).medir(ramo_id)
