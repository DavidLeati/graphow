"""A política de governança de um nó é a do Projeto que o contém, e nenhuma outra aresta a muda.

Segurança: uma Decision de um Projeto em arbitragem_maxima que orienta a Task de
outro Projeto, em governanca_maxima, não pode puxar a política permissiva para
o alvo. Só `contem`, `produz` e `decompoe` dizem a qual Projeto o nó pertence.
"""

from graphow.core.governanca import Gesto
from graphow.core.models import GrafoEstado
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.politica_governanca import resolver_politica_do_no
from graphow.kernel.rastreio_projeto import RastreadorProjetoAncestral
from tests.kernel.cenario_governanca import (
    PRESET_ARBITRAGEM,
    PRESET_MAXIMA,
    aresta,
    montar_estado,
    no,
    remover_aresta,
    remover_no,
    validar,
)


def _com_projeto_b_orientando_a_task_de_a(*, projeto_b_perto: bool) -> GrafoEstado:
    """Projeto A em governanca_maxima e Projeto B em arbitragem_maxima, cuja Decision orienta a Task `t` de A.

    Com `projeto_b_perto`, B contém a Decision direto (dois saltos até `t`, contra
    três saltos de A): a busca antiga, que subia por qualquer aresta, achava B.
    Sem ele, a Decision vem de uma Sessao de B, no mesmo nível de profundidade.
    """
    base = montar_estado(global_=PRESET_MAXIMA, governanca=PRESET_MAXIMA)
    nos = {**base.nos, "proj-b": no("proj-b", TipoNo.PROJETO, governanca=PRESET_ARBITRAGEM)}
    nos["dec-b"] = no("dec-b", TipoNo.DECISION)
    arestas = {"orienta-b-t": aresta("orienta-b-t", "dec-b", "t", TipoAresta.ORIENTA), **base.arestas}
    if projeto_b_perto:
        arestas["cont-b-dec"] = aresta("cont-b-dec", "proj-b", "dec-b", TipoAresta.CONTEM)
    else:
        nos["sess-b"] = no("sess-b", TipoNo.SESSAO, status="ativa")
        arestas["cont-b-sess"] = aresta("cont-b-sess", "proj-b", "sess-b", TipoAresta.CONTEM)
        arestas["prod-b-dec"] = aresta("prod-b-dec", "sess-b", "dec-b", TipoAresta.PRODUZ)
    return GrafoEstado(nos=nos, arestas=arestas)


def test_orienta_de_outro_projeto_nao_entrega_o_arbitro_a_task_edge_case() -> None:
    """Caso de borda: a Decision de B orienta a Task de A, e o árbitro segue sem gesto algum sobre ela."""
    for projeto_b_perto in (True, False):
        estado = _com_projeto_b_orientando_a_task_de_a(projeto_b_perto=projeto_b_perto)

        assert RastreadorProjetoAncestral().rastrear("t", estado) == "proj", projeto_b_perto
        assert not resolver_politica_do_no("t", estado, RastreadorProjetoAncestral()).permite(
            Gesto.EXCLUIR, PapelAutor.ARBITRO
        )
        assert not validar(PapelAutor.ARBITRO, estado, remover_no("t")).aprovado, projeto_b_perto
        assert not validar(PapelAutor.ARBITRO, estado, remover_aresta("bloqueia-q-t")).aprovado, projeto_b_perto


def test_orienta_de_outro_projeto_nao_tira_o_gesto_do_proprio_arbitro_nominal() -> None:
    """O mesmo estado, visto da Task de B: o árbitro continua com o gesto no projeto que o concede."""
    estado = _com_projeto_b_orientando_a_task_de_a(projeto_b_perto=True)
    nos = {**estado.nos, "t-b": no("t-b", TipoNo.TASK, status="pendente")}
    arestas = {**estado.arestas, "cont-b-t-b": aresta("cont-b-t-b", "proj-b", "t-b", TipoAresta.CONTEM)}
    com_task_de_b = GrafoEstado(nos=nos, arestas=arestas)

    assert validar(PapelAutor.ARBITRO, com_task_de_b, remover_no("t-b")).aprovado
    assert not validar(PapelAutor.ARBITRO, com_task_de_b, remover_no("t")).aprovado


def test_outras_arestas_de_entrada_tambem_nao_decidem_o_projeto_edge_case() -> None:
    """Caso de borda: deriva_de, justifica e bloqueia vindas de B não puxam a política de B para `t`."""
    base = _com_projeto_b_orientando_a_task_de_a(projeto_b_perto=True)
    arestas = dict(base.arestas)
    for tipo in (TipoAresta.DERIVA_DE, TipoAresta.JUSTIFICA, TipoAresta.BLOQUEIA):
        id_aresta = f"{tipo.value}-b-t"
        arestas[id_aresta] = aresta(id_aresta, "dec-b", "t", tipo)
    estado = GrafoEstado(nos=base.nos, arestas=arestas)

    assert RastreadorProjetoAncestral().rastrear("t", estado) == "proj"
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("t")).aprovado
