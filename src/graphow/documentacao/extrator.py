"""Extração do catálogo de código a partir da árvore sintática dos módulos."""

import ast

from graphow.core.exceptions import GraphowError
from graphow.documentacao.leitura_fonte import ArquivoFonte
from graphow.documentacao.modelo import (
    ClasseDocumentada,
    ConstanteDocumentada,
    FuncaoDocumentada,
    ModuloDocumentado,
    ParametroDocumentado,
    resumir_docstring,
)

PARAMETROS_IMPLICITOS: frozenset[str] = frozenset({"self", "cls"})
ANOTACAO_AUSENTE: str = "sem anotacao"
BASE_ABSTRATA: str = "ABC"
LIMITE_DE_VALOR_EXIBIDO: int = 72

TIPOS_DE_FUNCAO: tuple[type[ast.AST], ...] = (ast.FunctionDef, ast.AsyncFunctionDef)


def _texto_da_anotacao(anotacao: ast.expr | None) -> str:
    """Converte a anotação de tipo em texto, ou sinaliza a ausência dela."""
    if anotacao is None:
        return ANOTACAO_AUSENTE
    return ast.unparse(anotacao)


def _nomes_dos_decoradores(no: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> frozenset[str]:
    """Coleta os nomes simples dos decoradores aplicados ao elemento."""
    nomes: list[str] = []
    for decorador in no.decorator_list:
        alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
        nomes.append(alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", ""))
    return frozenset(nome for nome in nomes if nome)


def _eh_dataclass_congelada(no: ast.ClassDef) -> bool:
    """Detecta @dataclass(frozen=True), que marca as estruturas imutáveis."""
    for decorador in no.decorator_list:
        if not isinstance(decorador, ast.Call) or "dataclass" not in ast.unparse(decorador.func):
            continue
        if any(_argumento_congela(argumento) for argumento in decorador.keywords):
            return True
    return False


def _argumento_congela(argumento: ast.keyword) -> bool:
    """Identifica o argumento frozen=True dentro do decorador de dataclass."""
    return argumento.arg == "frozen" and ast.unparse(argumento.value) == "True"


def _extrair_parametros(no: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[ParametroDocumentado, ...]:
    """Lista os parâmetros posicionais, ignorando self e cls."""
    return tuple(
        ParametroDocumentado(nome=argumento.arg, anotacao=_texto_da_anotacao(argumento.annotation))
        for argumento in no.args.args
        if argumento.arg not in PARAMETROS_IMPLICITOS
    )


def _extrair_funcao(no: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncaoDocumentada:
    """Converte a definição de função no seu registro de catálogo."""
    decoradores = _nomes_dos_decoradores(no)
    return FuncaoDocumentada(
        nome=no.name,
        parametros=_extrair_parametros(no),
        retorno=_texto_da_anotacao(no.returns),
        resumo=resumir_docstring(ast.get_docstring(no)),
        linhas=(no.end_lineno or no.lineno) - no.lineno + 1,
        eh_publica=not no.name.startswith("_"),
        eh_propriedade="property" in decoradores,
        eh_abstrata="abstractmethod" in decoradores,
    )


def _extrair_campos(no: ast.ClassDef) -> tuple[ParametroDocumentado, ...]:
    """Coleta os atributos anotados no corpo da classe."""
    return tuple(
        ParametroDocumentado(nome=comando.target.id, anotacao=_texto_da_anotacao(comando.annotation))
        for comando in no.body
        if isinstance(comando, ast.AnnAssign) and isinstance(comando.target, ast.Name)
    )


def _extrair_classe(no: ast.ClassDef) -> ClasseDocumentada:
    """Converte a definição de classe no seu registro de catálogo."""
    metodos = tuple(_extrair_funcao(item) for item in no.body if isinstance(item, TIPOS_DE_FUNCAO))
    bases = tuple(ast.unparse(base) for base in no.bases)
    return ClasseDocumentada(
        nome=no.name,
        bases=bases,
        resumo=resumir_docstring(ast.get_docstring(no)),
        metodos=metodos,
        campos=_extrair_campos(no),
        eh_imutavel=_eh_dataclass_congelada(no),
        eh_abstrata=BASE_ABSTRATA in bases or any(metodo.eh_abstrata for metodo in metodos),
    )


def _extrair_constante(comando: ast.AnnAssign) -> ConstanteDocumentada | None:
    """Converte uma atribuição anotada de módulo em constante documentada."""
    if not isinstance(comando.target, ast.Name) or not comando.target.id.isupper():
        return None
    valor = ast.unparse(comando.value) if comando.value is not None else ""
    return ConstanteDocumentada(
        nome=comando.target.id,
        anotacao=_texto_da_anotacao(comando.annotation),
        valor=_encurtar(valor),
    )


def _encurtar(valor: str) -> str:
    """Reduz valores longos a uma forma legível em tabela."""
    achatado = " ".join(valor.split())
    if len(achatado) <= LIMITE_DE_VALOR_EXIBIDO:
        return achatado
    return achatado[: LIMITE_DE_VALOR_EXIBIDO - 1] + "…"


class ExtratorCatalogo:
    """Traduz arquivos-fonte em registros de catálogo, sem tocar em disco."""

    def extrair_modulo(self, arquivo: ArquivoFonte) -> ModuloDocumentado:
        """Analisa um módulo e devolve tudo que ele expõe."""
        arvore = self._analisar(arquivo)
        constantes = tuple(
            constante
            for constante in (
                _extrair_constante(comando)
                for comando in arvore.body
                if isinstance(comando, ast.AnnAssign)
            )
            if constante is not None
        )
        return ModuloDocumentado(
            caminho_relativo=arquivo.caminho_relativo,
            nome_modulo=arquivo.nome_modulo,
            resumo=resumir_docstring(ast.get_docstring(arvore)),
            linhas=arquivo.total_linhas,
            classes=tuple(_extrair_classe(no) for no in arvore.body if isinstance(no, ast.ClassDef)),
            funcoes=tuple(_extrair_funcao(no) for no in arvore.body if isinstance(no, TIPOS_DE_FUNCAO)),
            constantes=constantes,
        )

    def _analisar(self, arquivo: ArquivoFonte) -> ast.Module:
        """Constrói a árvore sintática, apontando o arquivo em caso de erro."""
        try:
            return ast.parse(arquivo.conteudo, filename=arquivo.caminho_relativo)
        except SyntaxError as erro:
            raise GraphowError(
                f"Modulo com sintaxe invalida: {erro}", {"caminho": arquivo.caminho_relativo}
            ) from erro
