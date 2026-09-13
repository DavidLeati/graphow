"""Testes da fiação do harness: o hook dispara e o grafo registra a execução."""

from graphow.core.events import TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor, TipoNo
from graphow.harness.servico_harness import (
    FaseDoHarness,
    PedidoDeCicloDeVida,
    ServicoHarness,
)
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.execucao import PedidoDeExecucao
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel


def _criar_setor(kernel: WriteKernel) -> None:
    """Cria o Setor que a sessão do harness vai habitar."""
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/setor-1",
                        value={"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "Engenharia"},
                    ),
                ),
                justificativa="bootstrap",
            )
        )
    )


def test_fase_de_inicio_abre_sessao_e_emite_evento_nominal() -> None:
    """O contrato da §3.9 estava declarado e nunca exercido; agora ele roda."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel)

    recibo = ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(
            fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor="setor-1", modelo="opus-5"
        )
    )

    assert recibo.sucesso is True
    assert kernel.obter_view().contem_no("sess-hook") is True
    tipos = [evento.tipo_evento for evento in kernel.repositorio.ler_eventos("main")]
    assert TipoEvento.EXECUCAO_SOLICITADA in tipos


def test_ciclo_completo_registra_as_tres_fases_nominal() -> None:
    """Solicitada, iniciada e concluída deixam de ser vocabulário sem uso."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel)
    servico = ServicoHarness(kernel)

    for fase in (FaseDoHarness.INICIO, FaseDoHarness.PROGRESSO, FaseDoHarness.FIM):
        servico.registrar(
            PedidoDeCicloDeVida(fase=fase, id_sessao="sess-hook", id_setor="setor-1", resumo="pronto")
        )

    tipos = {evento.tipo_evento for evento in kernel.repositorio.ler_eventos("main")}
    assert {
        TipoEvento.EXECUCAO_SOLICITADA,
        TipoEvento.EXECUCAO_INICIADA,
        TipoEvento.EXECUCAO_CONCLUIDA,
    } <= tipos


def test_execucao_cria_o_no_run_ligado_a_sessao_nominal() -> None:
    """O acumulador já sabia projetar estes eventos; faltava alguém emiti-los."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel)

    ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor="setor-1")
    )

    run = kernel.obter_view().obter_no("run-sess-hook")
    assert run is not None
    assert run.tipo == TipoNo.RUN
    assert run.obter_propriedade("id_sessao") == "sess-hook"


def test_fim_fecha_a_sessao_registrada_nominal() -> None:
    """O fim do hook precisa deixar o status da sessão coerente no canvas."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel)
    servico = ServicoHarness(kernel)
    servico.registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor="setor-1")
    )

    servico.registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.FIM, id_sessao="sess-hook", resumo="3 tarefas")
    )

    assert kernel.obter_view().obter_no("sess-hook").obter_propriedade("status") == "concluida"


def test_fim_sem_sessao_no_grafo_ainda_registra_telemetria_edge_case() -> None:
    """Caso de borda: hook fora de uma sessão declarada não pode falhar em silêncio."""
    kernel = montar_kernel_em_memoria()

    recibo = ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.FIM, id_sessao="sess-solta")
    )

    assert recibo.sucesso is True
    assert kernel.obter_view().contem_no("run-sess-solta") is True


def test_kernel_recusa_evento_fora_do_ciclo_de_execucao_edge_case() -> None:
    """Caso de borda: esta porta é só para o ciclo de vida, não para mutações."""
    kernel = montar_kernel_em_memoria()

    recibo = kernel.registrar_execucao(
        PedidoDeExecucao(id_run="r1", id_sessao="s1", tipo_evento=TipoEvento.NO_CRIADO)
    )

    assert recibo.sucesso is False
    assert kernel.obter_view().total_nos == 0


def test_evento_de_execucao_carrega_origem_harness_nominal() -> None:
    """A origem do disparo precisa distinguir o ambiente de um agente."""
    kernel = montar_kernel_em_memoria()

    ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook")
    )

    evento = kernel.repositorio.ler_eventos("main")[-1]
    assert evento.origem == OrigemEvento.HARNESS
    assert evento.papel == PapelAutor.SISTEMA
