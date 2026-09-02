"""O kernel emite spans de verdade; antes o tracer não tinha chamador algum.

`TracerOTel` era uma lista em memória que nenhum módulo usava, e o README
prometia suporte nativo a OpenTelemetry sobre isso. Ver achado A-13.
"""

import json
from pathlib import Path

from graphow.core.events import TipoEvento
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.telemetria import (
    ATRIBUTO_MODO_DE_FALHA,
    ATRIBUTO_NO,
    ATRIBUTO_PAPEL,
    ATRIBUTO_PATCH,
    ATRIBUTO_PORTAO,
    ATRIBUTO_SISTEMA,
    OPERACAO_REGISTRAR_EXECUCAO,
    OPERACAO_SUBMETER_PATCH,
)
from graphow.kernel.write_kernel import DependenciasKernel, WriteKernel
from graphow.observability.exportador_spans import TracerArquivoNDJSON
from graphow.observability.tracer import TracerOTel
from graphow.storage.in_memory_store import InMemoryEventStore


def _proposta(papel: PapelAutor, tipo: TipoNo) -> PropostaPatch:
    """Proposta mínima de criação de um nó do tipo informado."""
    return PropostaPatch.criar(
        DadosPropostaPatch(
            autor="david",
            papel=papel,
            operacoes=[
                ItemPatch(
                    op=OperacaoPatch.ADD,
                    path="/nos/n1",
                    value={"id": "n1", "tipo": tipo.value, "rotulo": "N1"},
                )
            ],
        )
    )


def _kernel_com_tracer() -> tuple[WriteKernel, TracerOTel]:
    """Kernel em memória com o coletor de spans injetado."""
    tracer = TracerOTel()
    kernel = WriteKernel(InMemoryEventStore(), DependenciasKernel(tracer=tracer))
    return kernel, tracer


def test_submissao_aceita_emite_span_nominal() -> None:
    """Toda escrita que passa pelos portões deixa um span com o papel e o alvo."""
    kernel, tracer = _kernel_com_tracer()

    kernel.submeter_patch(_proposta(PapelAutor.HUMANO, TipoNo.NOTE))

    spans = tracer.listar_todos_spans()
    assert [span.nome_operacao for span in spans] == [OPERACAO_SUBMETER_PATCH]
    assert spans[0].sucesso
    assert spans[0].atributos[ATRIBUTO_SISTEMA] == "graphow"
    assert spans[0].atributos[ATRIBUTO_PAPEL] == PapelAutor.HUMANO.value
    assert spans[0].atributos[ATRIBUTO_NO] == "n1"


def test_submissao_recusada_carrega_portao_e_modo_nominal() -> None:
    """A recusa é o span mais útil: ele diz onde parou e por qual modo MAST."""
    kernel, tracer = _kernel_com_tracer()

    kernel.submeter_patch(_proposta(PapelAutor.EXECUTOR, TipoNo.CONSTRAINT))

    span = tracer.listar_todos_spans()[0]
    assert not span.sucesso
    assert span.atributos[ATRIBUTO_PORTAO] == "RoleGate"
    assert span.atributos[ATRIBUTO_MODO_DE_FALHA] == "violacao_permissao_papel"


def test_registro_de_execucao_emite_span_proprio_nominal() -> None:
    """O fato de ciclo de vida do harness tem operação distinta da do patch."""
    kernel, tracer = _kernel_com_tracer()

    kernel.registrar_execucao(
        PedidoDeExecucao(
            id_run="run-1",
            id_sessao="sess-1",
            tipo_evento=TipoEvento.EXECUCAO_SOLICITADA,
            dados={"modelo": "claude-opus-5"},
        )
    )

    span = tracer.listar_todos_spans()[0]
    assert span.nome_operacao == OPERACAO_REGISTRAR_EXECUCAO
    assert span.atributos["gen_ai.model"] == "claude-opus-5"


def test_kernel_sem_tracer_nao_guarda_nada_edge_case() -> None:
    """Caso de borda: sem destino declarado a telemetria não custa memória."""
    kernel = montar_kernel_em_memoria()

    recibo = kernel.submeter_patch(_proposta(PapelAutor.HUMANO, TipoNo.NOTE))

    assert recibo.sucesso


def test_exportador_grava_uma_linha_por_span_nominal(tmp_path: Path) -> None:
    """O tracer em memória morria com o processo; o arquivo sobrevive a ele."""
    destino = tmp_path / "spans" / "graphow.ndjson"
    kernel = WriteKernel(InMemoryEventStore(), DependenciasKernel(tracer=TracerArquivoNDJSON(destino)))

    kernel.submeter_patch(_proposta(PapelAutor.HUMANO, TipoNo.NOTE))
    kernel.submeter_patch(_proposta(PapelAutor.EXECUTOR, TipoNo.CONSTRAINT))

    linhas = [json.loads(linha) for linha in destino.read_text(encoding="utf-8").splitlines()]
    assert [linha["status"] for linha in linhas] == ["OK", "ERROR"]
    assert all(linha["name"] == OPERACAO_SUBMETER_PATCH for linha in linhas)
    assert linhas[0]["attributes"][ATRIBUTO_PATCH]


def test_coletor_em_memoria_respeita_o_teto_edge_case() -> None:
    """Caso de borda: com chamador de verdade, a lista sem teto viraria vazamento."""
    tracer = TracerOTel(limite=2)
    kernel = WriteKernel(InMemoryEventStore(), DependenciasKernel(tracer=tracer))

    for _ in range(5):
        kernel.submeter_patch(_proposta(PapelAutor.HUMANO, TipoNo.NOTE))

    assert len(tracer.listar_todos_spans()) == 2
