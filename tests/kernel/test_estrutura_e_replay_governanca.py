"""A estrutura lida da política, o legado `nivel_autonomia` e o replay do veredito."""

from typing import Any

import pytest

from graphow.core.governanca import ID_GOVERNANCA_GLOBAL
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.matriz_papeis import SEPARADOR_DO_SUFIXO_DE_CONEXAO, autor_sem_sufixo_de_conexao, eh_autoria_propria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.role_gate import RoleGate
from graphow.lineage.replay_engine import ReplayEngine
from graphow.mcp.identidade_sessao import SEPARADOR_DO_SUFIXO_DE_CONEXAO as SEPARADOR_DO_MCP
from tests.kernel.cenario_governanca import (
    AGENTES_SEM_ARBITRO,
    PRESET_ARBITRAGEM,
    PRESET_MAXIMA,
    criar_aresta,
    criar_no,
    escrever,
    montar_estado,
    remover_aresta,
    validar,
)

ESTRUTURA_ILIMITADA: dict[str, Any] = {"preset": "personalizada", "personalizada": {"estrutura": "ilimitado"}}


def _nova_task() -> tuple[ItemPatch, ItemPatch]:
    """Task nova pendurada na Sessão: o que a estrutura ilimitada libera aos agentes."""
    return criar_no("t3", TipoNo.TASK), criar_aresta("prod-t3", "sess", "t3", TipoAresta.PRODUZ)


def _nova_setor() -> tuple[ItemPatch, ItemPatch]:
    """Setor novo pendurado no Projeto pela contenção."""
    return criar_no("setor2", TipoNo.SETOR), criar_aresta("cont-setor2", "proj", "setor2", TipoAresta.CONTEM)


@pytest.mark.parametrize("papel", [PapelAutor.EXECUTOR, PapelAutor.ARBITRO])
def test_legado_nivel_autonomia_ilimitado_segue_funcionando_nominal(papel: PapelAutor) -> None:
    """O Projeto com `nivel_autonomia='ilimitado'` e sem política própria libera a estrutura, como antes."""
    estado = montar_estado(nivel_autonomia="ilimitado")
    assert validar(papel, estado, *_nova_task()).aprovado
    assert validar(papel, estado, *_nova_setor()).aprovado


@pytest.mark.parametrize("papel", [PapelAutor.EXECUTOR, PapelAutor.PLANEJADOR, PapelAutor.REVISOR, PapelAutor.ARBITRO])
def test_legado_ilimitado_nao_entrega_a_governanca_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: o legado libera a estrutura e nada mais; os gestos seguem do humano."""
    estado = montar_estado(nivel_autonomia="ilimitado")
    assert not validar(papel, estado, criar_no("c2", TipoNo.CONSTRAINT), criar_aresta("prod-c2", "sess", "c2", TipoAresta.PRODUZ)).aprovado
    assert not validar(papel, estado, criar_aresta("escopa-c-t", "c", "t", TipoAresta.ESCOPA)).aprovado
    assert not validar(papel, estado, criar_aresta("vale-a2-proj", "a2", "proj", TipoAresta.VALE_PARA)).aprovado
    assert not validar(papel, estado, remover_aresta("bloqueia-q-t")).aprovado
    assert not validar(papel, estado, escrever(OperacaoPatch.REPLACE, "q", "status", "respondida")).aprovado


def test_projeto_estrito_nao_libera_a_estrutura_nominal() -> None:
    """Sem `ilimitado`, o agente segue sem criar Task nem Setor."""
    estado = montar_estado(global_=PRESET_MAXIMA)
    assert not validar(PapelAutor.EXECUTOR, estado, *_nova_task()).aprovado
    assert not validar(PapelAutor.EXECUTOR, estado, *_nova_setor()).aprovado


def test_preset_proprio_do_projeto_derruba_o_legado_edge_case() -> None:
    """Caso de borda: o Projeto com preset próprio não conserva o `nivel_autonomia` de antes."""
    estado = montar_estado(governanca=PRESET_MAXIMA, nivel_autonomia="ilimitado")
    assert not validar(PapelAutor.EXECUTOR, estado, *_nova_task()).aprovado


@pytest.mark.parametrize("global_", [PRESET_ARBITRAGEM, ESTRUTURA_ILIMITADA])
def test_estrutura_ilimitada_do_global_chega_ao_projeto_que_herda_nominal(global_: dict[str, Any]) -> None:
    """A estrutura ilimitada vem da política global e vale para quem herda."""
    estado = montar_estado(global_=global_)
    for papel in (PapelAutor.EXECUTOR, PapelAutor.ARBITRO):
        assert validar(papel, estado, *_nova_task()).aprovado
    fechado = montar_estado(global_=global_, governanca=PRESET_MAXIMA)
    assert not validar(PapelAutor.EXECUTOR, fechado, *_nova_task()).aprovado


@pytest.mark.parametrize("papel", [*AGENTES_SEM_ARBITRO, PapelAutor.ARBITRO])
def test_agente_nao_cria_projeto_nem_com_estrutura_global_ilimitada_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: o Projeto novo herdaria a política global; nenhum agente o cria."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    assert not validar(papel, estado, criar_no("proj2", TipoNo.PROJETO)).aprovado


def test_arbitro_nao_cria_governanca_nem_constraint_pela_estrutura_edge_case() -> None:
    """Caso de borda: a estrutura ilimitada não abre o Governanca, que é do humano em qualquer política."""
    estado = montar_estado(global_=PRESET_ARBITRAGEM)
    assert not validar(PapelAutor.ARBITRO, estado, criar_no("gov2", TipoNo.GOVERNANCA)).aprovado


def test_o_veredito_so_depende_do_estado_e_o_replay_o_repete_nominal() -> None:
    """O kernel lê a política só do estado: o estado reproduzido do log dá o mesmo veredito."""
    kernel = montar_kernel_em_memoria()
    humano = _submeter(kernel, PapelAutor.HUMANO, "david",
        criar_no("proj", TipoNo.PROJETO), criar_no("setor", TipoNo.SETOR),
        criar_aresta("cont-proj-setor", "proj", "setor", TipoAresta.CONTEM),
        criar_no("sess", TipoNo.SESSAO, status="ativa"),
        criar_aresta("cont-setor-sess", "setor", "sess", TipoAresta.CONTEM),
        criar_no("goal", TipoNo.GOAL), criar_aresta("prod-goal", "sess", "goal", TipoAresta.PRODUZ),
        criar_no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA, **PRESET_MAXIMA),
    )
    assert humano.sucesso, humano.mensagem
    antes = kernel.obter_estado().versao_log
    fechar = escrever(OperacaoPatch.REPLACE, "goal", "status", "concluido")
    assert not _submeter(kernel, PapelAutor.ARBITRO, "arbitro-1#aaaa", fechar).sucesso
    mudanca = escrever(OperacaoPatch.REPLACE, ID_GOVERNANCA_GLOBAL, "preset", "arbitragem_maxima")
    assert _submeter(kernel, PapelAutor.HUMANO, "david", mudanca).sucesso
    depois = kernel.obter_estado().versao_log
    assert _submeter(kernel, PapelAutor.ARBITRO, "arbitro-1#aaaa", fechar).sucesso
    motor = ReplayEngine(kernel.repositorio)
    for versao, esperado in ((antes, False), (depois, True)):
        estado = motor.reproduzir_ate_seq("main", versao)
        for _ in range(2):
            proposta = _proposta(PapelAutor.ARBITRO, "arbitro-1#aaaa", fechar)
            assert RoleGate().validar(proposta, estado).aprovado is esperado


def test_o_separador_do_sufixo_acompanha_o_da_conexao_mcp_edge_case() -> None:
    """Caso de borda: o kernel não importa o servidor MCP, então a cópia da constante é conferida aqui."""
    assert SEPARADOR_DO_SUFIXO_DE_CONEXAO == SEPARADOR_DO_MCP


@pytest.mark.parametrize(("autor", "aberta_por", "esperado"), [
    ("arbitro-1#aaaa", "arbitro-1#bbbb", True),
    ("arbitro-1", "arbitro-1#bbbb", True),
    ("arbitro-1#aaaa", "arbitro-1", True),
    ("arbitro-1#aaaa", "arbitro-2#aaaa", False),
    ("arbitro-1", None, False),
    ("arbitro-1", "", False),
    ("", "", False),
])
def test_autoria_propria_compara_sem_o_sufixo_edge_case(autor: str, aberta_por: Any, esperado: bool) -> None:
    """Caso de borda: o sufixo da conexão muda a cada processo, o nome declarado fica."""
    assert eh_autoria_propria(autor, aberta_por) is esperado
    assert autor_sem_sufixo_de_conexao("a#b") == "a"
    assert autor_sem_sufixo_de_conexao("a") == "a"


def _proposta(papel: PapelAutor, autor: str, *operacoes: ItemPatch) -> PropostaPatch:
    """Proposta pronta para o portão."""
    return PropostaPatch.criar(DadosPropostaPatch(autor=autor, papel=papel, operacoes=operacoes, justificativa="teste"))


def _submeter(kernel: Any, papel: PapelAutor, autor: str, *operacoes: ItemPatch) -> Any:
    """Submete o lote ao kernel sob o papel e o autor dados."""
    return kernel.submeter_patch(_proposta(papel, autor, *operacoes))
