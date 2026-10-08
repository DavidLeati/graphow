"""Controlador REST das propostas fora do Goal: a caixa do humano.

A proposta nasce do agente, como Note, e o humano a fecha mudando o `status` para
`aceita` ou `descartada`. A leitura vem da projeção das propostas abertas, a mesma
da vista do humano; a decisão passa pelo kernel, sob a identidade fixada no
servidor, como qualquer outra escrita. Aceitar não cria Task: a Task, se vier,
nasce de um Goal que o humano escopa, e a proposta só deixa de estar aberta.
"""

from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.graph_view import GrafoView
from graphow.projection.propostas import (
    CAMPO_STATUS_DA_PROPOSTA,
    STATUS_DE_DECISAO_DO_HUMANO,
    STATUS_PROPOSTA_ABERTA,
    PropostaForaDoGoal,
    eh_proposta_fora_do_goal,
    listar_propostas_abertas,
    status_da_proposta,
)
from graphow.web.dto import (
    NoCitadoWeb,
    PropostaWeb,
    RequisicaoDecisaoDeProposta,
    RespostaPropostasWeb,
    RespostaReciboWeb,
)
from graphow.web.identidade_web import IdentidadeSessaoWeb


class PropostasWebController:
    """Lê as propostas abertas para a caixa e recebe do humano a decisão sobre cada uma."""

    def __init__(self, kernel: WriteKernel, identidade: IdentidadeSessaoWeb | None = None) -> None:
        self._kernel: WriteKernel = kernel
        self._identidade: IdentidadeSessaoWeb = identidade or IdentidadeSessaoWeb()

    def listar(self, ramo_id: str = "main", id_projeto: str | None = None) -> RespostaPropostasWeb:
        """As propostas abertas do ramo, as do Projeto quando ele é dado, na ordem do log."""
        view = self._kernel.obter_view(ramo_id)
        return RespostaPropostasWeb(
            ramo_id=ramo_id,
            versao_log=view.versao_log,
            propostas=tuple(_descrever(proposta, view) for proposta in listar_propostas_abertas(view, id_projeto or None)),
        )

    def decidir(self, req: RequisicaoDecisaoDeProposta) -> RespostaReciboWeb:
        """Fecha a proposta aberta como aceita ou descartada, pelo kernel."""
        recusa = self._recusar(req)
        if recusa:
            return RespostaReciboWeb(sucesso=False, mensagem=recusa)
        operacao = ItemPatch(
            op=OperacaoPatch.REPLACE,
            path=f"/nos/{req.id_proposta}/propriedades/{CAMPO_STATUS_DA_PROPOSTA}",
            value=req.status,
        )
        dados = DadosPropostaPatch(
            autor=self._identidade.autor,
            papel=PapelAutor(self._identidade.papel_textual),
            operacoes=(operacao,),
            justificativa=f"Proposta {req.id_proposta}: {req.status}",
            ramo_id=req.ramo_id,
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

    def _recusar(self, req: RequisicaoDecisaoDeProposta) -> str:
        """O motivo de a decisão nem chegar ao kernel; vazio quando ela pode seguir."""
        if req.status not in STATUS_DE_DECISAO_DO_HUMANO:
            return f"A decisão é {' ou '.join(sorted(STATUS_DE_DECISAO_DO_HUMANO))}"
        no = self._kernel.obter_view(req.ramo_id).obter_no(req.id_proposta)
        if no is None or not eh_proposta_fora_do_goal(no):
            return f"'{req.id_proposta}' não é uma proposta fora do Goal"
        if status_da_proposta(no) != STATUS_PROPOSTA_ABERTA:
            return f"A proposta '{req.id_proposta}' já está {status_da_proposta(no)}"
        return ""


def _descrever(proposta: PropostaForaDoGoal, view: GrafoView) -> PropostaWeb:
    """A proposta com o rótulo do Projeto e as origens citadas, para a caixa não pedir de novo."""
    projeto = view.obter_no(proposta.projeto_id) if proposta.projeto_id else None
    return PropostaWeb(
        id=proposta.id,
        rotulo=proposta.rotulo,
        status=proposta.status,
        projeto_id=proposta.projeto_id,
        projeto_rotulo=projeto.rotulo if projeto is not None else "",
        origens=tuple(_citar(view.obter_no(id_origem), id_origem) for id_origem in proposta.origens),
        sessao_id=proposta.sessao_id,
        seq_criacao=proposta.seq_criacao,
        autor=proposta.autor,
        papel=proposta.papel,
    )


def _citar(no: NoGrafo | None, id_no: str) -> NoCitadoWeb:
    """A citação do nó; se ele sumiu do grafo, só o id."""
    if no is None:
        return NoCitadoWeb(id=id_no, tipo="", rotulo=id_no, seq=0)
    return NoCitadoWeb(id=no.id, tipo=no.tipo.value, rotulo=no.rotulo, seq=no.ordem.seq_criacao)
