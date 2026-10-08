"""D3: o executor não assume Task de Goal sem plano aprovado, e o log antigo segue reproduzindo."""

from typing import Any

import pytest

from graphow.core.events import DadosCriacaoEvento, EventoLog, TipoEvento
from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import OrigemEvento, PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import OperacaoPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.lineage.replay_engine import ReplayEngine
from tests.kernel.cenario_escopo import (
    AUTORES,
    definir_lista,
    entrada_do_plano,
    montar_kernel_com_goal,
    submeter,
)
from tests.kernel.cenario_governanca import criar_aresta, criar_no, escrever

MAXIMA: str = "governanca_maxima"
ARBITRAGEM: str = "arbitragem_maxima"
EXECUTOR: PapelAutor = PapelAutor.EXECUTOR


def _assumir(kernel: WriteKernel, id_task: str = "t1", papel: PapelAutor = EXECUTOR) -> Any:
    """O papel pega a Task (posse e status), como o `assumir_tarefa` faz."""
    assert kernel.adquirir_lock_task(id_task, AUTORES[papel])
    return submeter(kernel, papel, escrever(OperacaoPatch.REPLACE, id_task, "status", "em_andamento"))


def _aprovar(kernel: WriteKernel, papel: PapelAutor) -> None:
    """O papel grava a versão 1 do plano do Goal."""
    recibo = submeter(kernel, papel, definir_lista("planos", [entrada_do_plano(kernel, papel)]))
    assert recibo.sucesso, recibo.mensagem


def test_executor_recusado_sem_plano_aprovado_nominal() -> None:
    """Sem plano o executor não põe a Task em andamento, e a recusa diz o Goal e o gesto que destrava."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = _assumir(kernel)
    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.PLANO_NAO_APROVADO.value
    assert "o Goal goal não tem plano aprovado" in recibo.mensagem
    assert "aprovar_plano" in recibo.mensagem
    assert kernel.obter_estado().nos["t1"].propriedades["status"] == "pendente"


def test_plano_do_humano_libera_o_executor_nominal() -> None:
    """Com a versão do humano, o mesmo lote passa."""
    kernel = montar_kernel_com_goal(MAXIMA)
    _aprovar(kernel, PapelAutor.HUMANO)
    assert _assumir(kernel).sucesso


def test_plano_do_arbitro_tambem_libera_o_executor_nominal() -> None:
    """Qualquer versão destrava, a do árbitro inclusive, quando a política lhe entrega o gesto."""
    kernel = montar_kernel_com_goal(ARBITRAGEM)
    _aprovar(kernel, PapelAutor.ARBITRO)
    assert _assumir(kernel).sucesso


def test_task_sem_goal_acima_e_livre_edge_case() -> None:
    """Caso de borda: a Task que nenhum Goal contém por `decompoe` não tem plano a exigir."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert _assumir(kernel, "solta").sucesso


def test_humano_assume_sem_plano_edge_case() -> None:
    """Caso de borda: o humano nunca passa por esta regra."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = submeter(kernel, PapelAutor.HUMANO, escrever(OperacaoPatch.REPLACE, "t1", "status", "em_andamento"))
    assert recibo.sucesso


def test_goal_acima_pela_cadeia_de_subdivisoes_vale_edge_case() -> None:
    """Caso de borda: a Task filha de Task do Goal herda a exigência pelo Goal mais próximo acima."""
    kernel = montar_kernel_com_goal(MAXIMA)
    filha = (
        criar_no("t1a", TipoNo.TASK, status="pendente"),
        criar_aresta("prod-t1a", "sess", "t1a", TipoAresta.PRODUZ),
        criar_aresta("dec-t1-t1a", "t1", "t1a", TipoAresta.DECOMPOE),
    )
    assert submeter(kernel, PapelAutor.HUMANO, *filha).sucesso
    recibo = _assumir(kernel, "t1a")
    assert recibo.modo_de_falha == ModoFalhaMAST.PLANO_NAO_APROVADO.value


def test_outras_transicoes_do_executor_nao_sao_barradas_por_esta_regra_edge_case() -> None:
    """Caso de borda: a regra olha a ida para `em_andamento`; entregar para revisão segue o resto do RoleGate."""
    kernel = montar_kernel_com_goal(MAXIMA)
    assert kernel.adquirir_lock_task("t1", AUTORES[EXECUTOR])
    recibo = submeter(kernel, EXECUTOR, escrever(OperacaoPatch.REPLACE, "t1", "status", "pronto_para_revisao"))
    assert recibo.modo_de_falha != ModoFalhaMAST.PLANO_NAO_APROVADO.value


@pytest.mark.parametrize("papel", [PapelAutor.PLANEJADOR, PapelAutor.REVISOR])
def test_a_regra_e_do_executor_nao_de_quem_nao_assume_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: planejador e revisor não assumem Task, e a recusa deles não é a de plano."""
    kernel = montar_kernel_com_goal(MAXIMA)
    recibo = submeter(kernel, papel, escrever(OperacaoPatch.REPLACE, "t1", "status", "em_andamento"))
    assert recibo.modo_de_falha != ModoFalhaMAST.PLANO_NAO_APROVADO.value


def _evento_do_executor(seq: int, id_task: str) -> EventoLog:
    """O evento que um executor gravou na 1.4.0: a Task em andamento, sem que nenhum portão olhasse o plano."""
    dados = DadosCriacaoEvento(
        seq=seq,
        autor=AUTORES[EXECUTOR],
        papel=EXECUTOR,
        tipo_evento=TipoEvento.NO_ATUALIZADO,
        payload={"id": id_task, "propriedades": {"status": "em_andamento"}},
        origem=OrigemEvento.HARNESS,
        ramo_id="main",
    )
    return EventoLog.criar(dados)


def test_log_antigo_com_executor_em_andamento_sob_goal_sem_plano_reproduz_edge_case() -> None:
    """Caso de borda: os portões só rodam na submissão; o replay do log gravado antes dos planos não os consulta."""
    kernel = montar_kernel_com_goal(MAXIMA)
    seq = kernel.obter_estado().versao_log + 1
    kernel.repositorio.append_eventos([_evento_do_executor(seq, "t1")])
    estado = ReplayEngine(kernel.repositorio).reproduzir_ate_seq("main", seq)
    assert estado.nos["t1"].propriedades["status"] == "em_andamento"
    assert "planos" not in estado.nos["goal"].propriedades
    assert kernel.obter_estado().nos["t1"].propriedades["status"] == "em_andamento"
