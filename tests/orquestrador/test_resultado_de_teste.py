"""A leitura da saída dos runners: verde só quando passou sem pular, vermelho só pela asserção do teste declarado.

As saídas são as que os runners imprimem de fato (pytest 8, unittest do
Python 3.12, node:test 22 em TAP e spec), e as de jest, vitest e mocha no
formato que eles documentam.
"""

import pytest

from graphow.orquestrador.resultado_de_teste import por_que_nao_passou, por_que_o_vermelho_nao_vale

PYTEST: str = "python -m pytest -q aceite/aceite_c1.py::test_c1_media"
UNITTEST: str = "python -m unittest aceite.test_c1.TestC1.test_c1_media"
PYTEST_VERDE: str = ".                                                                        [100%]\n1 passed in 0.01s\n"
PYTEST_PULADO: str = "s                                                                        [100%]\n1 skipped in 0.01s\n"
PYTEST_XFAIL: str = "x                                                                        [100%]\n1 xfailed in 0.11s\n"
PYTEST_ASSERCAO: str = (
    "    def test_c1_media():\n>       assert media([1, 2]) == 1.5\nE       assert 1 == 1.5\n\n"
    "aceite\\aceite_c1.py:7: AssertionError\n=========================== short test summary info ===========================\n"
    "FAILED aceite/aceite_c1.py::test_c1_media - assert 1 == 1.5\n1 failed in 0.11s\n"
)
PYTEST_IMPORT_NO_TESTE: str = (
    "E       ModuleNotFoundError: No module named 'estatistica'\n\naceite\\aceite_c1.py:10: ModuleNotFoundError\n"
    "=========================== short test summary info ===========================\n"
    "FAILED aceite/aceite_c1.py::test_c1_media - ModuleNotFoundError: No modul...\n1 failed in 0.11s\n"
)
# A saída real do autor de aceite na fumaça da rodada 3: a asserção num helper e a linha FAILED cortada pelo pytest.
PYTEST_RESUMO_CORTADO: str = (
    "    def _func(nome):\n        import estatistica\n        f = getattr(estatistica, nome, None)\n"
    ">       assert f is not None\nE       AssertionError: estatistica.mediana nao existe\n\n"
    "aceite\\aceite_funcoes.py:14: AssertionError\n=========================== short test summary info ===========================\n"
    "FAILED aceite/aceite_funcoes.py::test_c1_mediana_impar_par_e_nao_altera - Ass...\n1 failed in 0.19s\n"
)
PYTEST_COLETA: str = (
    "aceite\\aceite_c1.py:1: in <module>\n    from estatistica import media\nE   ModuleNotFoundError: No module named 'estatistica'\n"
    "=========================== short test summary info ===========================\nERROR aceite/aceite_c1.py\n"
    "!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n1 error in 0.23s\n"
)
PYTEST_NAO_ACHOU: str = "ERROR: not found: aceite/aceite_c1.py::test_c1_mediaa\n(no match in any of [<Module aceite_c1.py>])\n\nno tests ran in 0.01s\n"
UNITTEST_OK: str = ".\n----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK\n"
UNITTEST_PULADO: str = "s\n----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK (skipped=1)\n"
UNITTEST_FALHA: str = (
    "F\n======================================================================\nFAIL: test_c1_media (aceite.test_c1.TestC1.test_c1_media)\n"
    "----------------------------------------------------------------------\nAssertionError: 1 != 1.5\n\n"
    "----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nFAILED (failures=1)\n"
)
UNITTEST_ERRO: str = (
    "E\n======================================================================\nERROR: test_c1_media (aceite.test_c1.TestC1.test_c1_media)\n"
    "ModuleNotFoundError: No module named 'estatistica'\n----------------------------------------------------------------------\n"
    "Ran 1 test in 0.001s\n\nFAILED (errors=1)\n"
)
NODE: str = 'node --test --test-name-pattern="c1 media" aceite/c1.test.mjs'


def _tap(nome: str, *, passou: int = 0, falhou: int = 0, pulou: int = 0, erro: str = "AssertionError") -> str:
    """A saída TAP do node:test para um teste."""
    linha = f"ok 1 - {nome}" if passou or pulou else f"not ok 1 - {nome}\n  failureType: 'testCodeFailure'\n  name: '{erro}'"
    return (f"# Subtest: {nome}\n{linha}\n1..1\n# tests 1\n# suites 0\n# pass {passou}\n# fail {falhou}\n# cancelled 0\n"
            f"# skipped {pulou}\n# todo 0\n# duration_ms 74.7\n")


JEST_FALHA: str = (
    "FAIL aceite/c1.test.js\n  ✕ c1 media (3 ms)\n\n  ● c1 media\n\n    expect(received).toBe(expected)\n\n"
    "Tests:       1 failed, 1 total\nTest Suites: 1 failed, 1 total\n"
)
JEST_PULADO: str = "PASS aceite/c1.test.js\n  ○ skipped c1 media\n\nTests:       1 skipped, 1 total\n"
VITEST_VERDE: str = " ✓ aceite/c1.test.js (1 test) 2ms\n\n Test Files  1 passed (1)\n      Tests  1 passed (1)\n"
VITEST_TODO: str = " Test Files  1 passed (1)\n      Tests  1 passed | 1 todo (2)\n"
MOCHA_PENDENTE: str = "  c1\n    ✓ c1 media\n    - c1 mediana\n\n  1 passing (5ms)\n  1 pending\n"


@pytest.mark.parametrize(
    ("comando", "codigo", "saida", "verde"),
    [
        (PYTEST, 0, PYTEST_VERDE, True),
        (PYTEST, 0, PYTEST_PULADO, False),
        (PYTEST, 0, PYTEST_XFAIL, False),
        (PYTEST, 0, "", False),
        (PYTEST, 0, "aceite ok\n", False),
        (PYTEST, 0, PYTEST_VERDE.replace("\n", "\r\n"), True),
        (PYTEST, 0, ".                                                                        [100%]\r\n", True),
        (PYTEST, 0, ".s                                                                       [100%]\r\n", False),
        (UNITTEST, 0, UNITTEST_OK, True),
        (UNITTEST, 0, UNITTEST_PULADO, False),
        (UNITTEST, 0, "\n----\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n", False),
        (NODE, 0, _tap("c1 media", passou=1), True),
        (NODE, 0, _tap("c1 media", pulou=1).replace("# skipped 1", "# skipped 1"), False),
        ("npx jest aceite", 0, JEST_PULADO, False),
        ("npx vitest run aceite", 0, VITEST_VERDE, True),
        ("npx vitest run aceite", 0, VITEST_TODO, False),
        ("npx mocha aceite", 0, MOCHA_PENDENTE, False),
        ("python aceite/aceite_c1.py", 0, "aceite ok\n", True),
        ("python aceite/aceite_c1.py", 0, "", False),
        ("python aceite/aceite_c1.py", 0, "test skipped: sem rede\n", False),
        ("python aceite/aceite_c1.py", 1, "aceite ok\n", False),
        ("python aceite/aceite_c1.py", None, "", False),
    ],
    ids=["pytest-verde", "pytest-skip", "pytest-xfail", "pytest-calado", "pytest-trocado", "pytest-crlf", "pytest-qq-so-progresso",
         "pytest-qq-com-skip", "unittest-ok", "unittest-skip",
         "unittest-nenhum", "node-verde", "node-skip", "jest-skip", "vitest-verde", "vitest-todo", "mocha-pending",
         "desconhecido-verde", "desconhecido-calado", "desconhecido-fala-em-pular", "codigo-1", "tempo-esgotado"],
)
def test_verde_so_quando_o_runner_diz_que_passou_sem_pular_edge_case(comando: str, codigo: int | None, saida: str, verde: bool) -> None:
    """Caso de borda: zero com teste pulado, esperado falho, por fazer, ou sem o resumo do runner chamado, não é verde."""
    motivo = por_que_nao_passou(comando, codigo, saida)

    assert (motivo == "") is verde, motivo


@pytest.mark.parametrize(
    ("comando", "codigo", "saida", "nome", "trecho"),
    [
        (PYTEST, 1, PYTEST_ASSERCAO, "test_c1_media", ""),
        (PYTEST, 1, PYTEST_ASSERCAO, "aceite/aceite_c1.py::test_c1_media", ""),
        (PYTEST, 1, PYTEST_ASSERCAO.replace("\n", "\r\n"), "test_c1_media", ""),
        (PYTEST, 1, PYTEST_IMPORT_NO_TESTE.replace("\n", "\r\n"), "test_c1_media", "ModuleNotFoundError"),
        (PYTEST, 1, PYTEST_IMPORT_NO_TESTE, "test_c1_media", "ModuleNotFoundError"),
        (PYTEST, 1, PYTEST_RESUMO_CORTADO, "test_c1_mediana_impar_par_e_nao_altera", ""),
        (PYTEST, 1, PYTEST_RESUMO_CORTADO.replace("14: AssertionError", "14: NameError"), "test_c1_mediana_impar_par_e_nao_altera",
         "NameError"),
        (PYTEST, 2, PYTEST_COLETA, "test_c1_media", "o pytest saiu com 2"),
        (PYTEST, 4, PYTEST_NAO_ACHOU, "test_c1_mediaa", "o pytest saiu com 4"),
        (PYTEST, 1, PYTEST_ASSERCAO, "test_c1_outro", "nao aparece como falho"),
        (PYTEST, 1, PYTEST_ASSERCAO.replace("1 failed in", "1 failed, 1 error in"), "test_c1_media", "erro(s)"),
        (PYTEST, 1, "FAILED aceite/aceite_c1.py::test_c1_media\n", "test_c1_media", "nao tem o resumo"),
        (UNITTEST, 1, UNITTEST_FALHA, "test_c1_media", ""),
        (UNITTEST, 1, UNITTEST_ERRO, "test_c1_media", "erro(s)"),
        (NODE, 1, _tap("c1 media", falhou=1), "c1 media", ""),
        (NODE, 1, _tap("c1 media", falhou=1, erro="ReferenceError"), "c1 media", "ReferenceError"),
        (NODE, 1, _tap("c1.test.mjs", falhou=1, erro="Error") + "Error [ERR_MODULE_NOT_FOUND]", "c1 media", "nao aparece"),
        ("npx jest aceite", 1, JEST_FALHA, "c1 media", ""),
        ("npx jest aceite", 1, JEST_FALHA.replace("expect(received).toBe(expected)", "Cannot find module '../media'"),
         "c1 media", "Cannot find module"),
        ("bash aceite/c1.sh", 127, "bash: estatistica: command not found\n", "c1", "codigo 127"),
        ("python aceite/aceite_c1.py", 1, 'File "aceite/aceite_c1.py", line 9, in test_c1_media\nAssertionError\n', "test_c1_media", ""),
        ("python aceite/aceite_c1.py", 1, "in test_c1_media\nModuleNotFoundError: No module named 'x'\n", "test_c1_media",
         "ModuleNotFoundError"),
        ("python aceite/aceite_c1.py", 0, "aceite ok\n", "test_c1_media", "saiu com zero"),
        ("python aceite/aceite_c1.py", None, "", "test_c1_media", "tempo acabou"),
    ],
    ids=["pytest-assercao", "pytest-nome-completo", "pytest-crlf", "pytest-import-crlf", "pytest-import-no-corpo", "pytest-resumo-cortado", "pytest-cortado-sem-assercao",
         "pytest-coleta", "pytest-nome-errado",
         "pytest-outro-teste", "pytest-com-erro", "pytest-sem-resumo", "unittest-failures", "unittest-errors", "node-assercao",
         "node-referencia", "node-arquivo-nao-carrega", "jest-expect", "jest-modulo", "comando-ausente", "desconhecido-assercao",
         "desconhecido-import", "verde", "tempo"],
)
def test_vermelho_so_vale_pela_assercao_do_teste_declarado_edge_case(
    comando: str, codigo: int | None, saida: str, nome: str, trecho: str
) -> None:
    """Caso de borda: import, coleta, comando ausente, nome errado e erro fora da asserção são vermelho pelo motivo errado."""
    motivo = por_que_o_vermelho_nao_vale(comando, codigo, saida, nome=nome)

    assert (motivo == "") is (trecho == ""), motivo
    assert trecho in motivo
