"""Controlador REST da memória: o que o canvas mostra dela e o que o humano faz com ela.

A memória em camadas existia para o agente (a vista, o MCP) e para o disco (o
acervo de notas), mas o canvas não tinha onde vê-la nem como promovê-la. Aqui o
painel lê os aprendizados com origem, alcance e marcas, e as sessões com o
fechamento e o estado da condensação; e o humano registra e promove pelo mesmo
caminho de patch de todo o resto, sob a identidade fixada no servidor.
"""

from collections.abc import Sequence
import uuid

from graphow.context.fechamento import localizar_condensacao
from graphow.context.memoria import ALCANCE_GLOBAL, CAMPO_ALCANCE, CAMPO_COMO_APLICAR
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusSessao, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.notas.extracao import montar_nota
from graphow.notas.modelo import OrigemDaNota
from graphow.projection.graph_view import GrafoView
from graphow.reactive.condensacao import tem_condensacao_pendente
from graphow.web.dto import (
    AprendizadoWeb,
    NoCitadoWeb,
    RequisicaoPromocaoDeAprendizado,
    RequisicaoRegistroDeAprendizado,
    RespostaMemoriaWeb,
    RespostaReciboWeb,
    SessaoDeMemoriaWeb,
)
from graphow.web.identidade_web import IdentidadeSessaoWeb

CONDENSACAO_FEITA: str = "feita"
CONDENSACAO_PENDENTE: str = "pendente"
CONDENSACAO_NENHUMA: str = "nenhuma"
CAMPO_STATUS: str = "status"
CAMPO_RESUMO: str = "resumo"
PREFIXO_DE_APRENDIZADO: str = "apr"


class MemoriaWebController:
    """Lê a memória do ramo para o painel e recebe do humano o registro e a promoção."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeSessaoWeb | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb()

    def obter_memoria(self, ramo_id: str = "main") -> RespostaMemoriaWeb:
        """Todos os aprendizados do ramo, promovidos ou não, e as sessões mais recentes primeiro."""
        view = self._kernel.obter_view(ramo_id)
        aprendizados = sorted(view.listar_nos_por_tipo(TipoNo.APRENDIZADO), key=_ordem_do_log)
        sessoes = sorted(view.listar_nos_por_tipo(TipoNo.SESSAO), key=_ordem_do_log, reverse=True)
        return RespostaMemoriaWeb(
            ramo_id=ramo_id,
            versao_log=view.versao_log,
            aprendizados=tuple(descrever_aprendizado(no, view) for no in aprendizados),
            sessoes=tuple(descrever_sessao(no, view) for no in sessoes),
        )

    def registrar_aprendizado(self, req: RequisicaoRegistroDeAprendizado) -> RespostaReciboWeb:
        """Cria o Aprendizado pendurado na sessão e derivado de cada origem, no mesmo lote."""
        if not req.afirmacao or not req.id_sessao or not req.origens:
            return RespostaReciboWeb(
                sucesso=False,
                mensagem="Um aprendizado precisa de afirmação, da sessão e de ao menos um nó de origem",
            )
        id_aprendizado = req.id_aprendizado or f"{PREFIXO_DE_APRENDIZADO}-{uuid.uuid4().hex[:8]}"
        operacoes = montar_operacoes_de_registro(id_aprendizado, req)
        return self._submeter(operacoes, req.ramo_id, f"Registro de aprendizado: {req.afirmacao}")

    def promover_aprendizado(self, req: RequisicaoPromocaoDeAprendizado) -> RespostaReciboWeb:
        """Dá alcance ao Aprendizado: `vale_para` um Projeto ou Setor, ou a marca global."""
        if not req.id_aprendizado or not (req.id_alvo or req.eh_global):
            return RespostaReciboWeb(
                sucesso=False,
                mensagem="Informe o aprendizado e um alvo (Projeto ou Setor), ou a promoção global",
            )
        operacoes = montar_operacoes_de_promocao(req)
        return self._submeter(operacoes, req.ramo_id, f"Promocao do aprendizado {req.id_aprendizado}")

    def _submeter(self, operacoes: Sequence[ItemPatch], ramo_id: str, justificativa: str) -> RespostaReciboWeb:
        """Submete o lote sob a identidade do servidor e converte o recibo para a interface."""
        dados = DadosPropostaPatch(
            autor=self._identidade.autor,
            papel=PapelAutor(self._identidade.papel_textual),
            operacoes=tuple(operacoes),
            justificativa=justificativa,
            ramo_id=ramo_id,
        )
        recibo = self._kernel.submeter_patch(PropostaPatch.criar(dados))
        return RespostaReciboWeb(
            sucesso=recibo.sucesso,
            mensagem=recibo.mensagem,
            versao_log=recibo.versao_log,
            eventos_gerados=recibo.eventos_gerados,
            diagnostico_mast=recibo.diagnostico.categoria.value if recibo.diagnostico else None,
            modo_de_falha=recibo.modo_de_falha,
        )


def descrever_aprendizado(no: NoGrafo, view: GrafoView) -> AprendizadoWeb:
    """A mesma leitura do acervo de notas, mais a sessão de origem e as marcas resolvidas."""
    nota = montar_nota(no, view)
    return AprendizadoWeb(
        id=nota.id,
        afirmacao=nota.afirmacao,
        como_aplicar=nota.como_aplicar,
        sessao_id=_origem_por_aresta(no.id, TipoAresta.PRODUZ, view),
        alcances=tuple(nota.alcances),
        origens=tuple(_citar(origem) for origem in nota.origens),
        contradicoes=tuple(_citar(origem) for origem in nota.contradicoes),
        substituto=nota.substituto,
        valido_ate=nota.valido_ate,
        promovido=bool(nota.alcances),
        vigente=nota.esta_vigente,
        autor=nota.autor,
        papel=nota.papel,
        seq_criacao=nota.seq_criacao,
    )


def descrever_sessao(no: NoGrafo, view: GrafoView) -> SessaoDeMemoriaWeb:
    """A sessão como a memória a vê: status, fechamento do rollup e a condensação."""
    estado, id_condensacao = _estado_da_condensacao(no.id, view)
    return SessaoDeMemoriaWeb(
        id=no.id,
        rotulo=no.rotulo,
        status=str(no.obter_propriedade(CAMPO_STATUS, StatusSessao.ATIVA.value)),
        resumo=str(no.obter_propriedade(CAMPO_RESUMO, "") or ""),
        setor_id=_origem_por_aresta(no.id, TipoAresta.CONTEM, view),
        fechamento=_linhas_de_fechamento(no.id, view),
        condensacao=estado,
        id_condensacao=id_condensacao,
        seq_criacao=no.ordem.seq_criacao,
    )


def montar_operacoes_de_registro(id_aprendizado: str, req: RequisicaoRegistroDeAprendizado) -> tuple[ItemPatch, ...]:
    """O nó, o `produz` da sessão e uma aresta `deriva_de` por origem, como o MCP faz."""
    no = {
        "id": id_aprendizado,
        "tipo": TipoNo.APRENDIZADO.value,
        "rotulo": req.afirmacao,
        "propriedades": {CAMPO_COMO_APLICAR: req.como_aplicar},
    }
    operacoes = [
        ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_aprendizado}", value=no),
        _aresta(f"prod-{id_aprendizado}", req.id_sessao, id_aprendizado, tipo=TipoAresta.PRODUZ),
    ]
    operacoes.extend(
        _aresta(f"deriv-{id_aprendizado}-{origem}", id_aprendizado, origem, tipo=TipoAresta.DERIVA_DE)
        for origem in req.origens
    )
    return tuple(operacoes)


def montar_operacoes_de_promocao(req: RequisicaoPromocaoDeAprendizado) -> tuple[ItemPatch, ...]:
    """A marca global como propriedade e o alcance por contêiner como aresta."""
    operacoes: list[ItemPatch] = []
    if req.eh_global:
        caminho = f"/nos/{req.id_aprendizado}/propriedades/{CAMPO_ALCANCE}"
        operacoes.append(ItemPatch(op=OperacaoPatch.REPLACE, path=caminho, value=ALCANCE_GLOBAL))
    if req.id_alvo:
        id_aresta = f"vale-{req.id_aprendizado}-{req.id_alvo}"
        operacoes.append(_aresta(id_aresta, req.id_aprendizado, req.id_alvo, tipo=TipoAresta.VALE_PARA))
    return tuple(operacoes)


def _aresta(id_aresta: str, origem_id: str, destino_id: str, *, tipo: TipoAresta) -> ItemPatch:
    """Operação de criação de uma aresta tipada."""
    valor = {"id": id_aresta, "origem_id": origem_id, "destino_id": destino_id, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _citar(origem: OrigemDaNota) -> NoCitadoWeb:
    """A citação de um nó, como a nota do acervo a faz."""
    return NoCitadoWeb(id=origem.id, tipo=origem.tipo, rotulo=origem.rotulo, seq=origem.seq)


def _origem_por_aresta(id_no: str, tipo: TipoAresta, view: GrafoView) -> str | None:
    """O nó de onde parte a primeira aresta do tipo que chega neste: a sessão ou o setor."""
    arestas = view.obter_arestas_entrada(id_no, tipo)
    return min(aresta.origem_id for aresta in arestas) if arestas else None


def _estado_da_condensacao(id_sessao: str, view: GrafoView) -> tuple[str, str | None]:
    """Feita quando a Note existe, pendente enquanto a Task está aberta, nenhuma no resto."""
    condensacao = localizar_condensacao(id_sessao, view)
    if condensacao is not None:
        return CONDENSACAO_FEITA, condensacao.id
    if tem_condensacao_pendente(id_sessao, view):
        return CONDENSACAO_PENDENTE, None
    return CONDENSACAO_NENHUMA, None


def _linhas_de_fechamento(id_sessao: str, view: GrafoView) -> tuple[str, ...]:
    """As linhas do fechamento determinístico que o rollup já calculou para a sessão."""
    resumo = view.obter_resumo(id_sessao)
    return resumo.fechamento.descrever() if resumo is not None else ()


def _ordem_do_log(no: NoGrafo) -> tuple[int, str]:
    """Ordem estável: posição de criação no log e, no empate, o id."""
    return (no.ordem.seq_criacao, no.id)
