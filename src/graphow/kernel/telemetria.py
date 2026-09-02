"""Descrição dos spans que o kernel emite a cada escrita aceita ou recusada.

Os atributos seguem a convenção GenAI do OpenTelemetry onde ela existe
(`gen_ai.*`, `agent.role`) e o namespace do produto onde não existe
(`graphow.*`). O kernel monta o fato; o destino do span é injetado e, por
padrão, é o tracer nulo. Ver achado A-13.
"""

from dataclasses import dataclass

from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.patch_models import PropostaPatch
from graphow.observability.tracer import DadosSpanDTO

SISTEMA: str = "graphow"

ATRIBUTO_SISTEMA: str = "gen_ai.system"
ATRIBUTO_MODELO: str = "gen_ai.model"
ATRIBUTO_PAPEL: str = "agent.role"
ATRIBUTO_AUTOR: str = "graphow.autor"
ATRIBUTO_PATCH: str = "graphow.patch.id"
ATRIBUTO_NO: str = "graphow.no.id"
ATRIBUTO_RAMO: str = "graphow.ramo.id"
ATRIBUTO_PORTAO: str = "graphow.portao"
ATRIBUTO_MODO_DE_FALHA: str = "graphow.modo_de_falha"
ATRIBUTO_EVENTOS: str = "graphow.eventos.total"
ATRIBUTO_RUN: str = "graphow.run.id"
ATRIBUTO_SESSAO: str = "graphow.sessao.id"

OPERACAO_SUBMETER_PATCH: str = "graphow.patch.submeter"
OPERACAO_REGISTRAR_EXECUCAO: str = "graphow.execucao.registrar"


@dataclass(frozen=True)
class FatoDeEscrita:
    """O desfecho de uma submissão, na forma de que a telemetria precisa.

    Existe para que este módulo não precise importar `write_kernel`, que o
    importa: o kernel traduz o próprio recibo e entrega os campos crus.
    """

    sucesso: bool
    portao: str | None = None
    modo_de_falha: str | None = None
    eventos_gerados: int = 0


def montar_span_de_patch(proposta: PropostaPatch, fato: FatoDeEscrita) -> DadosSpanDTO:
    """Descreve o span de uma submissão ao PatchBoard, aceita ou recusada."""
    atributos: dict[str, str | int] = {
        ATRIBUTO_SISTEMA: SISTEMA,
        ATRIBUTO_PAPEL: proposta.papel.value,
        ATRIBUTO_AUTOR: proposta.autor,
        ATRIBUTO_PATCH: proposta.id,
        ATRIBUTO_RAMO: proposta.ramo_id,
        ATRIBUTO_EVENTOS: fato.eventos_gerados,
    }
    atributos.update(_atributos_do_alvo(proposta))
    atributos.update(_atributos_da_recusa(fato))
    return DadosSpanDTO(
        nome_operacao=OPERACAO_SUBMETER_PATCH,
        atributos=atributos,
        sucesso=fato.sucesso,
        trace_id=proposta.trace_id,
    )


def montar_span_de_execucao(pedido: PedidoDeExecucao, sucesso: bool) -> DadosSpanDTO:
    """Descreve o span de um fato de ciclo de vida vindo do harness."""
    return DadosSpanDTO(
        nome_operacao=OPERACAO_REGISTRAR_EXECUCAO,
        atributos={
            ATRIBUTO_SISTEMA: SISTEMA,
            ATRIBUTO_MODELO: str(pedido.dados.get("modelo", "desconhecido")),
            ATRIBUTO_PAPEL: pedido.papel.value,
            ATRIBUTO_AUTOR: pedido.autor,
            ATRIBUTO_RUN: pedido.id_run,
            ATRIBUTO_SESSAO: pedido.id_sessao,
            ATRIBUTO_RAMO: pedido.ramo_id,
            "graphow.evento": pedido.tipo_evento.value,
        },
        sucesso=sucesso,
    )


def _atributos_do_alvo(proposta: PropostaPatch) -> dict[str, str]:
    """Identifica o nó focal do lote: o primeiro que a proposta toca."""
    for item in proposta.operacoes:
        segmentos = [seg for seg in item.path.split("/") if seg]
        if len(segmentos) >= 2 and segmentos[0] == "nos":
            return {ATRIBUTO_NO: segmentos[1]}
    return {}


def _atributos_da_recusa(fato: FatoDeEscrita) -> dict[str, str]:
    """Acrescenta portão e modo MAST quando a escrita foi recusada."""
    if fato.sucesso:
        return {}
    return {
        ATRIBUTO_PORTAO: fato.portao or "Desconhecido",
        ATRIBUTO_MODO_DE_FALHA: fato.modo_de_falha or "outro",
    }
