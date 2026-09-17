"""Testes do braço entre projetos: o aprendizado do primeiro projeto chega à tarefa do segundo."""

from collections.abc import Sequence

from graphow.avaliacao import executar_avaliacao
from graphow.avaliacao.cenario_entre_projetos import (
    ID_APRENDIZADO_ISOLADO,
    TAREFAS_ENTRE_PROJETOS,
    montar_cenario_entre_projetos,
)
from graphow.avaliacao.entre_projetos import ORCAMENTO_ENTRE_PROJETOS, MedidorEntreProjetos
from graphow.context.materializer import MaterializadorContexto
from graphow.context.memoria import IndiceSemantico
from graphow.core.models import NoGrafo


def test_heranca_e_lexico_entregam_dois_dos_tres_aprendizados_nominal() -> None:
    """Herança resolve o global; o léxico atravessa o projeto pela palavra em comum; o resto não chega."""
    relatorio = MedidorEntreProjetos(montar_cenario_entre_projetos()).medir_todas()

    por_tarefa = {medicao.id_tarefa: medicao for medicao in relatorio.medicoes}
    assert por_tarefa["t2-spans"].chegou is True
    assert por_tarefa["t2-cache"].chegou is True
    assert por_tarefa["t2-migracao"].chegou is False
    assert relatorio.acertos == 2
    assert relatorio.indice_semantico == "nulo"


def test_aprendizado_chega_dentro_do_orcamento_e_abaixo_do_despejo_nominal() -> None:
    """A tarefa recebe o aprendizado em 1500 tokens, muito abaixo de despejar o primeiro projeto."""
    relatorio = MedidorEntreProjetos(montar_cenario_entre_projetos()).medir_todas()

    for medicao in relatorio.medicoes:
        assert medicao.tokens_pela_vista <= ORCAMENTO_ENTRE_PROJETOS
        assert medicao.tokens_pela_vista < medicao.tokens_despejo_do_primeiro_projeto
        assert medicao.tokens_busca_cega > 0


class _IndiceQueConheceOIsolado(IndiceSemantico):
    """Índice de teste que sugere o aprendizado que herança e léxico não alcançam."""

    def sugerir(self, texto: str, candidatos: Sequence[NoGrafo]) -> tuple[str, ...]:
        """Sugere o aprendizado isolado para qualquer tarefa."""
        return (ID_APRENDIZADO_ISOLADO,)

    def descrever(self) -> str:
        """Nome do índice de teste."""
        return "fixo"


def test_indice_semantico_injetado_fecha_a_lacuna_nominal() -> None:
    """É o ponto de injeção da etapa 4: com um índice, a terceira tarefa também é atendida."""
    materializador = MaterializadorContexto(indice_semantico=_IndiceQueConheceOIsolado())

    relatorio = MedidorEntreProjetos(montar_cenario_entre_projetos(), materializador).medir_todas()

    assert relatorio.acertos == len(TAREFAS_ENTRE_PROJETOS)
    assert relatorio.indice_semantico == "fixo"


def test_relatorio_publica_o_braco_entre_projetos_nominal() -> None:
    """O número viaja no relatório de `graphow avaliar`, com a taxa de acerto declarada."""
    texto = "\n".join(executar_avaliacao().formatar())

    assert "ENTRE PROJETOS" in texto
    assert "Taxa de acerto: 2/3" in texto
