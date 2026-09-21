"""Testes do protocolo de memória: o texto que chega ao agente sem ninguém lembrar de mandá-lo."""

from graphow.context.protocolo import TITULO_DO_PROTOCOLO, montar_protocolo
from graphow.core.types import PapelAutor


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
    """O planejador não cria Evidence nem registra Aprendizado, e o texto diz isso antes do portão."""
    executor = montar_protocolo(papel=PapelAutor.EXECUTOR)[-1]
    planejador = montar_protocolo(papel=PapelAutor.PLANEJADOR)[-1]

    assert "`executor`" in executor
    assert "Evidence" in executor
    assert "registra Aprendizado" in executor
    assert "`planejador`" in planejador
    assert "Evidence" not in planejador
    assert "nao registra Aprendizado" in planejador


def test_humano_nao_recebe_linha_de_papel_edge_case() -> None:
    """Caso de borda: o humano cria tudo; uma linha de restrição seria mentira."""
    assert montar_protocolo(papel=PapelAutor.HUMANO) == montar_protocolo()


def test_protocolo_e_ascii_edge_case() -> None:
    """Caso de borda: o texto atravessa a saída padrão do hook, cuja codificação ninguém controla."""
    for linha in montar_protocolo(papel=PapelAutor.REVISOR, id_sessao="sess-1"):
        assert linha.isascii(), linha
