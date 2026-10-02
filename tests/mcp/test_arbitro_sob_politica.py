"""Testes do árbitro na camada MCP: as ferramentas que eram só do humano seguem a política do alvo."""

import pytest

from graphow.api.cli_parser import PAPEIS_ACEITOS_NO_MCP
from graphow.core.exceptions import ErroPermissaoPapel
from graphow.core.types import PapelAutor, TipoAresta
from graphow.mcp.identidade_sessao import (
    GESTO_POR_FERRAMENTA,
    IdentidadeSessaoMCP,
    PoliticaIdentidadeMCP,
)
from tests.mcp.cenario_governanca import (
    AUTOR_DO_ARBITRO,
    DONO_DA_POSSE,
    PRESETS_FIXOS,
    abrir_questao_como_agente,
    chamadas_do_gesto,
    definir_preset_do_projeto,
    definir_preset_global,
    montar_kernel,
    registrar_aprendizado_como_agente,
    servidor,
)

FERRAMENTAS_SOB_POLITICA = sorted(GESTO_POR_FERRAMENTA)
PAPEIS_DE_AGENTE_SEM_GESTO = ("planejador", "executor", "revisor")


def test_sessao_arbitro_abre_nominal() -> None:
    """O papel arbitro é aceito na abertura da sessão MCP e na linha de comando."""
    identidade = IdentidadeSessaoMCP.criar("arbitro-1", "arbitro")

    assert identidade.papel == PapelAutor.ARBITRO
    assert identidade.eh_humano is False
    assert "arbitro" in PAPEIS_ACEITOS_NO_MCP


def test_papel_sistema_segue_recusado_em_sessao_edge_case() -> None:
    """Caso de borda: abrir ao árbitro não abre a porta do papel de sistema."""
    with pytest.raises(ErroPermissaoPapel):
        IdentidadeSessaoMCP.criar("harness", "sistema")


def test_arbitro_responde_question_e_grava_o_papel_nominal() -> None:
    """Em arbitragem_maxima o árbitro encerra a dúvida de outro autor, e o papel fica no log."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    id_questao = abrir_questao_como_agente(kernel)

    resposta = servidor(kernel, "arbitro").executar_ferramenta(
        "responder_questao", {"id_questao": id_questao, "resposta": "Siga"}
    )

    assert resposta["sucesso"] is True, resposta
    questao = kernel.obter_view().obter_no(id_questao)
    assert questao.obter_propriedade("status") == "respondida"
    assert questao.obter_propriedade("respondida_por") == AUTOR_DO_ARBITRO
    assert questao.obter_propriedade("respondida_por_papel") == "arbitro"


def test_humano_responde_e_grava_o_papel_humano_nominal() -> None:
    """A resposta do humano também leva o papel, para o selo da UI distinguir as duas."""
    kernel = montar_kernel()
    id_questao = abrir_questao_como_agente(kernel)

    resposta = servidor(kernel, "humano").executar_ferramenta(
        "responder_questao", {"id_questao": id_questao, "resposta": "Siga"}
    )

    assert resposta["sucesso"] is True, resposta
    assert kernel.obter_view().obter_no(id_questao).obter_propriedade("respondida_por_papel") == "humano"


def test_arbitro_nao_responde_a_question_que_ele_abriu_edge_case() -> None:
    """Caso de borda: o anti-autoconflito é do kernel, e a camada MCP o deixa falar."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    aberta = servidor(kernel, "arbitro").executar_ferramenta(
        "abrir_questao", {"pergunta": "Posso?", "id_no_bloqueado": "task-a", "id_sessao": "sess-a"}
    )

    resposta = servidor(kernel, "arbitro").executar_ferramenta(
        "responder_questao", {"id_questao": aberta["id_questao"], "resposta": "Pode"}
    )

    assert resposta["sucesso"] is False
    assert kernel.obter_view().obter_no(aberta["id_questao"]).obter_propriedade("status") == "aberta"


def test_arbitro_promove_ao_setor_e_grava_quem_promoveu_nominal() -> None:
    """O árbitro cria o vale_para ao Setor da origem, sem tocar o alcance global."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    id_aprendizado = registrar_aprendizado_como_agente(kernel)

    resposta = servidor(kernel, "arbitro").executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": id_aprendizado}
    )

    assert resposta["sucesso"] is True, resposta
    view = kernel.obter_view()
    destinos = {a.destino_id for a in view.obter_arestas_saida(id_aprendizado, TipoAresta.VALE_PARA)}
    assert destinos == {"setor-a"}
    aprendizado = view.obter_no(id_aprendizado)
    assert aprendizado.obter_propriedade("promovido_por") == AUTOR_DO_ARBITRO
    assert aprendizado.obter_propriedade("promovido_por_papel") == "arbitro"
    assert aprendizado.obter_propriedade("alcance") is None


def test_humano_promove_e_grava_o_papel_humano_nominal() -> None:
    """A promoção do humano leva o papel humano; a global grava o alcance."""
    kernel = montar_kernel()
    id_aprendizado = registrar_aprendizado_como_agente(kernel)

    resposta = servidor(kernel, "humano").executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": id_aprendizado, "global": True}
    )

    assert resposta["sucesso"] is True, resposta
    aprendizado = kernel.obter_view().obter_no(id_aprendizado)
    assert aprendizado.obter_propriedade("promovido_por") == "david"
    assert aprendizado.obter_propriedade("promovido_por_papel") == "humano"
    assert aprendizado.obter_propriedade("alcance") == "global"


def test_arbitro_nao_promove_aprendizado_que_ele_registrou_edge_case() -> None:
    """Caso de borda: o árbitro que registrou o aprendizado não o promove, e quem barra é o kernel."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    registro = servidor(kernel, "arbitro").executar_ferramenta(
        "registrar_aprendizado", {"afirmacao": "Licao", "id_sessao": "sess-a", "origens": ["dec-a"]}
    )

    resposta = servidor(kernel, "arbitro", "arbitro-1").executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": registro["id_aprendizado"]}
    )

    assert resposta["sucesso"] is False
    assert "causa propria" in resposta["mensagem"]
    assert not kernel.obter_view().obter_arestas_saida(registro["id_aprendizado"], TipoAresta.VALE_PARA)


def test_arbitro_encerra_sessao_exclui_e_libera_posse_nominal() -> None:
    """Em arbitragem_maxima o árbitro encerra, exclui e libera a posse de outro autor."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    arbitro = servidor(kernel, "arbitro")

    encerrada = arbitro.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess-a"})
    em_lote = arbitro.executar_ferramenta("excluir_em_lote", {"ids_nos": ["dec-a"]})
    liberada = arbitro.executar_ferramenta("liberar_tarefa", {"id_task": "task-a"})
    arbitro.executar_ferramenta("liberar_tarefa", {"id_task": "task-b"})
    excluida = arbitro.executar_ferramenta("excluir_projeto", {"id_projeto": "proj-b"})

    assert encerrada["sucesso"] is True, encerrada
    assert em_lote["sucesso"] is True, em_lote
    assert liberada["sucesso"] is True, liberada
    assert excluida["sucesso"] is True, excluida
    view = kernel.obter_view()
    assert view.obter_no("sess-a").obter_propriedade("status") == "concluida"
    assert not view.contem_no("dec-a")
    assert not view.contem_no("proj-b")
    assert kernel.obter_dono_do_lock("task-a") is None


def test_arbitro_e_recusado_em_governanca_maxima_nominal() -> None:
    """Sem nó global vale governanca_maxima: o árbitro é recusado em todas as ferramentas sob política."""
    kernel = montar_kernel()
    chamadas = chamadas_do_gesto(kernel)
    arbitro = servidor(kernel, "arbitro")

    for ferramenta, argumentos in chamadas.items():
        resposta = arbitro.executar_ferramenta(ferramenta, argumentos)
        assert resposta["sucesso"] is False, ferramenta
        assert f"gesto '{GESTO_POR_FERRAMENTA[ferramenta].value}'" in resposta["erro"], ferramenta
        assert "abrir_questao" in resposta["erro"], ferramenta
    liberada = arbitro.executar_ferramenta("liberar_tarefa", {"id_task": "task-a"})
    assert liberada["sucesso"] is False
    assert kernel.obter_dono_do_lock("task-a") == DONO_DA_POSSE
    assert kernel.obter_view().contem_no("proj-a")


def test_arbitro_e_recusado_com_global_true_mesmo_em_arbitragem_maxima_edge_case() -> None:
    """Caso de borda: a promoção global é sempre do humano, em qualquer preset."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    id_aprendizado = registrar_aprendizado_como_agente(kernel)

    resposta = servidor(kernel, "arbitro").executar_ferramenta(
        "promover_aprendizado", {"id_aprendizado": id_aprendizado, "global": True}
    )

    assert resposta["sucesso"] is False
    assert "global" in resposta["erro"]
    assert kernel.obter_view().obter_no(id_aprendizado).obter_propriedade("alcance") is None


@pytest.mark.parametrize("preset", PRESETS_FIXOS)
@pytest.mark.parametrize("papel", PAPEIS_DE_AGENTE_SEM_GESTO)
def test_planejador_executor_e_revisor_sao_recusados_em_qualquer_preset_edge_case(papel: str, preset: str) -> None:
    """Caso de borda: abrir o gesto ao árbitro não o abre aos outros papéis de agente."""
    kernel = montar_kernel()
    definir_preset_global(kernel, preset)
    chamadas = chamadas_do_gesto(kernel)
    sessao = servidor(kernel, papel)

    for ferramenta, argumentos in chamadas.items():
        resposta = sessao.executar_ferramenta(ferramenta, argumentos)
        assert resposta["sucesso"] is False, (papel, preset, ferramenta)
        assert f"gesto '{GESTO_POR_FERRAMENTA[ferramenta].value}'" in resposta["erro"]
    assert kernel.obter_dono_do_lock("task-a") == DONO_DA_POSSE
    assert sessao.executar_ferramenta("liberar_tarefa", {"id_task": "task-a"})["sucesso"] is False
    assert kernel.obter_dono_do_lock("task-a") == DONO_DA_POSSE


def test_recusa_ao_agente_aponta_o_arbitro_quando_a_politica_o_entrega_nominal() -> None:
    """A mensagem diz o caminho: o árbitro em arbitragem_maxima, abrir_questao em governanca_maxima."""
    kernel = montar_kernel()
    definir_preset_do_projeto(kernel, "proj-a", "arbitragem_maxima")
    executor = servidor(kernel, "executor")

    com_arbitro = executor.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess-a"})
    sem_arbitro = executor.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess-b"})

    assert "arbitro" in com_arbitro["erro"] and "abrir_questao" not in com_arbitro["erro"]
    assert "abrir_questao" in sem_arbitro["erro"]


def test_excluir_em_lote_exige_todos_os_ids_permitidos_edge_case() -> None:
    """Caso de borda: com um id sob governanca_maxima o lote inteiro é recusado, sem excluir nada."""
    kernel = montar_kernel()
    definir_preset_do_projeto(kernel, "proj-a", "arbitragem_maxima")
    definir_preset_do_projeto(kernel, "proj-b", "governanca_maxima")
    arbitro = servidor(kernel, "arbitro")

    misto = arbitro.executar_ferramenta("excluir_em_lote", {"ids_nos": ["dec-a", "dec-b"]})
    permitido = arbitro.executar_ferramenta("excluir_em_lote", {"ids_nos": ["dec-a"]})

    assert misto["sucesso"] is False
    assert kernel.obter_view().contem_no("dec-b")
    assert permitido["sucesso"] is True, permitido
    assert not kernel.obter_view().contem_no("dec-a")


def test_politica_do_projeto_vence_a_global_para_o_arbitro_nominal() -> None:
    """Global em arbitragem_maxima, mas um Projeto em governanca_maxima: o árbitro só age no outro."""
    kernel = montar_kernel()
    definir_preset_global(kernel, "arbitragem_maxima")
    definir_preset_do_projeto(kernel, "proj-b", "governanca_maxima")
    arbitro = servidor(kernel, "arbitro")

    no_travado = arbitro.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess-b"})
    no_livre = arbitro.executar_ferramenta("encerrar_sessao", {"id_sessao": "sess-a"})

    assert no_travado["sucesso"] is False
    assert no_livre["sucesso"] is True, no_livre


def test_veredito_da_politica_e_puro_dado_o_resolvedor_nominal() -> None:
    """A PoliticaIdentidadeMCP sem resolvedor assume governanca_maxima e não toca em estado."""
    politica = PoliticaIdentidadeMCP()
    arbitro = IdentidadeSessaoMCP.criar("arbitro-1", "arbitro")
    humano = IdentidadeSessaoMCP.criar("david", "humano")

    assert politica.autorizar("responder_questao", arbitro, {"id_questao": "q"}).autorizado is False
    assert politica.autorizar("responder_questao", humano, {"id_questao": "q"}).autorizado is True
    assert politica.autorizar("configurar_governanca", arbitro).autorizado is False
    assert politica.autorizar("ler_vista", arbitro).autorizado is True
