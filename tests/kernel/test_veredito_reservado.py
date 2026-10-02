"""O veredito de uma Evidence é de quem julga: o RoleGate recusa a escrita aos demais papéis."""

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import ArestaGrafo, GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.kernel.role_gate import RoleGate

PAPEIS_QUE_NAO_JULGAM = [PapelAutor.EXECUTOR, PapelAutor.PLANEJADOR, PapelAutor.SISTEMA]
PAPEIS_QUE_JULGAM = [PapelAutor.REVISOR, PapelAutor.ARBITRO]


def _estado() -> GrafoEstado:
    """Sessão e uma Evidence do revisor que já carrega `veredito=rejeitado`, mais uma Evidence sem veredito."""
    nos = {
        "sess-1": NoGrafo("sess-1", TipoNo.SESSAO, "Sessao"),
        "ev-rev": NoGrafo("ev-rev", TipoNo.EVIDENCE, "Revisao", {"veredito": "rejeitado"}),
        "ev-livre": NoGrafo("ev-livre", TipoNo.EVIDENCE, "Verificacao", {"comando": "pytest"}),
    }
    arestas = {"p-ev-rev": ArestaGrafo("p-ev-rev", "sess-1", "ev-rev", TipoAresta.PRODUZ)}
    return GrafoEstado(nos=nos, arestas=arestas)


def _validar(papel: PapelAutor, operacao: ItemPatch) -> ResultadoValidacao:
    """Passa a operação pelo RoleGate sob o papel dado."""
    proposta = PropostaPatch.criar(DadosPropostaPatch(autor="agente-1", papel=papel, operacoes=[operacao]))
    return RoleGate().validar(proposta, _estado())


def _criar_evidence(propriedades: dict[str, object]) -> ItemPatch:
    """Cria a Evidence `ev-nova` com as propriedades dadas."""
    valor = {"id": "ev-nova", "tipo": TipoNo.EVIDENCE.value, "rotulo": "Nova", "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path="/nos/ev-nova", value=valor)


def _propriedade(op: OperacaoPatch, id_no: str = "ev-rev", valor: object = "aprovado") -> ItemPatch:
    """Escreve a propriedade `veredito` do nó."""
    return ItemPatch(op=op, path=f"/nos/{id_no}/propriedades/veredito", value=None if op == OperacaoPatch.REMOVE else valor)


def _recusado_por_reserva(resultado: ResultadoValidacao) -> bool:
    """A recusa é do RoleGate por violação de papel, e a mensagem cita o veredito."""
    return (
        not resultado.aprovado
        and resultado.portao_falha == "RoleGate"
        and resultado.modo == ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL
        and "veredito" in str(resultado.mensagem_erro)
    )


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
def test_quem_nao_julga_nao_cria_evidence_com_veredito_nominal(papel: PapelAutor) -> None:
    """Criar a Evidence `veredito=aprovado` é a aprovação que o executor daria a si mesmo."""
    assert _recusado_por_reserva(_validar(papel, _criar_evidence({"veredito": "aprovado"})))


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
@pytest.mark.parametrize("op", [OperacaoPatch.ADD, OperacaoPatch.REPLACE, OperacaoPatch.REMOVE])
def test_quem_nao_julga_nao_escreve_a_propriedade_do_veredito_edge_case(papel: PapelAutor, op: OperacaoPatch) -> None:
    """Caso de borda: trocar, acrescentar ou tirar o veredito da Evidence do revisor é recusado."""
    assert _recusado_por_reserva(_validar(papel, _propriedade(op)))


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
def test_quem_nao_julga_nao_acrescenta_veredito_a_evidence_sem_um_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: dar veredito a uma Evidence que não tinha também é escrever o veredito."""
    assert _recusado_por_reserva(_validar(papel, _propriedade(OperacaoPatch.ADD, "ev-livre")))


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
def test_quem_nao_julga_nao_reescreve_o_no_inteiro_com_veredito_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: o nó inteiro com `veredito` nas propriedades, por replace, é recusado."""
    valor = {"id": "ev-livre", "tipo": TipoNo.EVIDENCE.value, "rotulo": "x", "propriedades": {"veredito": "aprovado"}}
    operacao = ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/ev-livre", value=valor)

    assert _recusado_por_reserva(_validar(papel, operacao))


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
def test_quem_nao_julga_nao_remove_a_evidence_que_carrega_veredito_edge_case(papel: PapelAutor) -> None:
    """Caso de borda: apagar a rejeição do revisor devolveria a vez a uma aprovação antiga."""
    assert _recusado_por_reserva(_validar(papel, ItemPatch(op=OperacaoPatch.REMOVE, path="/nos/ev-rev")))


@pytest.mark.parametrize("papel", PAPEIS_QUE_NAO_JULGAM)
def test_evidence_sem_veredito_segue_livre_para_o_executor_nominal(papel: PapelAutor) -> None:
    """A Evidence de verificação, sem veredito, não muda: cria-se e edita-se como sempre."""
    criar = _validar(papel, _criar_evidence({"comando": "pytest", "resultado": "3 passed"}))
    editar = _validar(papel, ItemPatch(op=OperacaoPatch.REPLACE, path="/nos/ev-livre/propriedades/resultado", value="ok"))

    assert "veredito" not in str(criar.mensagem_erro)
    assert "veredito" not in str(editar.mensagem_erro)


@pytest.mark.parametrize("papel", PAPEIS_QUE_JULGAM)
def test_quem_julga_escreve_o_veredito_nominal(papel: PapelAutor) -> None:
    """Revisor e árbitro criam e trocam o veredito."""
    assert "veredito" not in str(_validar(papel, _criar_evidence({"veredito": "aprovado"})).mensagem_erro)
    assert "veredito" not in str(_validar(papel, _propriedade(OperacaoPatch.REPLACE)).mensagem_erro)


def test_humano_escreve_o_veredito_nominal() -> None:
    """O humano é o dono do grafo."""
    assert _validar(PapelAutor.HUMANO, _propriedade(OperacaoPatch.REPLACE)).aprovado is True
