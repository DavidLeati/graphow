"""Testes do braço de retomada: a sessão encerrada custa menos pela vista do que nó a nó."""

from graphow.avaliacao import executar_avaliacao
from graphow.avaliacao.cenario_memoria import (
    ID_NOTA_DE_CONDENSACAO,
    ids_de_conhecimento_do_corpus,
    montar_cenario_com_memoria,
)
from graphow.avaliacao.retomada import MedicaoDeRetomada, MedidorDeRetomada
from graphow.avaliacao.tarefas_gravadas import ID_SESSAO, TAREFAS_GRAVADAS, montar_cenario_gravado
from graphow.core.types import StatusSessao, TipoAresta, TipoNo


def test_cenario_com_memoria_encerra_e_condensa_a_sessao_nominal() -> None:
    """A extensão deixa a sessão encerrada e a condensação apontando para cada nó de conhecimento."""
    view = montar_cenario_com_memoria().obter_view()

    sessao = view.obter_no(ID_SESSAO)
    assert sessao is not None
    assert sessao.obter_propriedade("status") == StatusSessao.CONCLUIDA.value
    destinos = {aresta.destino_id for aresta in view.obter_arestas_saida(ID_NOTA_DE_CONDENSACAO, TipoAresta.DERIVA_DE)}
    assert destinos == set(ids_de_conhecimento_do_corpus())


def test_cenario_base_continua_intocado_edge_case() -> None:
    """Caso de borda: o braço original mede o mesmo grafo de sempre, sem a camada de memória."""
    view = montar_cenario_gravado().obter_view()

    assert view.obter_no(ID_SESSAO).obter_propriedade("status") == "ativa"
    assert view.contem_no(ID_NOTA_DE_CONDENSACAO) is False
    assert len(view.listar_nos_por_tipo(TipoNo.TASK)) == len(TAREFAS_GRAVADAS)


def test_retomar_pela_vista_custa_menos_que_ler_no_a_no_nominal() -> None:
    """É a comparação que a etapa 2 promete: a Note contra as Evidence uma a uma."""
    medicao = MedidorDeRetomada(montar_cenario_com_memoria()).medir()

    assert medicao.tokens_pela_vista < medicao.tokens_no_a_no
    assert medicao.nos_lidos_um_a_um == len(ids_de_conhecimento_do_corpus())
    assert 0.0 < medicao.reducao < 1.0


def test_vista_da_sessao_encerrada_entrega_toda_decisao_vigente_e_a_condensacao_nominal() -> None:
    """Economizar tokens só vale se nada do que importa ficou de fora."""
    medicao = MedidorDeRetomada(montar_cenario_com_memoria()).medir()

    assert medicao.decisoes_vigentes == sum(len(tarefa.decisoes) for tarefa in TAREFAS_GRAVADAS)
    assert medicao.cobertura_completa is True


def test_relatorio_publica_o_braco_de_retomada_nominal() -> None:
    """O número novo viaja no mesmo relatório, com os mesmos limites declarados."""
    relatorio = executar_avaliacao()

    assert relatorio.retomada is not None
    texto = "\n".join(relatorio.formatar())
    assert "RETOMADA DE SESSAO ENCERRADA" in texto
    assert "No a no" in texto


def test_reducao_sem_base_e_zero_edge_case() -> None:
    """Caso de borda: sem nó a ler não se inventa economia."""
    medicao = MedicaoDeRetomada(
        id_sessao="x",
        tokens_pela_vista=10,
        tokens_no_a_no=0,
        nos_lidos_um_a_um=0,
        decisoes_vigentes=0,
        decisoes_entregues=0,
        condensacao_entregue=False,
    )

    assert medicao.reducao == 0.0
    assert medicao.cobertura_completa is False
