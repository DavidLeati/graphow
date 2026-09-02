"""Verificação das premissas de aninhamento raso e captura cirúrgica de exceções."""

import ast

from tests.qualidade.analise_ast import (
    analisar_codigo_fonte,
    calcular_profundidade_de_aninhamento,
    coletar_funcoes,
    coletar_manipuladores_de_excecao,
    nomear_tipo_capturado,
)

PROFUNDIDADE_MAXIMA_DE_ANINHAMENTO: int = 2

CLASSES_DE_CAPTURA_GENERICA: frozenset[str] = frozenset({"Exception", "BaseException"})


def test_aninhamento_maximo_de_dois_niveis() -> None:
    """Nenhuma função pode encadear mais de dois blocos de controle."""
    violacoes: list[str] = []
    for arquivo in analisar_codigo_fonte():
        violacoes.extend(_coletar_violacoes_de_aninhamento(arquivo.nome, arquivo.arvore))
    assert not violacoes, "Aninhamento excessivo:\n" + "\n".join(violacoes)


def _coletar_violacoes_de_aninhamento(nome_arquivo: str, arvore: ast.Module) -> list[str]:
    """Lista as funções do módulo que excedem a profundidade permitida."""
    violacoes: list[str] = []
    for funcao in coletar_funcoes(arvore):
        profundidade = calcular_profundidade_de_aninhamento(funcao)
        if profundidade > PROFUNDIDADE_MAXIMA_DE_ANINHAMENTO:
            violacoes.append(f"  {nome_arquivo}::{funcao.name} tem profundidade {profundidade}")
    return violacoes


def test_captura_de_excecao_sempre_especifica() -> None:
    """Toda cláusula except deve nomear classes concretas, nunca capturas genéricas."""
    violacoes: list[str] = []
    for arquivo in analisar_codigo_fonte():
        violacoes.extend(_coletar_capturas_genericas(arquivo.nome, arquivo.arvore))
    assert not violacoes, "Captura generica de excecao:\n" + "\n".join(violacoes)


def _coletar_capturas_genericas(nome_arquivo: str, arvore: ast.Module) -> list[str]:
    """Lista as cláusulas except do módulo que capturam sem filtro de classe."""
    violacoes: list[str] = []
    for manipulador in coletar_manipuladores_de_excecao(arvore):
        descricao = nomear_tipo_capturado(manipulador)
        if _eh_captura_generica(manipulador):
            violacoes.append(f"  {nome_arquivo}:{manipulador.lineno} captura '{descricao}'")
    return violacoes


def _eh_captura_generica(manipulador: ast.ExceptHandler) -> bool:
    """Indica se a cláusula captura tudo, ou uma classe raiz da hierarquia."""
    if manipulador.type is None:
        return True
    return bool(_extrair_nomes_de_classe(manipulador.type) & CLASSES_DE_CAPTURA_GENERICA)


def _extrair_nomes_de_classe(expressao: ast.expr) -> frozenset[str]:
    """Extrai os nomes das classes citadas na cláusula, inclusive em tuplas."""
    if isinstance(expressao, ast.Name):
        return frozenset({expressao.id})
    if isinstance(expressao, ast.Attribute):
        return frozenset({expressao.attr})
    if isinstance(expressao, ast.Tuple):
        return frozenset().union(*(_extrair_nomes_de_classe(item) for item in expressao.elts))
    return frozenset()


def test_analisador_de_aninhamento_reconhece_excesso_edge_case() -> None:
    """Caso de borda: o próprio analisador acusa três níveis encadeados."""
    codigo = (
        "def exemplo(itens):\n"
        "    for item in itens:\n"
        "        if item:\n"
        "            while item:\n"
        "                item = None\n"
    )
    funcao = coletar_funcoes(ast.parse(codigo))[0]
    assert calcular_profundidade_de_aninhamento(funcao) == 3


def test_analisador_de_aninhamento_ignora_sequencias_planas_edge_case() -> None:
    """Caso de borda: guardas sequenciais no mesmo nível não somam profundidade."""
    codigo = (
        "def exemplo(valor):\n"
        "    if valor is None:\n"
        "        return 0\n"
        "    if valor < 0:\n"
        "        return -1\n"
        "    return 1\n"
    )
    funcao = coletar_funcoes(ast.parse(codigo))[0]
    assert calcular_profundidade_de_aninhamento(funcao) == 1


def test_detector_de_captura_generica_aceita_classes_concretas_edge_case() -> None:
    """Caso de borda: tupla de classes concretas não é considerada captura genérica."""
    codigo = "try:\n    pass\nexcept (ValueError, KeyError):\n    pass\n"
    manipulador = coletar_manipuladores_de_excecao(ast.parse(codigo))[0]
    assert _eh_captura_generica(manipulador) is False


def test_detector_de_captura_generica_reprova_except_nu_edge_case() -> None:
    """Caso de borda: except sem classe alguma é reprovado."""
    codigo = "try:\n    pass\nexcept:\n    pass\n"
    manipulador = coletar_manipuladores_de_excecao(ast.parse(codigo))[0]
    assert _eh_captura_generica(manipulador) is True
    assert nomear_tipo_capturado(manipulador) == "except nu (sem classe)"
