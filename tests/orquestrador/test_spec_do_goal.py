"""A spec do Goal do gerente: o código de cada critério e decisão vem da propriedade `codigo` do nó, não da ordem do log."""

from typing import Any

from graphow.core.types import PapelAutor
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.orquestrador.spec_do_goal import montar_spec_do_goal


def _no(id_no: str, tipo: str, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """A criação de um nó."""
    return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": propriedades or {}})


def _aresta(origem: str, destino: str, tipo: str) -> ItemPatch:
    """A criação de uma aresta."""
    id_aresta = f"{tipo}-{origem}-{destino}"
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}", {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo})


def _goal_com_criterios(codigos: list[str]) -> WriteKernel:
    """O Goal do gerente com um Criterio por código dado, todos num lote só (a ordem do log, entre eles, é a dos ids)."""
    kernel = montar_kernel_em_memoria()
    operacoes = [_no("proj", "Projeto"), _no("setor", "Setor"), _aresta("proj", "setor", "contem"), _no("sess", "Sessao"),
                 _aresta("setor", "sess", "contem"), _no("g", "Goal", {"descricao": "x"}), _aresta("sess", "g", "produz")]
    for numero, codigo in enumerate(codigos, start=1):
        id_no = f"crit-x-{numero}"
        operacoes += [_no(id_no, "Criterio", {"codigo": codigo, "texto": f"texto de {codigo or numero}", "verificacao": "teste"}),
                      _aresta("sess", id_no, "produz"), _aresta(id_no, "g", "escopa")]
    recibo = kernel.submeter_patch(PropostaPatch.criar(DadosPropostaPatch(
        autor="david", papel=PapelAutor.HUMANO, operacoes=tuple(operacoes), justificativa="Goal do gerente")))
    assert recibo.sucesso, recibo.mensagem
    return kernel


def test_codigo_do_criterio_vem_da_propriedade_e_nao_da_ordem_do_log_edge_case() -> None:
    """Caso de borda (acompanhamento 8): com onze critérios num lote, crit-x-10 nasce antes de crit-x-2, e C2 segue sendo crit-x-2."""
    kernel = _goal_com_criterios([f"C{n}" for n in range(1, 12)])

    spec = montar_spec_do_goal(kernel.obter_view(), "g")

    assert spec.nos_fixados["C2"] == "crit-x-2" and spec.nos_fixados["C10"] == "crit-x-10"
    assert spec.fixados.criterios == tuple(f"C{n}" for n in range(1, 12))
    assert [(c.id, c.texto) for c in spec.criterios_do_humano][:2] == [("C1", "texto de C1"), ("C2", "texto de C2")]
    assert "- C2 (crit-x-2, teste): texto de C2" in spec.texto


def test_codigo_gravado_fora_de_ordem_vale_como_o_humano_o_leu_edge_case() -> None:
    """Caso de borda: o critério gravado como C3 antes do C1 continua C3, e a lista sai em ordem numérica."""
    kernel = _goal_com_criterios(["C3", "C1", "C2"])

    spec = montar_spec_do_goal(kernel.obter_view(), "g")

    assert spec.nos_fixados["C3"] == "crit-x-1" and spec.fixados.criterios == ("C1", "C2", "C3")


def test_sem_codigo_valido_em_todos_os_codigos_saem_da_ordem_edge_case() -> None:
    """Caso de borda: o nó sem código, ou dois com o mesmo, fazem a numeração voltar à ordem do log, para todos."""
    sem_codigo = montar_spec_do_goal(_goal_com_criterios(["C1", ""]).obter_view(), "g")
    repetido = montar_spec_do_goal(_goal_com_criterios(["C1", "C1"]).obter_view(), "g")

    assert sem_codigo.nos_fixados == {"C1": "crit-x-1", "C2": "crit-x-2"}
    assert repetido.fixados.criterios == ("C1", "C2")
