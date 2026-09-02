"""Toda recusa dos portões declara o próprio modo de falha.

O classificador MAST decidia por substring da mensagem em português: "ciclo",
"permissão", "orçamento". Funcionava e quebraria em silêncio na primeira
reescrita de texto — nenhum teste amarrava a mensagem ao diagnóstico. Este teste
de AST amarra o contrário, que é o que importa: quem recusa nomeia o modo.
Ver achado A-13.
"""

import ast
from pathlib import Path

from graphow.core.falhas import CATEGORIA_POR_MODO, ModoFalhaMAST

RAIZ_KERNEL: Path = Path(__file__).parent.parent.parent / "src" / "graphow" / "kernel"

ARQUIVOS_DE_PORTAO: tuple[str, ...] = ("schema_gate.py", "role_gate.py", "invariant_gate.py")


def _coletar_recusas(caminho: Path) -> list[ast.Call]:
    """Reúne as chamadas a `ResultadoValidacao.falha` de um módulo."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    return [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "falha"
    ]


def _declara_modo(chamada: ast.Call) -> bool:
    """Informa se a chamada nomeia o argumento `modo`."""
    return any(palavra.arg == "modo" for palavra in chamada.keywords)


def test_todo_portao_declara_o_modo_de_falha_nominal() -> None:
    """Uma recusa sem modo volta a depender do texto para ser classificada."""
    sem_modo: list[str] = []
    for arquivo in ARQUIVOS_DE_PORTAO:
        caminho = RAIZ_KERNEL / arquivo
        sem_modo.extend(
            f"  {arquivo}:{chamada.lineno}"
            for chamada in _coletar_recusas(caminho)
            if not _declara_modo(chamada)
        )

    assert not sem_modo, "Recusas sem modo declarado:\n" + "\n".join(sem_modo)


def test_os_portoes_recusam_de_fato_edge_case() -> None:
    """Caso de borda: o teste acima passaria vazio se ninguém recusasse nada."""
    total = sum(len(_coletar_recusas(RAIZ_KERNEL / arquivo)) for arquivo in ARQUIVOS_DE_PORTAO)

    assert total >= 20


def test_todo_modo_tem_categoria_declarada_edge_case() -> None:
    """Caso de borda: um modo novo sem categoria cairia no balde genérico."""
    ausentes = [modo.value for modo in ModoFalhaMAST if modo not in CATEGORIA_POR_MODO]

    assert not ausentes, ausentes
