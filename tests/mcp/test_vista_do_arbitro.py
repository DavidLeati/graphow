"""A vista que uma sessão árbitro recebe: a dúvida, a Task que ela trava, as decisões e as evidências."""

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from tests.mcp.cenario_governanca import (
    DONO_DA_POSSE,
    _aresta,
    _no,
    abrir_questao_como_agente,
    montar_kernel,
    servidor,
)


def _ligar_decisao_e_evidencia(kernel: WriteKernel) -> None:
    """O humano liga a Decision à Task por `orienta` e cria uma Evidence derivada da Task."""
    kernel.liberar_lock_task("task-a", DONO_DA_POSSE)
    operacoes = [
        _aresta("dec-a", "task-a", TipoAresta.ORIENTA),
        _no("ev-a", TipoNo.EVIDENCE),
        _aresta("sess-a", "ev-a", TipoAresta.PRODUZ),
        _aresta("ev-a", "task-a", TipoAresta.DERIVA_DE),
    ]
    recibo = kernel.submeter_patch(
        PropostaPatch.criar(
            DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="liga")
        )
    )
    assert recibo.sucesso, recibo.mensagem


def test_vista_da_question_na_sessao_arbitro_traz_task_decisao_e_evidencia_nominal() -> None:
    """Lida pelo árbitro, a Question mostra a Task bloqueada e as decisões e evidências do trabalho travado."""
    kernel = montar_kernel()
    _ligar_decisao_e_evidencia(kernel)
    id_questao = abrir_questao_como_agente(kernel)

    resposta = servidor(kernel, "arbitro").executar_ferramenta(
        "ler_vista", {"id_alvo": id_questao, "orcamento_tokens": 4000}
    )

    assert resposta["sucesso"] is True
    assert resposta["perspectiva"] == "arbitro"
    conteudo = resposta["conteudo"]
    assert "Task Bloqueada Pela Duvida" in conteudo
    assert "task-a" in conteudo
    assert "Decisoes Que Governam Esta Tarefa" in conteudo
    assert "dec-a" in conteudo
    assert "ev-a" in conteudo


def test_vista_da_task_na_sessao_arbitro_traz_a_duvida_aberta_nominal() -> None:
    """Lida a partir da Task, a vista do árbitro traz a dúvida aberta que a trava."""
    kernel = montar_kernel()
    _ligar_decisao_e_evidencia(kernel)
    id_questao = abrir_questao_como_agente(kernel)

    resposta = servidor(kernel, "arbitro").executar_ferramenta("ler_vista", {"id_alvo": "task-a", "orcamento_tokens": 4000})

    assert resposta["sucesso"] is True
    assert "Duvidas Abertas Em Julgamento" in resposta["conteudo"]
    assert id_questao in resposta["conteudo"]
    assert "dec-a" in resposta["conteudo"]


def test_vista_do_executor_sobre_a_mesma_question_nao_tem_as_secoes_do_arbitro_edge_case() -> None:
    """Caso de borda: o árbitro não cai mais na política do executor, que não traz estas seções."""
    kernel = montar_kernel()
    _ligar_decisao_e_evidencia(kernel)
    id_questao = abrir_questao_como_agente(kernel)

    resposta = servidor(kernel, "executor").executar_ferramenta(
        "ler_vista", {"id_alvo": id_questao, "orcamento_tokens": 4000}
    )

    assert "Task Bloqueada Pela Duvida" not in resposta["conteudo"]
    assert "Duvidas Abertas Em Julgamento" not in resposta["conteudo"]
