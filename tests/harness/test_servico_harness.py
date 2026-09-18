"""Testes da fiação do harness: o hook dispara e o grafo registra a execução."""

from pathlib import Path

from graphow.core.events import TipoEvento
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
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
    """Cria o Setor, pendurado num Projeto, que a sessão do harness vai habitar."""
    kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(
                autor="david",
                papel=PapelAutor.HUMANO,
                operacoes=(
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/proj-1",
                        value={"id": "proj-1", "tipo": TipoNo.PROJETO.value, "rotulo": "Projeto"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/nos/setor-1",
                        value={"id": "setor-1", "tipo": TipoNo.SETOR.value, "rotulo": "Engenharia"},
                    ),
                    ItemPatch(
                        op=OperacaoPatch.ADD,
                        path="/arestas/contem-proj-1-setor-1",
                        value={
                            "id": "contem-proj-1-setor-1",
                            "origem_id": "proj-1",
                            "destino_id": "setor-1",
                            "tipo": TipoAresta.CONTEM.value,
                        },
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


def _repositorio_de_teste(tmp_path: Path, nome: str) -> str:
    """Uma pasta com `.git`, como o repositório em que o hook roda."""
    (tmp_path / nome / ".git").mkdir(parents=True)
    return str(tmp_path / nome)


def test_inicio_sem_setor_abre_a_sessao_no_ambiente_padrao_do_repositorio_nominal(tmp_path: Path) -> None:
    """Sem `--setor`, a sessão nasce no Projeto do repositório, dentro do Setor `Memoria`."""
    kernel = montar_kernel_em_memoria()
    diretorio = _repositorio_de_teste(tmp_path, "meu-repo")

    recibo = ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", diretorio_de_trabalho=diretorio)
    )

    assert recibo.sucesso is True
    assert recibo.id_setor == "setor-meu-repo-memoria"
    view = kernel.obter_view()
    assert view.obter_no("proj-meu-repo").rotulo == "meu-repo"
    assert [no.id for no in view.obter_filhos_por_contencao("setor-meu-repo-memoria")] == ["sess-hook"]
    assert view.obter_no("sess-hook").obter_propriedade("status") == "ativa"


def test_inicio_repetido_nao_reabre_nem_duplica_a_sessao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o ambiente reenvia o início da mesma sessão; nada nasce duas vezes."""
    kernel = montar_kernel_em_memoria()
    diretorio = _repositorio_de_teste(tmp_path, "meu-repo")
    servico = ServicoHarness(kernel)
    pedido = PedidoDeCicloDeVida(fase=FaseDoHarness.INICIO, id_sessao="sess-hook", diretorio_de_trabalho=diretorio)

    servico.registrar(pedido)
    recibo = servico.registrar(pedido)

    assert recibo.id_setor == "setor-meu-repo-memoria"
    view = kernel.obter_view()
    assert len(view.listar_nos_por_tipo(TipoNo.SESSAO)) == 1
    assert len(view.listar_nos_por_tipo(TipoNo.SETOR)) == 1


def test_setor_declarado_vence_o_ambiente_padrao_nominal(tmp_path: Path) -> None:
    """Quem passa `--setor` escolhe onde a sessão mora; o ambiente padrão nem é criado."""
    kernel = montar_kernel_em_memoria()
    _criar_setor(kernel)
    diretorio = _repositorio_de_teste(tmp_path, "meu-repo")

    recibo = ServicoHarness(kernel).registrar(
        PedidoDeCicloDeVida(
            fase=FaseDoHarness.INICIO, id_sessao="sess-hook", id_setor="setor-1", diretorio_de_trabalho=diretorio
        )
    )

    assert recibo.id_setor == "setor-1"
    view = kernel.obter_view()
    assert view.contem_no("proj-meu-repo") is False
    assert [no.id for no in view.obter_filhos_por_contencao("setor-1")] == ["sess-hook"]
