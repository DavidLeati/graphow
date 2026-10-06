"""O lote que a skill graphow-gerente manda gravar passa pelos quatro portões.

A skill ensina, em prosa, a forma da definição de uma demanda: o Goal produzido
pela Sessao, a Constraint que o escopa, a Decision que o orienta e a Evidence que
a justifica. Se um portão passar a recusar essa forma, a skill ensinaria a
gravar o que o kernel não aceita; este teste avisa antes.
"""

from graphow.core.types import PapelAutor
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.in_memory_store import InMemoryEventStore
from graphow.web.dto import RequisicaoNovoNo
from graphow.web.rest_canvas_controller import CanvasWebController


def _kernel_com_sessao() -> WriteKernel:
    """Um Projeto, um Setor e a Sessao em que o gerente roda."""
    kernel = WriteKernel(InMemoryEventStore())
    canvas = CanvasWebController(kernel)
    requisicoes = (
        RequisicaoNovoNo(tipo="Projeto", rotulo="Projeto", id_no="proj"),
        RequisicaoNovoNo(tipo="Setor", rotulo="Setor", id_no="setor", contido_em="proj"),
        RequisicaoNovoNo(tipo="Sessao", rotulo="Sessao", id_no="sess", contido_em="setor"),
    )
    for requisicao in requisicoes:
        assert canvas.criar_no(requisicao).sucesso is True
    return kernel


def _no(id_no: str, tipo: str, propriedades: dict[str, object]) -> ItemPatch:
    """Cria um nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: str) -> ItemPatch:
    """Cria uma aresta com id derivado das pontas."""
    id_aresta = f"{tipo}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _definicao_da_demanda() -> tuple[ItemPatch, ...]:
    """Goal, Constraint, Decision e Evidence como a skill descreve, num lote só."""
    goal = {"descricao": "Validar o e-mail do cliente", "criterios_aceite": ["e-mail invalido nao grava"], "em_aberto": [], "fora_do_escopo": []}
    return (
        _no("goal", "Goal", goal),
        _aresta("sess", "goal", "produz"),
        _no("restricao", "Constraint", {}),
        _aresta("sess", "restricao", "produz"),
        _aresta("restricao", "goal", "escopa"),
        _no("decisao", "Decision", {"motivo": "remover grava um valor valido e errado"}),
        _aresta("sess", "decisao", "produz"),
        _aresta("decisao", "goal", "orienta"),
        _no("evidencia", "Evidence", {"fonte": "chamado 75666", "local": "interacao de 04/09", "trecho": "campo E-mail NF-e preenchido com caracteres especiais"}),
        _aresta("sess", "evidencia", "produz"),
        _aresta("evidencia", "decisao", "justifica"),
    )


def test_definicao_da_demanda_passa_como_humano_nominal() -> None:
    """O gerente grava pela conexão humana, e a definição inteira entra num lote."""
    kernel = _kernel_com_sessao()
    dados = DadosPropostaPatch(autor="humano", papel=PapelAutor.HUMANO, operacoes=_definicao_da_demanda())

    resultado = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert resultado.sucesso is True, resultado
    estado = kernel.obter_estado()
    assert estado.nos["goal"].propriedades["criterios_aceite"] == ["e-mail invalido nao grava"]
    assert {"escopa-restricao-goal", "orienta-decisao-goal", "justifica-evidencia-decisao"} <= set(estado.arestas)


def test_evidencia_com_local_sem_trecho_derruba_a_definicao_edge_case() -> None:
    """Caso de borda: a Evidence que aponta o local na fonte sem o trecho literal não ganha autoridade de fato."""
    kernel = _kernel_com_sessao()
    sem_trecho = tuple(
        _no("evidencia", "Evidence", {"fonte": "chamado 75666", "local": "interacao de 04/09"}) if item.path == "/nos/evidencia" else item
        for item in _definicao_da_demanda()
    )
    dados = DadosPropostaPatch(autor="humano", papel=PapelAutor.HUMANO, operacoes=sem_trecho)

    resultado = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert resultado.sucesso is False
    assert "goal" not in kernel.obter_estado().nos


def test_definicao_da_demanda_e_recusada_ao_planejador_edge_case() -> None:
    """Caso de borda: o mesmo lote vindo de um agente cai, porque Goal e Constraint seguem do humano."""
    kernel = _kernel_com_sessao()
    dados = DadosPropostaPatch(autor="condutor", papel=PapelAutor.PLANEJADOR, operacoes=_definicao_da_demanda())

    resultado = kernel.submeter_patch(PropostaPatch.criar(dados))

    assert resultado.sucesso is False
    assert "goal" not in kernel.obter_estado().nos
