"""Testes do vocabulário da ontologia que a interface consulta em vez de copiar."""

from graphow.core.types import StatusQuestion, StatusTask, TipoAresta, TipoNo
from graphow.kernel.schema_gate import SchemaGate
from graphow.web.ontologia_publica import montar_ontologia_publica


def test_toda_aresta_da_ontologia_e_publicada_nominal() -> None:
    """Um tipo de aresta ausente aqui some do seletor da tela sem aviso."""
    publicada = montar_ontologia_publica()

    assert set(publicada["arestas"]) == {tipo.value for tipo in TipoAresta}
    assert publicada["tipos_no"] == [tipo.value for tipo in TipoNo]


def test_pares_publicados_sao_os_que_o_portao_aplica_nominal() -> None:
    """A tela sugere exatamente o que o SchemaGate aceita — nem mais, nem menos."""
    publicada = montar_ontologia_publica()["arestas"]

    for tipo, pares in SchemaGate.PARES_ARESTAS_PERMITIDOS.items():
        esperados = {(origem.value, destino.value) for origem, destino in pares}
        assert {tuple(par) for par in publicada[tipo.value]} == esperados, tipo


def test_status_publicados_seguem_os_enums_do_nucleo_edge_case() -> None:
    """Caso de borda: um status novo no núcleo precisa aparecer no seletor do inspetor."""
    status = montar_ontologia_publica()["status"]

    assert status["Task"] == [valor.value for valor in StatusTask]
    assert status["Question"] == [valor.value for valor in StatusQuestion]
