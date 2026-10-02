"""O SchemaGate recusa o Governanca e a `governanca` de um Projeto malformados."""

from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.governanca import ID_GOVERNANCA_GLOBAL
from graphow.core.models import GrafoEstado, NoGrafo
from graphow.core.types import PapelAutor, TipoNo
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
from graphow.kernel.schema_gate import SchemaGate


def _validar(estado: GrafoEstado, *operacoes: ItemPatch) -> ResultadoValidacao:
    """Passa o lote pelo SchemaGate sob o papel humano."""
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes)
    return SchemaGate().validar(PropostaPatch.criar(dados), estado)


def _criar(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """Criação de nó com as propriedades dadas."""
    valor: dict[str, Any] = {"id": id_no, "tipo": tipo.value, "rotulo": id_no}
    if propriedades is not None:
        valor["propriedades"] = propriedades
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _propriedade(op: OperacaoPatch, id_no: str, chave: str, valor: Any = None) -> ItemPatch:
    """Escrita de uma propriedade de nó."""
    return ItemPatch(op=op, path=f"/nos/{id_no}/propriedades/{chave}", value=valor)


def _estado() -> GrafoEstado:
    """Estado com um Governanca, um Projeto e uma Note já criados."""
    nos = {
        "gov": NoGrafo(id="gov", tipo=TipoNo.GOVERNANCA, rotulo="gov"),
        "proj": NoGrafo(id="proj", tipo=TipoNo.PROJETO, rotulo="proj"),
        "nota": NoGrafo(id="nota", tipo=TipoNo.NOTE, rotulo="nota"),
    }
    return GrafoEstado(nos=nos)


def _recusado(resultado: ResultadoValidacao) -> bool:
    """Confere a recusa pela estrutura incompleta e pela mensagem de governança."""
    return (
        not resultado.aprovado
        and resultado.modo == ModoFalhaMAST.ESTRUTURA_INCOMPLETA
        and "governança" in str(resultado.mensagem_erro)
    )


@pytest.mark.parametrize("propriedades", [
    None,
    {},
    {"preset": "arbitragem_maxima"},
    {"preset": "personalizada", "personalizada": {"excluir": "arbitro", "max_correcoes": 5}},
])
def test_governanca_valido_e_aceito_nominal(propriedades: dict[str, Any] | None) -> None:
    """Criar o Governanca com preset e personalizada válidos passa."""
    assert _validar(GrafoEstado(), _criar(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA, propriedades)).aprovado


@pytest.mark.parametrize("propriedades", [
    {"preset": "herdar"},
    {"preset": "fantasma"},
    {"nivel_autonomia": "ilimitado"},
    {"personalizada": {"gesto_x": "humano"}},
    {"personalizada": {"excluir": "ninguem"}},
    {"personalizada": {"max_correcoes": 9}},
    {"personalizada": "texto"},
])
def test_governanca_malformado_e_recusado_edge_case(propriedades: dict[str, Any]) -> None:
    """Caso de borda: o Governanca só aceita preset e personalizada, ambos no domínio."""
    assert _recusado(_validar(GrafoEstado(), _criar(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA, propriedades)))


@pytest.mark.parametrize("governanca", [
    {"preset": "herdar"},
    {"preset": "arbitragem_maxima"},
    {"preset": "personalizada", "personalizada": {"constraint": "arbitro"}},
])
def test_projeto_com_governanca_valida_e_aceito_nominal(governanca: dict[str, Any]) -> None:
    """Criar o Projeto com a propriedade `governanca` válida passa."""
    assert _validar(GrafoEstado(), _criar("p", TipoNo.PROJETO, {"governanca": governanca})).aprovado


@pytest.mark.parametrize("governanca", [
    {"preset": "fantasma"},
    {"preset": "personalizada", "personalizada": {"excluir": "estrito"}},
    {"extra": 1},
    "herdar",
    None,
])
def test_projeto_com_governanca_malformada_e_recusado_edge_case(governanca: object) -> None:
    """Caso de borda: a `governanca` do Projeto malformada é recusada na criação."""
    assert _recusado(_validar(GrafoEstado(), _criar("p", TipoNo.PROJETO, {"governanca": governanca})))


def test_escrita_de_propriedade_do_governanca_existente_nominal() -> None:
    """Trocar o preset ou a personalizada do Governanca existente passa quando válido."""
    estado = _estado()
    assert _validar(estado, _propriedade(OperacaoPatch.REPLACE, "gov", "preset", "arbitragem_maxima")).aprovado
    assert _validar(estado, _propriedade(OperacaoPatch.ADD, "gov", "personalizada", {"excluir": "arbitro"})).aprovado
    assert _validar(estado, _propriedade(OperacaoPatch.REMOVE, "gov", "preset")).aprovado


@pytest.mark.parametrize(("chave", "valor"), [
    ("preset", "herdar"),
    ("preset", 1),
    ("personalizada", {"excluir": "talvez"}),
    ("personalizada", {"fantasma": "humano"}),
    ("personalizada", [1]),
    ("nivel_autonomia", "ilimitado"),
])
def test_escrita_invalida_no_governanca_existente_e_recusada_edge_case(chave: str, valor: object) -> None:
    """Caso de borda: a propriedade fora do domínio, ou desconhecida, é recusada."""
    assert _recusado(_validar(_estado(), _propriedade(OperacaoPatch.REPLACE, "gov", chave, valor)))


def test_escrita_da_governanca_do_projeto_existente_edge_case() -> None:
    """Caso de borda: a `governanca` de um Projeto já criado é validada na escrita."""
    estado = _estado()
    assert _validar(estado, _propriedade(OperacaoPatch.REPLACE, "proj", "governanca", {"preset": "herdar"})).aprovado
    assert _recusado(_validar(estado, _propriedade(OperacaoPatch.REPLACE, "proj", "governanca", {"preset": "x"})))
    assert _validar(estado, _propriedade(OperacaoPatch.REMOVE, "proj", "governanca")).aprovado


def test_propriedades_de_outros_nos_nao_sao_afetadas_edge_case() -> None:
    """Caso de borda: uma propriedade qualquer, em Note ou no Projeto, segue livre."""
    estado = _estado()
    assert _validar(estado, _propriedade(OperacaoPatch.REPLACE, "nota", "preset", "qualquer")).aprovado
    assert _validar(estado, _propriedade(OperacaoPatch.REPLACE, "proj", "nivel_autonomia", "ilimitado")).aprovado


def test_escrita_em_no_criado_no_mesmo_lote_edge_case() -> None:
    """Caso de borda: o tipo do nó criado antes no lote também orienta a validação."""
    criar = _criar(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA)
    assert _validar(GrafoEstado(), criar, _propriedade(OperacaoPatch.ADD, ID_GOVERNANCA_GLOBAL, "preset", "personalizada")).aprovado
    assert _recusado(_validar(GrafoEstado(), criar, _propriedade(OperacaoPatch.ADD, ID_GOVERNANCA_GLOBAL, "preset", "herdar")))


@pytest.mark.parametrize("id_no", ["gov", "gov2", "governanca", "governanca-global-2"])
def test_governanca_com_id_diferente_do_singleton_e_recusado_edge_case(id_no: str) -> None:
    """Caso de borda: só o singleton é lido pela resolução; um segundo nó seria configuração fantasma."""
    resultado = _validar(GrafoEstado(), _criar(id_no, TipoNo.GOVERNANCA))
    assert not resultado.aprovado
    assert resultado.modo == ModoFalhaMAST.ESTRUTURA_INCOMPLETA
    assert ID_GOVERNANCA_GLOBAL in str(resultado.mensagem_erro)
    assert "governança" in str(resultado.mensagem_erro)


def test_governanca_singleton_com_o_id_certo_e_aceito_nominal() -> None:
    """O nó `governanca-global` segue podendo ser criado, vazio ou com política válida."""
    assert _validar(GrafoEstado(), _criar(ID_GOVERNANCA_GLOBAL, TipoNo.GOVERNANCA)).aprovado
