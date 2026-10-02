"""O RoleGate aplica a política de governança do projeto a cada gesto."""

import pytest

from graphow.core.governanca import Gesto
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import OperacaoPatch
from tests.kernel.cenario_governanca import (
    AGENTES_SEM_ARBITRO,
    CASOS_DE_GESTO,
    PRESET_ARBITRAGEM,
    PRESET_MAXIMA,
    criar_aresta,
    criar_no,
    escrever,
    montar_estado,
    remover_aresta,
    remover_no,
    validar,
)

CASOS = list(CASOS_DE_GESTO)


@pytest.mark.parametrize("caso", CASOS)
def test_governanca_maxima_recusa_o_arbitro_e_nomeia_o_gesto_nominal(caso: str) -> None:
    """Em governanca_maxima o gesto é do humano: o árbitro é recusado e a recusa diz qual gesto falta."""
    gesto, operacoes = CASOS_DE_GESTO[caso]
    estado = montar_estado(global_=PRESET_MAXIMA)
    resultado = validar(PapelAutor.ARBITRO, estado, *operacoes())
    assert not resultado.aprovado
    assert gesto.value in str(resultado.mensagem_erro)
    assert "politica de governanca" in str(resultado.mensagem_erro)
    assert validar(PapelAutor.HUMANO, estado, *operacoes()).aprovado


@pytest.mark.parametrize("caso", CASOS)
def test_arbitragem_maxima_aceita_o_arbitro_nominal(caso: str) -> None:
    """Em arbitragem_maxima o árbitro faz cada gesto, e o humano segue podendo."""
    _, operacoes = CASOS_DE_GESTO[caso]
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    resultado = validar(PapelAutor.ARBITRO, estado, *operacoes())
    assert resultado.aprovado, resultado.mensagem_erro
    assert validar(PapelAutor.HUMANO, estado, *operacoes()).aprovado


@pytest.mark.parametrize("papel", AGENTES_SEM_ARBITRO)
@pytest.mark.parametrize("caso", CASOS)
def test_arbitragem_maxima_nao_entrega_nada_aos_outros_agentes_edge_case(caso: str, papel: PapelAutor) -> None:
    """Caso de borda: planejador, executor e revisor seguem recusados com a arbitragem máxima."""
    _, operacoes = CASOS_DE_GESTO[caso]
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    assert not validar(papel, estado, *operacoes()).aprovado


@pytest.mark.parametrize("caso", CASOS)
def test_sem_no_global_vale_governanca_maxima_edge_case(caso: str) -> None:
    """Caso de borda: sem o nó `governanca-global` o árbitro não faz gesto algum."""
    _, operacoes = CASOS_DE_GESTO[caso]
    assert not validar(PapelAutor.ARBITRO, montar_estado(), *operacoes()).aprovado


def test_heranca_do_global_para_o_projeto_nominal() -> None:
    """O Projeto sem preset próprio herda o global; um preset próprio o sobrepõe."""
    _, operacoes = CASOS_DE_GESTO["excluir_aprendizado"]
    herdando = montar_estado(global_=PRESET_ARBITRAGEM, governanca={"preset": "herdar"})
    assert validar(PapelAutor.ARBITRO, herdando, *operacoes()).aprovado
    fechado = montar_estado(global_=PRESET_ARBITRAGEM, governanca=PRESET_MAXIMA)
    assert not validar(PapelAutor.ARBITRO, fechado, *operacoes()).aprovado
    aberto = montar_estado(global_=PRESET_MAXIMA, governanca=PRESET_ARBITRAGEM)
    assert validar(PapelAutor.ARBITRO, aberto, *operacoes()).aprovado


def test_personalizada_do_projeto_muda_so_o_gesto_declarado_nominal() -> None:
    """A personalizada parcial do Projeto entrega ao árbitro só o gesto que declara; o resto herda."""
    projeto = {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}}
    estado = montar_estado(global_=PRESET_MAXIMA, governanca=projeto)
    assert validar(PapelAutor.ARBITRO, estado, remover_no("a")).aprovado
    assert not validar(PapelAutor.ARBITRO, estado, escrever(OperacaoPatch.REPLACE, "q", "status", "respondida")).aprovado
    assert not validar(PapelAutor.ARBITRO, estado, escrever(OperacaoPatch.REPLACE, "goal", "status", "concluido")).aprovado


def test_personalizada_global_vale_para_o_projeto_que_herda_nominal() -> None:
    """A personalizada global, herdada pelo Projeto, decide gesto a gesto."""
    globais = {"preset": "personalizada", "personalizada": {"fechar_goal": "arbitro"}}
    estado = montar_estado(global_=globais)
    assert validar(PapelAutor.ARBITRO, estado, escrever(OperacaoPatch.REPLACE, "goal", "status", "concluido")).aprovado
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("a")).aprovado


def test_preset_fixo_ignora_a_personalizada_guardada_edge_case() -> None:
    """Caso de borda: com preset fixo a personalizada fica guardada à parte e não vale."""
    globais = {"preset": "governanca_maxima", "personalizada": {"excluir": "arbitro"}}
    assert not validar(PapelAutor.ARBITRO, montar_estado(global_=globais), remover_no("a")).aprovado


def test_o_projeto_decide_o_gesto_de_cada_alvo_edge_case() -> None:
    """Caso de borda: a política lida é a do projeto do alvo, não a de outro projeto do grafo."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM, governanca=PRESET_MAXIMA)
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("a")).aprovado
    assert validar(PapelAutor.ARBITRO, montar_estado(global_=PRESET_ARBITRAGEM), remover_no("a")).aprovado


@pytest.mark.parametrize("caso", ["questao_respondida", "questao_sem_status", "bloqueio_retirado", "excluir_questao"])
def test_arbitro_nao_encerra_a_question_que_abriu_edge_case(caso: str) -> None:
    """Caso de borda: o árbitro não encerra a dúvida que abriu, nem com outra conexão (sufixo `#`)."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    operacoes = {
        "questao_respondida": (escrever(OperacaoPatch.REPLACE, "q-arb", "status", "respondida"),),
        "questao_sem_status": (escrever(OperacaoPatch.REMOVE, "q-arb", "status"),),
        "bloqueio_retirado": (remover_aresta("bloqueia-q-arb-t2"),),
        "excluir_questao": (remover_no("q-arb"),),
    }[caso]
    proprio = validar(PapelAutor.ARBITRO, estado, *operacoes, autor="arbitro-1#cccc")
    assert not proprio.aprovado
    assert "causa propria" in str(proprio.mensagem_erro)
    assert validar(PapelAutor.ARBITRO, estado, *operacoes, autor="arbitro-1").aprovado is False
    assert validar(PapelAutor.ARBITRO, estado, *operacoes, autor="arbitro-2#cccc").aprovado


def test_arbitro_encerra_a_question_de_outro_autor_nominal() -> None:
    """O árbitro encerra a dúvida que o executor abriu."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    resposta = escrever(OperacaoPatch.REPLACE, "q", "status", "respondida")
    assert validar(PapelAutor.ARBITRO, estado, resposta, autor="arbitro-1#cccc").aprovado


def test_arbitro_so_encerra_com_status_declarado_edge_case() -> None:
    """Caso de borda: um status inventado não encerra, nem para o árbitro."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    inventado = escrever(OperacaoPatch.REPLACE, "q", "status", "resolvida")
    assert not validar(PapelAutor.ARBITRO, estado, inventado).aprovado


@pytest.mark.parametrize("papel", [PapelAutor.ARBITRO, *AGENTES_SEM_ARBITRO])
def test_alcance_do_aprendizado_segue_do_humano_em_arbitragem_maxima_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: a promoção global (`alcance`) é do humano em qualquer política."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    alcance = escrever(OperacaoPatch.REPLACE, "a", "alcance", "global")
    resultado = validar(papel, estado, alcance)
    assert not resultado.aprovado
    assert "alcance" in str(resultado.mensagem_erro)
    nascido = criar_no("a3", TipoNo.APRENDIZADO, alcance="global")
    assert not validar(papel, estado, nascido, criar_aresta("prod-a3", "sess", "a3", TipoAresta.PRODUZ)).aprovado


@pytest.mark.parametrize("papel", [PapelAutor.ARBITRO, *AGENTES_SEM_ARBITRO])
@pytest.mark.parametrize("operacao", ["replace", "add", "remove"])
def test_agente_nao_escreve_a_governanca_do_projeto_edge_case(operacao: str, papel: PapelAutor) -> None:
    """Caso de borda: o meta-portão é do humano, inclusive em arbitragem_maxima."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM, governanca=PRESET_MAXIMA)
    op = OperacaoPatch(operacao)
    resultado = validar(papel, estado, escrever(op, "proj", "governanca", PRESET_ARBITRAGEM))
    assert not resultado.aprovado
    assert "governanca" in str(resultado.mensagem_erro)


@pytest.mark.parametrize("papel", [PapelAutor.ARBITRO, *AGENTES_SEM_ARBITRO])
@pytest.mark.parametrize("governanca", [PRESET_ARBITRAGEM, {}])
def test_agente_nao_cria_projeto_com_governanca_edge_case(governanca: dict[str, str], papel: PapelAutor) -> None:
    """Caso de borda: o Projeto nasce de agente sem `governanca`, mesmo vazia."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    criar = criar_no("proj2", TipoNo.PROJETO, governanca=governanca)
    resultado = validar(papel, estado, criar)
    assert not resultado.aprovado
    assert "governanca" in str(resultado.mensagem_erro)


def test_humano_escreve_a_governanca_do_projeto_nominal() -> None:
    """O humano segue escrevendo a política do Projeto."""
    estado = montar_estado(global_=PRESET_MAXIMA)
    assert validar(PapelAutor.HUMANO, estado, escrever(OperacaoPatch.REPLACE, "proj", "governanca", PRESET_ARBITRAGEM)).aprovado


@pytest.mark.parametrize("preset", [PRESET_MAXIMA, PRESET_ARBITRAGEM])
@pytest.mark.parametrize("papel", [PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR])
def test_executor_e_planejador_nao_encerram_sessao_nem_fecham_goal_edge_case(papel: PapelAutor, preset: dict[str, str]) -> None:
    """Caso de borda: antes qualquer agente encerrava a Sessão e fechava o Goal por `propor_patch`."""
    estado = montar_estado(global_=preset)
    assert not validar(papel, estado, escrever(OperacaoPatch.REPLACE, "sess", "status", "concluida")).aprovado
    assert not validar(papel, estado, escrever(OperacaoPatch.REPLACE, "goal", "status", "concluido")).aprovado
    assert not validar(papel, estado, escrever(OperacaoPatch.REMOVE, "sess", "status")).aprovado


@pytest.mark.parametrize("preset", [PRESET_MAXIMA, PRESET_ARBITRAGEM])
def test_sistema_segue_encerrando_a_sessao_nominal(preset: dict[str, str]) -> None:
    """O harness encerra e reabre a Sessão que abriu, sempre, em qualquer política."""
    estado = montar_estado(global_=preset)
    for status in ("concluida", "ativa"):
        assert validar(PapelAutor.SISTEMA, estado, escrever(OperacaoPatch.REPLACE, "sess", "status", status)).aprovado


def test_goal_e_sessao_nao_nascem_fechados_por_agente_edge_case() -> None:
    """Caso de borda: criar o Goal concluído ou a Sessão encerrada é o mesmo gesto, e não escapa."""
    estado = montar_estado(global_=PRESET_MAXIMA)
    goal = criar_no("g2", TipoNo.GOAL, status="concluido")
    sessao = criar_no("s2", TipoNo.SESSAO, status="concluida")
    ligar_goal = criar_aresta("prod-g2", "sess", "g2", TipoAresta.PRODUZ)
    ligar_sessao = criar_aresta("cont-s2", "setor", "s2", TipoAresta.CONTEM)
    for papel in (PapelAutor.EXECUTOR, PapelAutor.ARBITRO):
        assert not validar(papel, estado, goal, ligar_goal).aprovado
        assert not validar(papel, estado, sessao, ligar_sessao).aprovado
    aberta = criar_no("s3", TipoNo.SESSAO, status="ativa")
    assert validar(PapelAutor.SISTEMA, estado, aberta, criar_aresta("cont-s3", "setor", "s3", TipoAresta.CONTEM)).aprovado


@pytest.mark.parametrize("estrutura", ["estrito", "ilimitado"])
def test_governanca_nunca_e_do_arbitro_edge_case(estrutura: str) -> None:
    """Caso de borda: o nó Governanca segue do humano, até na arbitragem máxima."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM, nivel_autonomia=estrutura)
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("governanca-global")).aprovado
    edicao = escrever(OperacaoPatch.REPLACE, "governanca-global", "preset", "governanca_maxima")
    assert not validar(PapelAutor.ARBITRO, estado, edicao).aprovado


def test_gesto_excluir_nao_abre_a_constraint_com_constraint_humano_edge_case() -> None:
    """Caso de borda: `excluir` não é atalho para a Constraint; quem a governa é o gesto `constraint`."""
    globais = {"preset": "personalizada", "personalizada": {"excluir": "arbitro"}}
    assert not validar(PapelAutor.ARBITRO, montar_estado(global_=globais), remover_no("c")).aprovado


def test_gesto_constraint_nao_abre_o_governanca_edge_case() -> None:
    """Caso de borda: o gesto `constraint` abre a Constraint e mais nada que seja do humano."""
    assert Gesto.CONSTRAINT.value == "constraint"
    estado = montar_estado(global_={"preset": "personalizada", "personalizada": {"constraint": "arbitro"}})
    assert validar(PapelAutor.ARBITRO, estado, remover_no("c")).aprovado
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("governanca-global")).aprovado
