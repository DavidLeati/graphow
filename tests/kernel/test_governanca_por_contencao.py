"""A política de governança de um nó é a do Projeto que o contém, e nenhuma outra aresta a muda.

Segurança: uma Decision de um Projeto em arbitragem_maxima que orienta a Task de
outro Projeto, em governanca_maxima, não pode puxar a política permissiva para
o alvo. Só `contem`, `produz` e `decompoe` dizem a qual Projeto o nó pertence.
"""

from typing import Any

import pytest

from graphow.core.governanca import GESTOS_POR_PAPEL, Gesto
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


def _com_goal_de_b_decompondo_a_task_de_a(
    *, id_b: str, intermediarios: int, preset_a: dict[str, Any], preset_b: dict[str, Any]
) -> GrafoEstado:
    """A Task `t` do Projeto A, decomposta por um Goal do Projeto B a `intermediarios` Sessões de distância dele.

    O caminho de A até `t` tem três saltos (Setor, Sessao, Task). Com 0
    intermediários o de B tem dois, com 1 tem três (empate) e com 2 tem quatro.
    """
    base = montar_estado(global_=PRESET_MAXIMA, governanca=preset_a)
    nos = {**base.nos, id_b: no(id_b, TipoNo.PROJETO, governanca=preset_b), "goal-b": no("goal-b", TipoNo.GOAL)}
    arestas = dict(base.arestas)
    arestas["decompoe-b-t"] = aresta("decompoe-b-t", "goal-b", "t", TipoAresta.DECOMPOE)
    pai = id_b
    for indice in range(intermediarios):
        id_sessao = f"sess-b{indice}"
        nos[id_sessao] = no(id_sessao, TipoNo.SESSAO, status="ativa")
        arestas[f"cont-{id_sessao}"] = aresta(f"cont-{id_sessao}", pai, id_sessao, TipoAresta.CONTEM)
        pai = id_sessao
    arestas["cont-goal-b"] = aresta("cont-goal-b", pai, "goal-b", TipoAresta.CONTEM)
    return GrafoEstado(nos=nos, arestas=arestas)


@pytest.mark.parametrize("intermediarios", [0, 1, 2])
@pytest.mark.parametrize("id_b", ["a-proj-b", "z-proj-b"])
def test_decompoe_de_goal_de_projeto_permissivo_nao_entrega_a_task_ao_arbitro_edge_case(
    id_b: str, intermediarios: int
) -> None:
    """Caso de borda: B (arbitragem) decompõe a Task de A (governanca_maxima), mais perto, empatado ou mais longe."""
    estado = _com_goal_de_b_decompondo_a_task_de_a(
        id_b=id_b, intermediarios=intermediarios, preset_a=PRESET_MAXIMA, preset_b=PRESET_ARBITRAGEM
    )
    politica = resolver_politica_do_no("t", estado, RastreadorProjetoAncestral())

    assert RastreadorProjetoAncestral().rastrear_todos("t", estado) == tuple(sorted(("proj", id_b)))
    assert all(not politica.permite(gesto, PapelAutor.ARBITRO) for gesto in GESTOS_POR_PAPEL)
    assert not politica.estrutura_ilimitada
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("t")).aprovado
    assert not validar(PapelAutor.ARBITRO, estado, remover_aresta("bloqueia-q-t")).aprovado


def test_projeto_restritivo_decompondo_task_de_projeto_permissivo_tambem_restringe_edge_case() -> None:
    """Caso de borda: o inverso. A Task de A (arbitragem) decomposta por um Goal de B (governanca_maxima) fica restrita."""
    estado = _com_goal_de_b_decompondo_a_task_de_a(
        id_b="proj-b", intermediarios=2, preset_a=PRESET_ARBITRAGEM, preset_b=PRESET_MAXIMA
    )
    politica = resolver_politica_do_no("t", estado, RastreadorProjetoAncestral())

    assert politica.origem(Gesto.EXCLUIR) == "projeto:proj-b"
    assert not validar(PapelAutor.ARBITRO, estado, remover_no("t")).aprovado


def test_com_um_projeto_so_a_politica_dele_vale_sem_mudanca_nominal() -> None:
    """Sem Goal de outro Projeto, a Task de A em arbitragem segue entregando o gesto ao árbitro."""
    estado = montar_estado(global_=PRESET_MAXIMA, governanca=PRESET_ARBITRAGEM)
    politica = resolver_politica_do_no("t", estado, RastreadorProjetoAncestral())

    assert politica.permite(Gesto.EXCLUIR, PapelAutor.ARBITRO)
    assert politica.origem(Gesto.EXCLUIR) == "preset:arbitragem_maxima"
    assert validar(PapelAutor.ARBITRO, estado, remover_no("t")).aprovado
