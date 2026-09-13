"""Testes da seção de panorama: agregação, teto de filhos e o que nunca é cortado."""

from graphow.context.panorama import (
    LIMITE_DE_FILHOS_NOMEADOS_POR_TIPO,
    FilhoResumido,
    montar_secao_de_panorama,
    ordenar_por_urgencia,
)
from graphow.context.secoes import PrioridadeRetencao
from graphow.core.models import NoGrafo
from graphow.core.types import StatusTask, TipoNo
from graphow.projection.rollup import ResumoDeSubarvore


def _no(id_no: str, tipo: TipoNo = TipoNo.ARTIFACT, **propriedades: str) -> NoGrafo:
    """Nó mínimo para montar o panorama."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=f"Rotulo {id_no}", propriedades=dict(propriedades))


def _resumo(id_no: str, concluidas: int, abertas: int) -> ResumoDeSubarvore:
    """Resumo de subárvore com a distribuição de tarefas pedida."""
    por_status: dict[str, int] = {}
    if concluidas:
        por_status[StatusTask.CONCLUIDO.value] = concluidas
    if abertas:
        por_status[StatusTask.PENDENTE.value] = abertas
    return ResumoDeSubarvore(
        id=id_no, total_nos=concluidas + abertas + 1, tarefas_por_status=por_status
    )


def test_filho_com_subarvore_traz_o_agregado_na_linha() -> None:
    """A linha do contêiner precisa dizer o progresso sem que ele seja aberto."""
    filho = FilhoResumido(_no("setor-a", TipoNo.SETOR), _resumo("setor-a", concluidas=3, abertas=2))

    linha = filho.formatar()

    assert "3/5 tarefas concluidas" in linha
    assert "2 abertas" in linha
    assert "trabalho aberto" in linha


def test_filho_folha_mantem_o_proprio_status_na_linha() -> None:
    """Sem isso o panorama diria menos que a lista de vizinhos que ele substituiu."""
    filho = FilhoResumido(_no("t1", TipoNo.TASK, status=StatusTask.PENDENTE.value), None)

    assert "[pendente]" in filho.formatar()


def test_tarefa_pendente_sem_subarvore_conta_como_trabalho_aberto() -> None:
    """Uma Task folha e pendente é exatamente o que o agente precisa ver."""
    aberta = FilhoResumido(_no("t1", TipoNo.TASK, status=StatusTask.PENDENTE.value), None)
    fechada = FilhoResumido(_no("t2", TipoNo.TASK, status=StatusTask.CONCLUIDO.value), None)

    assert aberta.tem_trabalho_aberto is True
    assert fechada.tem_trabalho_aberto is False


def test_quem_tem_trabalho_aberto_aparece_primeiro() -> None:
    """A ordem é o que orienta a descida: o pendente antes do encerrado."""
    encerrado = FilhoResumido(_no("a-setor", TipoNo.SETOR), _resumo("a-setor", 2, 0))
    pendente = FilhoResumido(_no("z-setor", TipoNo.SETOR), _resumo("z-setor", 1, 1))

    ordenados = ordenar_por_urgencia([encerrado, pendente])

    assert [filho.no.id for filho in ordenados] == ["z-setor", "a-setor"]


def test_teto_limita_quantas_folhas_o_panorama_nomeia() -> None:
    """Sem teto, o panorama de uma Sessão volta a ser a lista crua."""
    filhos = [FilhoResumido(_no(f"art-{i}"), None) for i in range(12)]

    secao = montar_secao_de_panorama(filhos)

    nomeados = [linha for linha in secao.linhas if linha.startswith("- [")]
    assert len(nomeados) == LIMITE_DE_FILHOS_NOMEADOS_POR_TIPO
    assert any("e mais 7 do tipo Artifact" in linha for linha in secao.linhas)


def test_teto_nunca_esconde_quem_tem_trabalho_aberto() -> None:
    """Cortar o nó pendente devolveria o agente à varredura."""
    abertas = [
        FilhoResumido(_no(f"t{i}", TipoNo.TASK, status=StatusTask.PENDENTE.value), None)
        for i in range(8)
    ]

    secao = montar_secao_de_panorama(abertas)

    assert len(secao.ids_incluidos) == 8
    assert not any("e mais" in linha for linha in secao.linhas)


def test_panorama_retem_como_navegacao() -> None:
    """É a afordância de descida: descartá-la cega o agente antes da hora."""
    secao = montar_secao_de_panorama([FilhoResumido(_no("a"), None)])

    assert secao.prioridade_retencao == PrioridadeRetencao.NAVEGACAO
    assert secao.pode_encolher is True


def test_panorama_sem_filhos_fica_vazio_e_nao_e_renderizado() -> None:
    """Um nó folha não deve ganhar um cabeçalho de seção vazio."""
    secao = montar_secao_de_panorama([])

    assert secao.esta_vazia is True
