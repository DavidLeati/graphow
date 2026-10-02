"""Cenário compartilhado dos testes de governança no RoleGate: um estado pequeno e as operações dos gestos.

O RoleGate é uma função do estado e da proposta: os testes montam o estado
direto, sem passar pelo log, e perguntam o veredito.
"""

from collections.abc import Callable
from typing import Any

from graphow.core.governanca import ID_GOVERNANCA_GLOBAL, Gesto
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.kernel.role_gate import RoleGate

PRESET_MAXIMA: dict[str, Any] = {"preset": "governanca_maxima"}
PRESET_ARBITRAGEM: dict[str, Any] = {"preset": "arbitragem_maxima"}
AGENTES_SEM_ARBITRO = [PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR]


def no(id_no: str, tipo: TipoNo, **propriedades: Any) -> NoGrafo:
    """Nó com rótulo igual ao id."""
    return NoGrafo(id=id_no, tipo=tipo, rotulo=id_no, propriedades=dict(propriedades))


def aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ArestaGrafo:
    """Aresta com id explícito."""
    return ArestaGrafo(id=id_aresta, origem_id=origem, destino_id=destino, tipo=tipo)


def montar_estado(
    *,
    global_: dict[str, Any] | None = None,
    governanca: dict[str, Any] | None = None,
    nivel_autonomia: str | None = None,
) -> GrafoEstado:
    """Projeto -> Setor -> Sessão, que produz Goal, Task, Questions, Constraint e Aprendizados.

    `global_` vira as propriedades do nó `governanca-global`; `governanca` e
    `nivel_autonomia` vão para o Projeto. `q` foi aberta por um executor e `q-arb`
    pelo árbitro `arbitro-1`; ambas bloqueiam uma Task.
    """
    propriedades_do_projeto: dict[str, Any] = {}
    if governanca is not None:
        propriedades_do_projeto["governanca"] = governanca
    if nivel_autonomia is not None:
        propriedades_do_projeto["nivel_autonomia"] = nivel_autonomia
    nos = [
        no("proj", TipoNo.PROJETO, **propriedades_do_projeto),
        no("setor", TipoNo.SETOR),
        no("sess", TipoNo.SESSAO, status="ativa"),
        no("goal", TipoNo.GOAL, status="em_andamento"),
        no("t", TipoNo.TASK, status="pendente"),
        no("t2", TipoNo.TASK, status="pendente"),
        no("q", TipoNo.QUESTION, status="aberta", aberta_por="executor-1#aaaa"),
        no("q-arb", TipoNo.QUESTION, status="aberta", aberta_por="arbitro-1#bbbb"),
        no("c", TipoNo.CONSTRAINT),
        no("a", TipoNo.APRENDIZADO),
        no("a2", TipoNo.APRENDIZADO),
    ]
    if global_ is not None:
        nos.append(no(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA, **global_))
    arestas = [
        aresta("cont-proj-setor", "proj", "setor", TipoAresta.CONTEM),
        aresta("cont-setor-sess", "setor", "sess", TipoAresta.CONTEM),
        *(aresta(f"prod-{id_no}", "sess", id_no, TipoAresta.PRODUZ) for id_no in ("goal", "t", "t2", "q", "q-arb", "c", "a", "a2")),
        aresta("bloqueia-q-t", "q", "t", TipoAresta.BLOQUEIA),
        aresta("bloqueia-q-arb-t2", "q-arb", "t2", TipoAresta.BLOQUEIA),
        aresta("escopa-c-goal", "c", "goal", TipoAresta.ESCOPA),
        aresta("vale-a-setor", "a", "setor", TipoAresta.VALE_PARA),
    ]
    return GrafoEstado(nos={n.id: n for n in nos}, arestas={a.id: a for a in arestas})


def criar_no(id_no: str, tipo: TipoNo, **propriedades: Any) -> ItemPatch:
    """Criação de nó."""
    valor: dict[str, Any] = {"id": id_no, "tipo": tipo.value, "rotulo": id_no}
    if propriedades:
        valor["propriedades"] = propriedades
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def criar_aresta(id_aresta: str, origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta."""
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def escrever(op: OperacaoPatch, id_no: str, chave: str, valor: Any = None) -> ItemPatch:
    """Escrita de uma propriedade."""
    return ItemPatch(op=op, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)


def remover_no(id_no: str) -> ItemPatch:
    """Remoção de nó inteiro."""
    return ItemPatch(op=OperacaoPatch.REMOVE, path=f"/nos/{id_no}")


def remover_aresta(id_aresta: str) -> ItemPatch:
    """Remoção de aresta."""
    return ItemPatch(op=OperacaoPatch.REMOVE, path=f"/arestas/{id_aresta}")


def validar(papel: PapelAutor, estado: GrafoEstado, *operacoes: ItemPatch, autor: str | None = None) -> ResultadoValidacao:
    """Passa o lote pelo RoleGate sob o papel e o autor dados."""
    dados = DadosPropostaPatch(autor=autor or f"{papel.value}-1", papel=papel, operacoes=operacoes)
    return RoleGate().validar(PropostaPatch.criar(dados), estado)


# Operações que exercem cada gesto: id do caso -> (gesto, construtor das operações).
Operacoes = Callable[[], tuple[ItemPatch, ...]]
CASOS_DE_GESTO: dict[str, tuple[Gesto, Operacoes]] = {
    "questao_respondida": (
        Gesto.RESPONDER_QUESTAO, lambda: (escrever(OperacaoPatch.REPLACE, "q", "status", "respondida"),)
    ),
    "questao_descartada": (
        Gesto.RESPONDER_QUESTAO, lambda: (escrever(OperacaoPatch.REPLACE, "q", "status", "descartada"),)
    ),
    "questao_sem_status": (Gesto.RESPONDER_QUESTAO, lambda: (escrever(OperacaoPatch.REMOVE, "q", "status"),)),
    "bloqueio_retirado": (Gesto.RESPONDER_QUESTAO, lambda: (remover_aresta("bloqueia-q-t"),)),
    "promover_a_projeto": (
        Gesto.PROMOVER_APRENDIZADO, lambda: (criar_aresta("vale-a2-proj", "a2", "proj", TipoAresta.VALE_PARA),)
    ),
    "promover_a_setor": (
        Gesto.PROMOVER_APRENDIZADO, lambda: (criar_aresta("vale-a2-setor", "a2", "setor", TipoAresta.VALE_PARA),)
    ),
    "promocao_retirada": (Gesto.PROMOVER_APRENDIZADO, lambda: (remover_aresta("vale-a-setor"),)),
    "criar_constraint": (
        Gesto.CONSTRAINT,
        lambda: (
            criar_no("c2", TipoNo.CONSTRAINT),
            criar_aresta("prod-c2", "sess", "c2", TipoAresta.PRODUZ),
        ),
    ),
    "editar_constraint": (
        Gesto.CONSTRAINT, lambda: (ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/c/rotulo", value="nova"),)
    ),
    "remover_constraint": (Gesto.CONSTRAINT, lambda: (remover_no("c"),)),
    "escopar": (Gesto.CONSTRAINT, lambda: (criar_aresta("escopa-c-t", "c", "t", TipoAresta.ESCOPA),)),
    "desescopar": (Gesto.CONSTRAINT, lambda: (remover_aresta("escopa-c-goal"),)),
    "excluir_task": (Gesto.EXCLUIR, lambda: (remover_no("t"),)),
    "excluir_questao": (Gesto.EXCLUIR, lambda: (remover_no("q"),)),
    "excluir_aprendizado": (Gesto.EXCLUIR, lambda: (remover_no("a"),)),
    "fechar_goal": (Gesto.FECHAR_GOAL, lambda: (escrever(OperacaoPatch.REPLACE, "goal", "status", "concluido"),)),
    "encerrar_sessao": (
        Gesto.ENCERRAR_SESSAO, lambda: (escrever(OperacaoPatch.REPLACE, "sess", "status", "concluida"),)
    ),
}
