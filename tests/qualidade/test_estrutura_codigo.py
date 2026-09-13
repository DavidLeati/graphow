"""Verificação estrita das premissas estruturais de tamanho, assinatura e tipagem."""

import ast

from tests.qualidade.analise_ast import analisar_codigo_fonte, coletar_arquivos_codigo_fonte, coletar_funcoes

LIMITE_DE_LINHAS_POR_ARQUIVO: int = 400
LIMITE_DE_LINHAS_POR_FUNCAO: int = 30
LIMITE_DE_PARAMETROS_POSICIONAIS: int = 3

PARAMETROS_IMPLICITOS: frozenset[str] = frozenset({"self", "cls"})


def test_tamanho_maximo_de_arquivos_limite_400_linhas() -> None:
    """Valida que nenhum arquivo em src/graphow ultrapassa o limite estrito de linhas."""
    arquivos = coletar_arquivos_codigo_fonte()
    assert len(arquivos) > 0

    violacoes = [
        f"  {arquivo.name}: {len(arquivo.read_text(encoding='utf-8').splitlines())} linhas"
        for arquivo in arquivos
        if len(arquivo.read_text(encoding="utf-8").splitlines()) > LIMITE_DE_LINHAS_POR_ARQUIVO
    ]
    assert not violacoes, f"Arquivos acima de {LIMITE_DE_LINHAS_POR_ARQUIVO} linhas:\n" + "\n".join(violacoes)


def test_tamanho_maximo_de_funcoes_limite_30_linhas() -> None:
    """Valida que nenhuma função ou método ultrapassa o limite estrito de linhas."""
    violacoes: list[str] = []
    for arquivo in analisar_codigo_fonte():
        violacoes.extend(_coletar_funcoes_longas(arquivo.nome, arquivo.arvore))
    assert not violacoes, f"Funcoes acima de {LIMITE_DE_LINHAS_POR_FUNCAO} linhas:\n" + "\n".join(violacoes)


def _coletar_funcoes_longas(nome_arquivo: str, arvore: ast.Module) -> list[str]:
    """Lista as funções do módulo cujo corpo excede o limite de linhas."""
    violacoes: list[str] = []
    for funcao in coletar_funcoes(arvore):
        total_linhas = (funcao.end_lineno or funcao.lineno) - funcao.lineno + 1
        if total_linhas > LIMITE_DE_LINHAS_POR_FUNCAO:
            violacoes.append(f"  {nome_arquivo}::{funcao.name} tem {total_linhas} linhas")
    return violacoes


def test_quantidade_maxima_de_argumentos_posicionais() -> None:
    """Valida que funções possuem no máximo três argumentos posicionais."""
    violacoes: list[str] = []
    for arquivo in analisar_codigo_fonte():
        violacoes.extend(_coletar_assinaturas_largas(arquivo.nome, arquivo.arvore))
    assert not violacoes, "Assinaturas com parametros demais:\n" + "\n".join(violacoes)


def _coletar_assinaturas_largas(nome_arquivo: str, arvore: ast.Module) -> list[str]:
    """Lista as funções do módulo com excesso de parâmetros posicionais."""
    violacoes: list[str] = []
    for funcao in coletar_funcoes(arvore):
        posicionais = [arg.arg for arg in funcao.args.args if arg.arg not in PARAMETROS_IMPLICITOS]
        if len(posicionais) > LIMITE_DE_PARAMETROS_POSICIONAIS:
            violacoes.append(f"  {nome_arquivo}::{funcao.name} tem {len(posicionais)} parametros")
    return violacoes


def test_tipagem_estatica_explicita_100_porcento() -> None:
    """Valida que 100% das funções possuem retorno e parâmetros tipados."""
    violacoes: list[str] = []
    for arquivo in analisar_codigo_fonte():
        violacoes.extend(_coletar_lacunas_de_tipagem(arquivo.nome, arquivo.arvore))
    assert not violacoes, "Lacunas de tipagem:\n" + "\n".join(violacoes)


def _coletar_lacunas_de_tipagem(nome_arquivo: str, arvore: ast.Module) -> list[str]:
    """Lista retornos e parâmetros sem anotação de tipo no módulo."""
    violacoes: list[str] = []
    for funcao in coletar_funcoes(arvore):
        if funcao.name != "__init__" and funcao.returns is None:
            violacoes.append(f"  {nome_arquivo}::{funcao.name} sem anotacao de retorno")
        violacoes.extend(_coletar_parametros_sem_tipo(nome_arquivo, funcao))
    return violacoes


def _coletar_parametros_sem_tipo(nome_arquivo: str, funcao: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Lista os parâmetros da função que não declaram tipo."""
    return [
        f"  {nome_arquivo}::{funcao.name} parametro '{argumento.arg}' sem tipo"
        for argumento in funcao.args.args
        if argumento.arg not in PARAMETROS_IMPLICITOS and argumento.annotation is None
    ]
