"""Os trechos fora do conflito do rebase de onde a fatia tira a base (revisão da T3g5), sobre os textos que o git daria.

A base antiga é `def somar(a, b):` e `return 0`; o Goal muda o `return`, e a
base põe o cabeçalho no topo e `# so inteiros` antes do `return`: o rebase
deixa em conflito as linhas 3 e 4 da base nova.
"""

from graphow.orquestrador.trechos_do_rebase import TextosDoArquivo, resolvida, trechos_fora_do_rebase

BASE: str = "# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n    return 0\n"
REBASE: str = ("# soma de inteiros\ndef somar(a, b):\n<<<<<<< ponta\n    return a + b\n=======\n    # so inteiros\n"
               "    return 0\n>>>>>>> base\n")
REBASE_DIFF3: str = ("# soma de inteiros\ndef somar(a, b):\n<<<<<<< ponta\n    return a + b\n||||||| antiga\n    return 0\n"
                     "=======\n    # so inteiros\n    return 0\n>>>>>>> base\n")
RESOLVIDO: str = "# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n    return a + b\n"
MESCLA_DO_RESOLVIDO: str = ("# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n<<<<<<< base\n    return 0\n=======\n"
                            "    return a + b\n>>>>>>> resultado\n")
COLADO: str = "def somar(a, b):  # do goal\n    # so inteiros\n    return a + b\n"
MESCLA_DO_COLADO: str = f"<<<<<<< base\n{BASE}=======\n{COLADO}>>>>>>> resultado\n"
SEM_CABECALHO: str = "def somar(a, b):\n    # so inteiros\n    return a + b\n"
MESCLA_SEM_CABECALHO: str = ("# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n<<<<<<< base\n    return 0\n=======\n"
                             "    return a + b\n>>>>>>> resultado\n")
ANTIGA_NO_CONFLITO: str = "# soma de inteiros\ndef somar(a, b):\n    return 0\n"


def test_resolucao_do_conflito_dentro_do_trecho_do_rebase_passa_nominal() -> None:
    """T3g6.1 (contraprova): a resolução que mantém o cabeçalho e junta os dois lados no trecho em conflito não tem trecho
    fora; com os marcadores no estilo diff3 no rebase, também não."""
    assert trechos_fora_do_rebase(TextosDoArquivo(BASE, REBASE, RESOLVIDO, MESCLA_DO_RESOLVIDO)) == ()
    assert trechos_fora_do_rebase(TextosDoArquivo(BASE, REBASE_DIFF3, RESOLVIDO, MESCLA_DO_RESOLVIDO)) == ()


def test_conflito_novo_fora_do_trecho_do_rebase_e_recusado_com_as_linhas_da_base_edge_case() -> None:
    """T3g6.1 (sonda): sem o cabeçalho e com a linha colada a ele mudada, o conflito da mescla cobre as linhas 1 a 4 da base
    nova, e o rebase só deixou as 3 e 4 em conflito."""
    trechos = trechos_fora_do_rebase(TextosDoArquivo(BASE, REBASE, COLADO, MESCLA_DO_COLADO))
    assert trechos == ("linhas 1 a 4 da base nova, conflito fora do trecho do rebase",)


def test_linha_da_base_que_a_mescla_limpa_poria_de_volta_fora_do_trecho_e_recusada_edge_case() -> None:
    """Sem o cabeçalho e sem mexer na linha colada, a mescla põe o cabeçalho de volta sem conflito: a linha 1 da base nova
    falta no resultado, fora do trecho do rebase."""
    trechos = trechos_fora_do_rebase(TextosDoArquivo(BASE, REBASE, SEM_CABECALHO, MESCLA_SEM_CABECALHO))
    assert trechos == ("linha 1 da base nova, linha da base fora do resultado",)


def test_linha_da_base_que_falta_dentro_do_trecho_do_rebase_fica_com_a_revisao_edge_case() -> None:
    """A resolução que volta o trecho em conflito ao texto antigo tira dele o `# so inteiros` sem conflito na mescla; a
    linha está dentro do trecho do rebase, onde a fatia resolve como quiser, e quem julga é a revisão."""
    mescla = "# soma de inteiros\ndef somar(a, b):\n    # so inteiros\n    return 0\n"
    assert trechos_fora_do_rebase(TextosDoArquivo(BASE, REBASE, ANTIGA_NO_CONFLITO, mescla)) == ()


def test_resolvida_tira_os_marcadores_e_guarda_o_trecho_de_cada_lado_edge_case() -> None:
    """O lado 0 é o primeiro da mescla, o 1 o segundo; a seção da base antiga (diff3) sai, e a linha `=======` fora de um
    conflito é texto."""
    texto = f"=======\n{REBASE_DIFF3}fim\n"
    assert resolvida(texto, lado=0).linhas == ("=======\n", "# soma de inteiros\n", "def somar(a, b):\n", "    return a + b\n", "fim\n")
    assert resolvida(texto, lado=0).trechos == ((3, 4),)
    assert resolvida(texto, lado=1).trechos == ((3, 5),)
