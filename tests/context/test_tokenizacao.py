"""Testes do estimador calibrado: acento e pictograma custam mais que ASCII."""

from graphow.context.token_counter import ContadorTokens
from graphow.context.tokenizacao import (
    ClasseDeCaractere,
    EstimadorPorClasseDeCaractere,
    EstimadorPorNormalizacao,
    classificar,
)

HEURISTICA_ANTIGA_CARACTERES_POR_TOKEN: float = 4.0


def test_classifica_cada_faixa_de_caractere_nominal() -> None:
    """A calibração começa por saber em que faixa cada caractere cai."""
    assert classificar("a") == ClasseDeCaractere.ASCII
    assert classificar("ç") == ClasseDeCaractere.LATINO_ACENTUADO
    assert classificar("漢") == ClasseDeCaractere.OUTRO_PLANO_BASICO
    assert classificar("🔒") == ClasseDeCaractere.ASTRAL


def test_texto_acentuado_custa_mais_que_o_mesmo_texto_em_ascii_nominal() -> None:
    """Era o erro de A-16: o orçamento entregue passava do declarado."""
    estimador = EstimadorPorClasseDeCaractere()

    com_acento = estimador.estimar_texto("Decisão de execução válida")
    sem_acento = estimador.estimar_texto("Decisao de execucao valida")

    assert com_acento > sem_acento


def test_pictograma_nunca_e_contado_como_um_quarto_de_token_edge_case() -> None:
    """Caso de borda: os selos de bloqueio dos rótulos eram quase de graça."""
    estimador = EstimadorPorClasseDeCaractere()

    assert estimador.estimar_texto("🔒🔒🔒🔒") >= 8


def test_estimativa_nunca_fica_abaixo_da_heuristica_antiga_edge_case() -> None:
    """Caso de borda: subestimar quebra a promessa que o agente não pode conferir."""
    estimador = EstimadorPorClasseDeCaractere()
    amostras = (
        "Criar LRU Cache Determinístico de Vértices",
        "Proibido float binário (Decimal 18d)",
        "plain ascii label without accents",
        "🔒 Tarefa bloqueada por dúvida aberta",
    )

    for amostra in amostras:
        piso = len(amostra) / HEURISTICA_ANTIGA_CARACTERES_POR_TOKEN
        assert estimador.estimar_texto(amostra) >= piso, amostra


def test_texto_vazio_nao_custa_nada_edge_case() -> None:
    """Caso de borda: a string vazia continua valendo zero."""
    assert EstimadorPorClasseDeCaractere().estimar_texto("") == 0


def test_normalizacao_nfd_separa_o_acento_e_encarece_edge_case() -> None:
    """Caso de borda: a escolha de normalização muda a conta, e fica explícita."""
    composto = "ação"

    assert EstimadorPorNormalizacao().estimar_texto(composto) >= EstimadorPorClasseDeCaractere().estimar_texto(composto)


def test_contador_expoe_a_calibracao_em_uso_nominal() -> None:
    """Uma métrica de tokens precisa dizer com que régua foi medida."""
    assert ContadorTokens.calibracao_em_uso() == "classe-de-caractere-v1"
