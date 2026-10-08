"""Testes do protocolo de memória: o texto que chega ao agente sem ninguém lembrar de mandá-lo."""

from graphow.context.protocolo import TITULO_DO_PROTOCOLO, montar_protocolo
from graphow.core.governanca import PresetGovernanca, compor_politica_global, politica_do_preset, politica_padrao
from graphow.core.types import PapelAutor

GESTOS_HUMANOS_DE_SEMPRE: str = "Promover aprendizado e encerrar a sessao sao gestos humanos"


def test_protocolo_nomeia_as_ferramentas_da_memoria_nominal() -> None:
    """Quem lê o protocolo sabe por qual ferramenta cada passo acontece."""
    texto = "\n".join(montar_protocolo())

    assert texto.startswith(TITULO_DO_PROTOCOLO)
    for ferramenta in ("`ler_vista`", "`propor_patch`", "`abrir_questao`", "`registrar_aprendizado`"):
        assert ferramenta in texto
    assert "condensacao_de_sessao" in texto


def test_protocolo_cita_a_sessao_quando_o_hook_a_conhece_nominal() -> None:
    """O hook sabe o id da sessão; o MCP não. A linha de leitura muda só nisso."""
    com_sessao = montar_protocolo(id_sessao="sess-1")
    sem_sessao = montar_protocolo()

    assert "`ler_vista` na sessao sess-1" in com_sessao[1]
    assert "sess-1" not in "\n".join(sem_sessao)
    assert len(com_sessao) == len(sem_sessao)


def test_linha_do_papel_sai_do_role_gate_nominal() -> None:
    """O planejador cria Evidence localizada e não registra Aprendizado, e o texto diz isso antes do portão."""
    executor = montar_protocolo(papel=PapelAutor.EXECUTOR)[-1]
    planejador = montar_protocolo(papel=PapelAutor.PLANEJADOR)[-1]

    assert "`executor`" in executor
    assert "Evidence" in executor
    assert "registra Aprendizado" in executor
    assert "evidencia_sem_localizacao" not in executor
    assert "`planejador`" in planejador
    assert "cria Evidence" in planejador
    assert "`trecho`" in planejador
    assert "evidencia_sem_localizacao" in planejador
    assert "nao registra Aprendizado" in planejador


def test_humano_nao_recebe_linha_de_papel_edge_case() -> None:
    """Caso de borda: o humano cria tudo; uma linha de restrição seria mentira."""
    assert montar_protocolo(papel=PapelAutor.HUMANO) == montar_protocolo()


def test_protocolo_e_ascii_edge_case() -> None:
    """Caso de borda: o texto atravessa a saída padrão do hook, cuja codificação ninguém controla."""
    for linha in montar_protocolo(papel=PapelAutor.REVISOR, id_sessao="sess-1"):
        assert linha.isascii(), linha


def test_protocolo_diz_como_consolidar_aprendizados_nominal() -> None:
    """O agente que pega a Task de consolidar sabe pelo protocolo que registra com substitui."""
    texto = "\n".join(montar_protocolo())

    assert "consolidar aprendizados" in texto
    assert "substitui = os ids absorvidos" in texto


def test_governanca_maxima_mantem_o_texto_de_sempre_nominal() -> None:
    """Em governança máxima, com ou sem política explícita, o último passo é o texto de antes."""
    padrao = montar_protocolo()
    explicita = montar_protocolo(politica=politica_do_preset(PresetGovernanca.GOVERNANCA_MAXIMA))

    assert explicita == padrao == montar_protocolo(politica=politica_padrao())
    assert GESTOS_HUMANOS_DE_SEMPRE in padrao[-1]
    assert "arbitro" not in "\n".join(padrao)


def test_arbitragem_maxima_cita_os_gestos_do_arbitro_e_o_que_segue_humano_nominal() -> None:
    """Com o árbitro, o protocolo não afirma que promover e encerrar são do humano."""
    linhas = montar_protocolo(politica=politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA))
    passo = linhas[-1]

    assert GESTOS_HUMANOS_DE_SEMPRE not in "\n".join(linhas)
    assert passo.startswith("6. ")
    for gesto in ("responder_questao", "promover_aprendizado", "encerrar_sessao", "excluir", "integracao"):
        assert gesto in passo.split("Seguem humanos:")[0], gesto
    assert "Governanca arbitragem_maxima" in passo
    assert "Seguem humanos: promocao global de aprendizado e a configuracao da governanca, responder_desvio;" in passo
    assert "aprovar_plano" in passo.split("Seguem humanos:")[0]


def test_personalizada_separa_o_que_e_do_arbitro_do_que_segue_humano_nominal() -> None:
    """Numa personalizada o gesto entregue vai para o árbitro, e o resto segue na lista dos humanos."""
    politica = compor_politica_global({"preset": "personalizada", "personalizada": {"excluir": "arbitro"}})

    passo = montar_protocolo(politica=politica)[-1]
    do_arbitro, humanos = passo.split("Seguem humanos:")

    assert "Governanca personalizada" in passo
    assert "gestos com o arbitro: excluir." in do_arbitro
    assert "promover_aprendizado" in humanos
    assert "encerrar_sessao" in humanos
    assert "excluir" not in humanos


def test_politica_sem_gesto_do_arbitro_diz_nenhum_edge_case() -> None:
    """Caso de borda: personalizada que só mexe na estrutura não lista gesto nenhum para o árbitro."""
    politica = compor_politica_global({"preset": "personalizada", "personalizada": {"estrutura": "ilimitado"}})

    passo = montar_protocolo(politica=politica)[-1]

    assert "gestos com o arbitro: nenhum." in passo


def test_protocolo_com_governanca_e_ascii_edge_case() -> None:
    """Caso de borda: o passo de governança também atravessa a saída padrão do hook."""
    politica = politica_do_preset(PresetGovernanca.ARBITRAGEM_MAXIMA)

    for linha in montar_protocolo(papel=PapelAutor.ARBITRO, id_sessao="sess-1", politica=politica):
        assert linha.isascii(), linha
