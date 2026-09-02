"""Controlador REST especializado para operações de leitura e mutação visual do Canvas."""

from collections.abc import Mapping
from dataclasses import dataclass
import uuid

from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.projection.graph_view import GrafoView
from graphow.web.identidade_web import IdentidadeSessaoWeb
from graphow.web.mapeamento_escopo import MapeadorEscopo
from graphow.web.dto import (
    DadosArestaVisual,
    DadosCanvasVisual,
    DadosNoVisual,
    RequisicaoEdicaoNo,
    RequisicaoExclusaoLote,
    RequisicaoExclusaoProjeto,
    RequisicaoNovaAresta,
    RequisicaoNovoNo,
    RequisicaoSalvarLayout,
    RespostaReciboWeb,
    PosicaoNoCanvas,
)


CHAVE_POS_X: str = "pos_x"
CHAVE_POS_Y: str = "pos_y"


@dataclass(frozen=True)
class ContextoFiltroVisual:
    """DTO imutável para parâmetros de filtragem e mapeamento visual."""

    mapa_sessoes: Mapping[str, str]
    mapa_projetos: Mapping[str, str]
    nos_bloqueados: frozenset[str]
    sessao_id: str | None = None
    projeto_id: str | None = None


@dataclass(frozen=True)
class MetadadosSubmissao:
    """DTO imutável para metadados de autoria e justificativa de submissões."""

    autor: str
    papel: str
    ramo_id: str
    justificativa: str


class CanvasWebController:
    """Controlador responsável por gerar a projeção do Canvas e processar mutações de nós/arestas."""

    def __init__(
        self,
        kernel: WriteKernel,
        identidade: IdentidadeSessaoWeb | None = None,
        mapeador: MapeadorEscopo | None = None,
    ) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb()
        self._mapeador: MapeadorEscopo = mapeador or MapeadorEscopo()

    def _metadados(self, ramo_id: str, justificativa: str) -> "MetadadosSubmissao":
        """Metadados de autoria vindos sempre da identidade fixada no servidor."""
        return MetadadosSubmissao(
            autor=self._identidade.autor,
            papel=self._identidade.papel_textual,
            ramo_id=ramo_id,
            justificativa=justificativa,
        )

    def obter_canvas(
        self,
        ramo_id: str = "main",
        sessao_id: str | None = None,
        projeto_id: str | None = None,
    ) -> DadosCanvasVisual:
        """Gera a projeção visual completa do grafo com metadados de bloqueio e locks."""
        view: GrafoView = self._kernel.obter_view(ramo_id)
        ctx = ContextoFiltroVisual(
            mapa_sessoes=self._mapeador.mapear_sessoes(view),
            mapa_projetos=self._mapeador.mapear_projetos(view),
            nos_bloqueados=self._mapeador.identificar_tasks_bloqueadas(view),
            sessao_id=sessao_id,
            projeto_id=projeto_id,
        )
        nos_visuais = self._extrair_nos_visuais(view, ctx)
        arestas_visuais = self._extrair_arestas_visuais(view, nos_visuais)
        return DadosCanvasVisual(
            ramo_id=ramo_id,
            versao_log=view.versao_log,
            total_nos=len(nos_visuais),
            total_arestas=len(arestas_visuais),
            nos=nos_visuais,
            arestas=arestas_visuais,
        )

    def _extrair_nos_visuais(self, view: GrafoView, ctx: ContextoFiltroVisual) -> list[DadosNoVisual]:
        """Converte nós do estado em DTOs visuais aplicando filtros opcionais de sessão e projeto."""
        nos_visuais: list[DadosNoVisual] = []
        for no in view.listar_todos_os_nos():
            proj_no = ctx.mapa_projetos.get(no.id)
            if ctx.projeto_id is not None and proj_no != ctx.projeto_id:
                continue
            sessao_no = ctx.mapa_sessoes.get(no.id)
            if ctx.sessao_id is not None and no.tipo != TipoNo.SESSAO and sessao_no != ctx.sessao_id:
                continue
            lock_dono = self._kernel.obter_dono_do_lock(no.id)
            bloqueado = no.id in ctx.nos_bloqueados or no.obter_propriedade("status") == StatusTask.BLOQUEADO.value
            nos_visuais.append(DadosNoVisual(
                id=no.id,
                tipo=no.tipo.value,
                rotulo=no.rotulo,
                propriedades=dict(no.propriedades),
                esta_bloqueado=bloqueado,
                lock_ativo=lock_dono,
                sessao_id=sessao_no,
            ))
        return nos_visuais

    def _extrair_arestas_visuais(self, view: GrafoView, nos_visuais: list[DadosNoVisual]) -> list[DadosArestaVisual]:
        """Converte arestas do estado em DTOs visuais restritos aos nós visíveis."""
        ids_visiveis = {n.id for n in nos_visuais}
        arestas_visuais: list[DadosArestaVisual] = []
        for a in view.listar_todas_as_arestas():
            if a.origem_id in ids_visiveis and a.destino_id in ids_visiveis:
                arestas_visuais.append(DadosArestaVisual(
                    id=a.id,
                    origem_id=a.origem_id,
                    destino_id=a.destino_id,
                    tipo=a.tipo.value,
                ))
        return arestas_visuais

    def criar_no(self, req: RequisicaoNovoNo) -> RespostaReciboWeb:
        """Processa a criação de um novo nó com vinculação opcional à Sessão."""
        id_no = req.id_no or f"{req.tipo.lower()}-{uuid.uuid4().hex[:8]}"
        payload_no = {"id": id_no, "tipo": req.tipo, "rotulo": req.rotulo, "propriedades": dict(req.propriedades)}
        operacoes: list[ItemPatch] = [ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=payload_no)]
        if req.sessao_id is not None:
            id_aresta = f"prod-{id_no}"
            payload_aresta = {"id": id_aresta, "origem_id": req.sessao_id, "destino_id": id_no, "tipo": TipoAresta.PRODUZ.value}
            operacoes.append(ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=payload_aresta))
        meta = self._metadados(req.ramo_id, f"Criação de nó {req.tipo}: {req.rotulo}")
        return self._submeter_operacoes(operacoes, meta)

    def criar_aresta(self, req: RequisicaoNovaAresta) -> RespostaReciboWeb:
        """Processa a criação de uma nova aresta tipada entre dois nós."""
        id_aresta = req.id_aresta or f"edge-{uuid.uuid4().hex[:8]}"
        payload_aresta = {"id": id_aresta, "origem_id": req.origem_id, "destino_id": req.destino_id, "tipo": req.tipo}
        operacoes = [ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=payload_aresta)]
        meta = self._metadados(req.ramo_id, f"Conexão {req.origem_id} -[{req.tipo}]-> {req.destino_id}")
        return self._submeter_operacoes(operacoes, meta)

    def editar_no(self, req: RequisicaoEdicaoNo) -> RespostaReciboWeb:
        """Processa alterações de rótulo e propriedades de um nó existente."""
        operacoes: list[ItemPatch] = []
        if req.novo_rotulo is not None:
            operacoes.append(ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{req.id_no}/rotulo", value=req.novo_rotulo))
        for chave, valor in req.novas_propriedades.items():
            operacoes.append(ItemPatch(op=OperacaoPatch.REPLACE, path=f"/nos/{req.id_no}/propriedades/{chave}", value=valor))
        if not operacoes:
            return RespostaReciboWeb(sucesso=True, mensagem="Nenhuma modificação solicitada")
        meta = self._metadados(req.ramo_id, f"Edição do nó {req.id_no}")
        return self._submeter_operacoes(operacoes, meta)

    def remover_elemento(self, tipo_elemento: str, id_elemento: str, ramo_id: str = "main") -> RespostaReciboWeb:
        """Remove nó ou aresta gerando o respectivo patch de remoção."""
        if tipo_elemento not in ("nos", "arestas"):
            return RespostaReciboWeb(sucesso=False, mensagem=f"Tipo de elemento inválido: {tipo_elemento}")
        operacoes = [ItemPatch(op=OperacaoPatch.REMOVE, path=f"/{tipo_elemento}/{id_elemento}")]
        meta = self._metadados(ramo_id, f"Remoção de {tipo_elemento}: {id_elemento}")
        return self._submeter_operacoes(operacoes, meta)

    def remover_lote(self, req: RequisicaoExclusaoLote) -> RespostaReciboWeb:
        """Processa a remoção atômica de múltiplos nós e arestas."""
        operacoes: list[ItemPatch] = []
        for id_no in req.ids_nos:
            operacoes.append(ItemPatch(op=OperacaoPatch.REMOVE, path=f"/nos/{id_no}"))
        for id_aresta in req.ids_arestas:
            operacoes.append(ItemPatch(op=OperacaoPatch.REMOVE, path=f"/arestas/{id_aresta}"))
        if not operacoes:
            return RespostaReciboWeb(sucesso=True, mensagem="Nenhum elemento fornecido para exclusão")
        total = len(operacoes)
        meta = self._metadados(req.ramo_id, f"Exclusão em lote de {total} elementos")
        return self._submeter_operacoes(operacoes, meta)

    def salvar_layout(self, req: RequisicaoSalvarLayout) -> RespostaReciboWeb:
        """Persiste as coordenadas do canvas como propriedades dos nós."""
        view = self._kernel.obter_view(req.ramo_id)
        operacoes = self._montar_operacoes_de_layout(req.posicoes, view)
        if not operacoes:
            return RespostaReciboWeb(sucesso=True, mensagem="Nenhuma posicao a persistir")
        meta = self._metadados(req.ramo_id, f"Arranjo visual de {len(operacoes) // 2} nos")
        return self._submeter_operacoes(operacoes, meta)

    def _montar_operacoes_de_layout(
        self,
        posicoes: tuple[PosicaoNoCanvas, ...],
        view: GrafoView,
    ) -> list[ItemPatch]:
        """Converte as coordenadas em operações, ignorando nós que já não existem."""
        operacoes: list[ItemPatch] = []
        for posicao in posicoes:
            operacoes.extend(self._operacoes_de_uma_posicao(posicao, view))
        return operacoes

    def _operacoes_de_uma_posicao(self, posicao: PosicaoNoCanvas, view: GrafoView) -> tuple[ItemPatch, ...]:
        """Par de operações que grava as coordenadas de um nó, quando elas mudaram.

        Reescrever a coordenada que já está lá custa um evento no log e uma
        notificação em tempo real para cada cliente aberto. O canvas envia o mapa
        inteiro a cada arrasto, então sem esta comparação mover um nó gravava
        todos os outros — e o log virava, quase inteiro, coordenada que não mudou.
        """
        no = view.obter_no(posicao.id_no)
        if no is None:
            return ()
        if self._coordenadas_inalteradas(no, posicao):
            return ()
        return (
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path=f"/nos/{posicao.id_no}/propriedades/{CHAVE_POS_X}",
                value=posicao.x,
            ),
            ItemPatch(
                op=OperacaoPatch.REPLACE,
                path=f"/nos/{posicao.id_no}/propriedades/{CHAVE_POS_Y}",
                value=posicao.y,
            ),
        )

    def _coordenadas_inalteradas(self, no: NoGrafo, posicao: PosicaoNoCanvas) -> bool:
        """Indica se o nó já carrega exatamente as coordenadas recebidas."""
        return (
            no.obter_propriedade(CHAVE_POS_X) == posicao.x
            and no.obter_propriedade(CHAVE_POS_Y) == posicao.y
        )

    def remover_projeto_completo(self, req: RequisicaoExclusaoProjeto) -> RespostaReciboWeb:
        """Processa a remoção em cascata de um projeto e todos os seus descendentes."""
        view = self._kernel.obter_view(req.ramo_id)
        if not view.contem_no(req.id_projeto):
            return RespostaReciboWeb(sucesso=False, mensagem=f"Projeto '{req.id_projeto}' não encontrado")
        ids_remover = self._mapeador.coletar_descendentes_do_projeto(req.id_projeto, view)
        operacoes = [ItemPatch(op=OperacaoPatch.REMOVE, path=f"/nos/{nid}") for nid in ids_remover]
        meta = self._metadados(
            req.ramo_id,
            f"Remoção em cascata do projeto '{req.id_projeto}' ({len(ids_remover)} nós)",
        )
        return self._submeter_operacoes(operacoes, meta)

    def _submeter_operacoes(self, operacoes: list[ItemPatch], meta: MetadadosSubmissao) -> RespostaReciboWeb:
        """Submete lote de operações ao Kernel e converte o recibo para DTO Web."""
        dados = DadosPropostaPatch(
            autor=meta.autor,
            papel=PapelAutor(meta.papel),
            operacoes=tuple(operacoes),
            justificativa=meta.justificativa,
            ramo_id=meta.ramo_id,
        )
        proposta = PropostaPatch.criar(dados)
        recibo: ResultadoSubmissao = self._kernel.submeter_patch(proposta)
        return RespostaReciboWeb(
            sucesso=recibo.sucesso,
            mensagem=recibo.mensagem,
            versao_log=recibo.versao_log,
            eventos_gerados=recibo.eventos_gerados,
            diagnostico_mast=recibo.diagnostico.categoria.value if recibo.diagnostico else None,
            modo_de_falha=recibo.modo_de_falha,
        )
