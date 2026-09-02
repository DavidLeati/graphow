"""Utilitários de análise sintática compartilhados pelas verificações de qualidade."""

import ast
from dataclasses import dataclass
from pathlib import Path

RAIZ_CODIGO_FONTE: Path = Path(__file__).parent.parent.parent / "src" / "graphow"

TIPOS_DE_BLOCO_ANINHAVEL: tuple[type[ast.stmt], ...] = (ast.If, ast.For, ast.While, ast.AsyncFor)
TIPOS_DE_FUNCAO: tuple[type[ast.AST], ...] = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class ArquivoAnalisado:
    """Par imutável de caminho e árvore sintática de um módulo do código-fonte."""

    caminho: Path
    arvore: ast.Module

    @property
    def nome(self) -> str:
        """Nome do arquivo, usado nas mensagens de falha."""
        return self.caminho.name


def coletar_arquivos_codigo_fonte() -> tuple[Path, ...]:
    """Enumera todos os módulos Python sob src/graphow."""
    return tuple(sorted(RAIZ_CODIGO_FONTE.rglob("*.py")))


def analisar_codigo_fonte() -> tuple[ArquivoAnalisado, ...]:
    """Lê e converte cada módulo do código-fonte em sua árvore sintática."""
    return tuple(
        ArquivoAnalisado(caminho=caminho, arvore=ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho)))
        for caminho in coletar_arquivos_codigo_fonte()
    )


def coletar_funcoes(arvore: ast.Module) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    """Coleta todas as funções e métodos declarados no módulo."""
    return tuple(no for no in ast.walk(arvore) if isinstance(no, TIPOS_DE_FUNCAO))


def calcular_profundidade_de_aninhamento(funcao: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Mede o maior encadeamento de blocos de controle dentro do corpo da função."""
    return max((_profundidade_do_no(comando, 0) for comando in funcao.body), default=0)


def _profundidade_do_no(no: ast.AST, profundidade_atual: int) -> int:
    """Percorre recursivamente o comando somando um nível por bloco de controle."""
    if isinstance(no, TIPOS_DE_FUNCAO):
        return profundidade_atual
    profundidade_neste_no = profundidade_atual + 1 if isinstance(no, TIPOS_DE_BLOCO_ANINHAVEL) else profundidade_atual
    filhos = list(ast.iter_child_nodes(no))
    if not filhos:
        return profundidade_neste_no
    return max([profundidade_neste_no] + [_profundidade_do_no(filho, profundidade_neste_no) for filho in filhos])


def coletar_manipuladores_de_excecao(arvore: ast.Module) -> tuple[ast.ExceptHandler, ...]:
    """Coleta todas as cláusulas except declaradas no módulo."""
    return tuple(no for no in ast.walk(arvore) if isinstance(no, ast.ExceptHandler))


def nomear_tipo_capturado(manipulador: ast.ExceptHandler) -> str:
    """Descreve, em texto, a classe de exceção que a cláusula captura."""
    if manipulador.type is None:
        return "except nu (sem classe)"
    return ast.unparse(manipulador.type)
