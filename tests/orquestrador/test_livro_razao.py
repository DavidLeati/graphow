"""O livro-razão do Goal gravado pelo orquestrador e relido como o estado do laço."""

import copy

import pytest

from graphow.core.types import PapelAutor, TipoAresta
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.gravacao_do_plano import PlanoParaGravar, gravar_plano
from graphow.orquestrador.leitura_do_goal import ler_estado
from graphow.orquestrador.livro_razao import GoalNovo, LivroRazaoDoGoal, LoteRecusado
from graphow.orquestrador.saidas import Plano, SaidaDoExecutor, Verificacao

from tests.orquestrador.test_esquemas_e_saidas import PLANO, VERIFICACAO

CONFIGURACAO: m.ConfiguracaoDoGoal = m.ConfiguracaoDoGoal(
    modo=m.MODO_AUTONOMO, repositorio="C:/repo", area="C:/areas/soma", ramo="graphow/soma", base="main",
    slug="soma", orcamento_usd=30.0,
)


def _livro_com_plano() -> tuple[WriteKernel, LivroRazaoDoGoal]:
    """Um Goal criado da spec, com o plano de exemplo gravado."""
    kernel = montar_kernel_em_memoria()
    livro = LivroRazaoDoGoal(kernel, "goal-soma")
    livro.criar_goal(GoalNovo("goal-soma", "soma", "# Pedido\nSomar dois numeros.", CONFIGURACAO, "repo"))
    gravar_plano(livro, PlanoParaGravar(Plano.de_json(PLANO), "soma", "abc123", "docs/goals/soma.md", renomear_goal=True))
    return kernel, livro


def test_goal_e_plano_viram_nos_do_livro_razao_nominal() -> None:
    """Critérios como Constraint, decisão como Decision, fatias como Task com dependência, tudo do orquestrador."""
    kernel, _ = _livro_com_plano()
    view = kernel.obter_view()

    estado = ler_estado(view, "goal-soma")

    assert estado is not None and estado.rotulo == "Soma de dois numeros"
    assert [fatia.codigo for fatia in estado.fatias] == ["F1", "F2"]
    assert estado.fatias[1].depende_de == ("task-soma-f1",)
    assert view.obter_no("crit-soma-c1").rotulo == "somar(2, 3) devolve 5"
    assert [a.destino_id for a in view.obter_arestas_saida("crit-soma-c1", TipoAresta.ESCOPA)] == ["goal-soma"]
    assert view.obter_no("dec-soma-d1").obter_propriedade("motivo") == "o pacote nao tem dependencia"
    assert estado.plano is not None and estado.plano["comando_suite"] == "python -m pytest -q"
    assert {no.proveniencia.papel for no in view.listar_todos_os_nos()} == {PapelAutor.ORQUESTRADOR.value}
    assert [fatia.codigo for fatia in estado.prontas()] == ["F1"]


def test_fatias_fecham_em_ordem_e_a_verificacao_liga_o_goal_nominal() -> None:
    """Concluir F1 libera F2; a verificação rejeitada abre a correção; a limpa permite fechar."""
    kernel, livro = _livro_com_plano()
    saida = SaidaDoExecutor("pronto", "feito", ("soma.py",), ("pytest: ok",))
    for id_task in ("task-soma-f1", "task-soma-f2"):
        livro.iniciar_tentativa(id_task, 1)
        livro.concluir_fatia(id_task, 1, commit="c0ffee" + id_task[-1], saida=saida)

    verificacao = Verificacao.de_json(VERIFICACAO)
    pendencia = {"gravidade": "acompanhamento", "titulo": "nome", "descricao": "d", "origem": "verificacao 1"}
    id_evidencia = livro.gravar_verificacao(1, verificacao, commit="c0ffee2", ciclo=0, pendencias=[pendencia])
    livro.criar_correcoes(id_evidencia, verificacao.bloqueantes(), ciclo=1, ordem=2)
    estado = ler_estado(kernel.obter_view(), "goal-soma")

    assert estado is not None
    assert estado.ultima_verificacao is not None and not estado.ultima_verificacao.limpa
    assert [fatia.codigo for fatia in estado.prontas()] == ["K1.1"]
    assert estado.ciclos_de_correcao == 1
    assert estado.pendencias == [pendencia]
    correcao = estado.fatias[-1]
    assert correcao.texto(m.CAMPO_CORRIGE) == id_evidencia
    livro.iniciar_tentativa(correcao.id, 1)
    livro.concluir_fatia(correcao.id, 1, commit="c0ffee3", saida=saida)
    limpa = Verificacao.de_json({**copy.deepcopy(VERIFICACAO), "criterios": [
        {"id": "C1", "veredito": "atende", "prova": "ok"}, {"id": "C2", "veredito": "atende", "prova": "ok"}]})
    livro.gravar_verificacao(2, limpa, commit="c0ffee3", ciclo=1, pendencias=[])
    livro.fechar("c0ffee3")
    final = ler_estado(kernel.obter_view(), "goal-soma")
    assert final is not None and final.fechado and final.ultima_verificacao.limpa


def test_duvida_pausa_so_a_fatia_e_a_resposta_do_humano_a_libera_nominal() -> None:
    """A Question bloqueia a fatia; o humano responde e ela volta à fila."""
    kernel, livro = _livro_com_plano()
    livro.iniciar_tentativa("task-soma-f1", 1)
    id_questao = livro.abrir_duvida("task-soma-f1", 1, pergunta="Soma de inteiros ou de decimais?\nOpcoes: a, b", patch="p.patch")

    pausada = ler_estado(kernel.obter_view(), "goal-soma")
    resposta = PropostaPatch.criar(DadosPropostaPatch(
        autor="humano", papel=PapelAutor.HUMANO, justificativa="resposta",
        operacoes=(ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/status", "respondida"),
                   ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/resposta", "decimais")),
    ))
    assert kernel.submeter_patch(resposta).sucesso
    liberada = ler_estado(kernel.obter_view(), "goal-soma")

    assert pausada is not None and pausada.prontas() == () and [f.codigo for f in pausada.pausadas()] == ["F1"]
    assert liberada is not None and [f.codigo for f in liberada.prontas()] == ["F1"]
    assert liberada.fatias[0].duvidas[0].resposta == "decimais"


def test_segunda_falha_vira_pendencia_do_goal_edge_case() -> None:
    """Caso de borda: a fatia bloqueada sai da fila e a pendência fica no Goal."""
    kernel, livro = _livro_com_plano()
    livro.iniciar_tentativa("task-soma-f1", 1)
    livro.registrar_falha("task-soma-f1", 1, erro="suite vermelha", patch="t1.patch", falhas=1)
    livro.iniciar_tentativa("task-soma-f1", 2)
    livro.marcar_pendencia("task-soma-f1", "falhou duas vezes", [{"origem": "task-soma-f1", "titulo": "falhou duas vezes"}])

    estado = ler_estado(kernel.obter_view(), "goal-soma")

    assert estado is not None
    assert [fatia.codigo for fatia in estado.bloqueadas()] == ["F1"]
    assert estado.prontas() == ()
    assert estado.pendencias == [{"origem": "task-soma-f1", "titulo": "falhou duas vezes"}]
    assert estado.fatias[0].tentativas == 2


def test_lote_recusado_vira_erro_com_o_motivo_do_kernel_edge_case() -> None:
    """Caso de borda: o orquestrador que tentasse responder a própria dúvida é recusado pelo kernel."""
    _, livro = _livro_com_plano()
    id_questao = livro.abrir_duvida("task-soma-f1", 1, pergunta="Pergunta?", patch="")

    with pytest.raises(LoteRecusado) as recusa:
        livro.gravar([ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_questao}/propriedades/status", "respondida")], "teste")

    assert "responder e do humano" in recusa.value.contexto["motivo"]
