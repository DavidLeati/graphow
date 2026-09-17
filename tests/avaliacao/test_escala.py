"""Testes da medição de escala: o fechamento no rollup precisa ter custo medido."""

from graphow.avaliacao.escala import medir_escala
from graphow.avaliacao.tarefas_gravadas import montar_cenario_gravado


def test_relatorio_de_escala_mede_o_rollup_e_o_panorama_da_raiz_nominal() -> None:
    """As duas medidas que decidem se o fechamento pode viajar no rollup."""
    relatorio = medir_escala(montar_cenario_gravado())

    assert relatorio.milissegundos_do_rollup >= 0.0
    assert relatorio.tokens_do_panorama_da_raiz > 0
    texto = "\n".join(relatorio.formatar())
    assert "Rollup por commit" in texto
    assert "Panorama da raiz" in texto
