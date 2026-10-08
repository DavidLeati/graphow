"""`criar_tarefa` e a ligação de escopo: os campos viram arestas e propriedade, e a regra é do kernel."""

from typing import Any

import pytest

from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.projection.classificacao_escopo import ClasseDeEscopo, classificar_tarefa_vigente
from tests.kernel.cenario_escopo import montar_kernel_com_goal, submeter
from tests.kernel.cenario_governanca import criar_aresta
from tests.mcp.cenario_governanca import servidor

MAXIMA: str = "governanca_maxima"


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object] | None = None) -> ItemPatch:
    """A criação do nó com as propriedades dadas."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _kernel(*, com_plano: bool) -> WriteKernel:
    """O Goal com a `t1`, o critério, uma Evidence rejeitada e uma Decision revogada, com ou sem plano aprovado."""
    kernel = montar_kernel_com_goal(MAXIMA)
    apoio = (
        _no("crit", TipoNo.CONSTRAINT, {"tipo": "criterio_aceite"}),
        criar_aresta("prod-crit", "sess", "crit", TipoAresta.PRODUZ),
        criar_aresta("escopa-crit", "crit", "goal", TipoAresta.ESCOPA),
        _no("ev-rej", TipoNo.EVIDENCE, {"veredito": "rejeitado"}),
        criar_aresta("prod-ev-rej", "sess", "ev-rej", TipoAresta.PRODUZ),
        _no("dec-velha", TipoNo.DECISION, {"status": "revogada"}),
        criar_aresta("prod-dec-velha", "sess", "dec-velha", TipoAresta.PRODUZ),
    )
    assert submeter(kernel, PapelAutor.HUMANO, *apoio).sucesso
    if com_plano:
        resposta = servidor(kernel, "humano").executar_ferramenta("aprovar_plano", {"id_goal": "goal"})
        assert resposta["sucesso"] is True, resposta
    return kernel


def _criar(kernel: WriteKernel, **argumentos: Any) -> dict[str, Any]:
    """O planejador cria a Task `nova` na sessão `sess`, sob o Goal, com os argumentos a mais."""
    base = {"titulo": "nova", "id_task": "nova", "id_sessao": "sess", "id_tarefa_pai": "goal"}
    return servidor(kernel, "planejador").executar_ferramenta("criar_tarefa", {**base, **argumentos})


def _destinos(kernel: WriteKernel, tipo: TipoAresta) -> set[str]:
    """Os destinos das arestas do tipo que saem da `nova`."""
    return {a.destino_id for a in kernel.obter_estado().arestas.values() if a.origem_id == "nova" and a.tipo == tipo}


def test_campos_de_ligacao_viram_arestas_e_propriedade_nominal() -> None:
    """Cada campo novo gera a aresta do tipo certo; `atende_criterio` fica na Task, e o Goal sem plano aceita."""
    kernel = _kernel(com_plano=False)
    recibo = _criar(
        kernel, motivada_por=["dec-1", "ev-rej"], atende_criterio=["crit"],
        acompanha="ev-rej", integra="t1", desfaz="dec-velha",
    )
    assert recibo["sucesso"] is True, recibo
    assert _destinos(kernel, TipoAresta.MOTIVADA_POR) == {"dec-1", "ev-rej"}
    assert _destinos(kernel, TipoAresta.ACOMPANHA) == {"ev-rej"}
    assert _destinos(kernel, TipoAresta.INTEGRA) == {"t1"}
    assert _destinos(kernel, TipoAresta.DESFAZ) == {"dec-velha"}
    assert kernel.obter_estado().nos["nova"].propriedades["atende_criterio"] == ["crit"]


def test_sem_os_campos_a_task_antiga_nao_muda_de_forma_edge_case() -> None:
    """Caso de borda: sem os campos novos nenhuma aresta de escopo nem `atende_criterio` aparece."""
    kernel = _kernel(com_plano=False)
    assert _criar(kernel)["sucesso"] is True
    assert "atende_criterio" not in kernel.obter_estado().nos["nova"].propriedades
    assert all(
        a.tipo not in {TipoAresta.MOTIVADA_POR, TipoAresta.ACOMPANHA, TipoAresta.INTEGRA, TipoAresta.DESFAZ}
        for a in kernel.obter_estado().arestas.values()
    )


def test_com_plano_o_pai_goal_sozinho_chega_recusado_com_a_mensagem_nominal() -> None:
    """A recusa do kernel chega ao agente com o modo de falha, as ligações aceitas e o exemplo."""
    kernel = _kernel(com_plano=True)
    recibo = _criar(kernel)
    assert recibo["sucesso"] is False
    assert recibo["modo_de_falha"] == "ligacao_de_escopo_ausente"
    assert "Ligações aceitas" in recibo["mensagem"] and "criar_tarefa(" in recibo["mensagem"]
    assert "nova" not in kernel.obter_estado().nos


def test_com_plano_motivada_por_e_atende_criterio_passam_e_classificam_b3_nominal() -> None:
    """A ligação emergente completa deixa a Task nascer, e a classificação a lê como B3."""
    kernel = _kernel(com_plano=True)
    recibo = _criar(kernel, motivada_por=["dec-1"], atende_criterio=["crit"])
    assert recibo["sucesso"] is True, recibo
    assert classificar_tarefa_vigente(kernel.obter_view(), "nova") == ClasseDeEscopo.B3


def test_com_plano_subdivisao_e_reversao_pelas_ferramentas_passam_nominal() -> None:
    """A subdivisão por `id_tarefa_pai` de Task do plano e a reversão por `desfaz` valem."""
    kernel = _kernel(com_plano=True)
    assert _criar(kernel, id_tarefa_pai="t1")["sucesso"] is True
    assert _criar(kernel, id_task="reverte-1", titulo="reverte-1", desfaz="dec-velha")["sucesso"] is True
    assert classificar_tarefa_vigente(kernel.obter_view(), "reverte-1") == ClasseDeEscopo.REVERSAO


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("motivada_por", 7), ("motivada_por", ["dec-1", 3]), ("atende_criterio", {"id": "crit"}), ("acompanha", ["ev-rej"]), ("integra", 5), ("desfaz", ["dec-velha"])],
)
def test_argumento_de_tipo_errado_e_recusado_na_camada_mcp_edge_case(campo: str, valor: object) -> None:
    """Caso de borda: o tipo do argumento é conferido antes do kernel, e nada é gravado."""
    kernel = _kernel(com_plano=False)
    recibo = _criar(kernel, **{campo: valor})
    assert recibo["sucesso"] is False
    assert campo in recibo["erro"]
    assert "nova" not in kernel.obter_estado().nos
