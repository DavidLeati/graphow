"""As constantes de convenção do escopo governado: nomes estáveis que o kernel e as projeções leem."""

from graphow.core import escopo


def test_constantes_de_convencao_tem_os_nomes_do_contrato_nominal() -> None:
    """Gravar um nome diferente do declarado aqui quebraria o que lê a propriedade."""
    assert escopo.CAMPO_TIPO_CONSTRAINT == "tipo"
    assert escopo.CONSTRAINT_CRITERIO_ACEITE == "criterio_aceite"
    assert escopo.CONSTRAINT_FRONTEIRA == "fronteira"
    assert escopo.ACAO_PROPOSTA_FORA_DO_GOAL == "proposta_fora_do_goal"
    assert escopo.ACAO_VEREDITO_DE_ESCOPO == "veredito_de_escopo"
    assert escopo.CAMPO_ATENDE_CRITERIO == "atende_criterio"
    assert escopo.CAMPO_FASE == "fase"
    assert escopo.CAMPO_PLANOS == "planos"
    assert escopo.CAMPO_RESPOSTAS_DE_DESVIO == "respostas_de_desvio"


def test_constantes_de_convencao_sao_distintas_edge_case() -> None:
    """Caso de borda: dois nomes iguais fariam uma propriedade sobrescrever a outra."""
    nomes = [valor for chave, valor in vars(escopo).items() if chave.isupper() and isinstance(valor, str)]
    assert len(nomes) == len(set(nomes))
