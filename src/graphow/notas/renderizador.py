"""Renderização das notas em Markdown, no formato "afirmação, como se sabe, como aplicar".

Uma afirmação sem evidência é lida com autoridade meses depois, quando ninguém
lembra se foi verificada. Por isso cada nota abre com a afirmação e diz em
seguida de onde ela veio, com o identificador e a posição no log de cada
origem: quem quiser conferir sabe onde olhar. Os links entre notas saem de
`substitui` e `contradiz`, nunca de texto escrito à mão.
"""

from collections.abc import Sequence

from graphow.notas.modelo import NotaDeAprendizado, OrigemDaNota

AVISO_DE_GERACAO: str = (
    "> Nota gerada a partir do grafo por `graphow notas-gerar`. Não edite à mão: a próxima\n"
    "> geração sobrescreve. Para mudar o texto, mude o grafo; `--conferir` acusa a deriva."
)
NOME_DO_INDICE: str = "INDEX.md"
TITULO_DO_INDICE: str = "# Acervo de aprendizados"
ALCANCE_GLOBAL_NO_INDICE: str = "global"


def renderizar_nota(nota: NotaDeAprendizado) -> str:
    """Uma nota inteira: afirmação, como se sabe, como aplicar e os avisos."""
    linhas = [
        f"# {nota.afirmacao}",
        "",
        AVISO_DE_GERACAO,
        "",
        nota.afirmacao,
        "",
        f"**Como se sabe:** {_citar(nota.origens) or 'a origem foi removida do grafo'}",
        f"**Como aplicar:** {nota.como_aplicar or '(não declarado)'}",
        "",
    ]
    linhas.extend(_linhas_de_metadados(nota))
    return "\n".join(linhas) + "\n"


def _citar(origens: Sequence[OrigemDaNota]) -> str:
    """As origens em uma frase, separadas por ponto e vírgula."""
    return "; ".join(origem.descrever() for origem in origens)


def _linhas_de_metadados(nota: NotaDeAprendizado) -> list[str]:
    """Alcance, autoria e os avisos derivados das arestas."""
    linhas = [
        f"- Alcance: {', '.join(nota.alcances) if nota.alcances else 'nenhum'}",
        f"- Registrado por: {nota.autor} ({nota.papel}), log #{nota.seq_criacao}",
    ]
    if nota.valido_ate:
        linhas.append(f"- Válido até: {nota.valido_ate}")
    if nota.substituto is not None:
        linhas.append(f"- Substituído por: [[{nota.substituto}]] (não siga esta nota)")
    if nota.contradicoes:
        linhas.append(f"- Contradito por: {_citar(nota.contradicoes)} (precisa de revisão)")
    return linhas


def renderizar_indice(notas: Sequence[NotaDeAprendizado]) -> str:
    """O índice do acervo: as notas por alcance, com as substituídas marcadas."""
    vigentes = sum(1 for nota in notas if nota.esta_vigente)
    linhas = [
        TITULO_DO_INDICE,
        "",
        AVISO_DE_GERACAO,
        "",
        f"{len(notas)} notas · {vigentes} vigentes · {len(notas) - vigentes} substituídas",
        "",
    ]
    for alcance in _alcances_em_ordem(notas):
        linhas.extend(_secao_do_alcance(alcance, notas))
    return "\n".join(linhas) + "\n"


def _alcances_em_ordem(notas: Sequence[NotaDeAprendizado]) -> tuple[str, ...]:
    """Global primeiro, depois os contêineres em ordem alfabética."""
    alcances = {alcance for nota in notas for alcance in nota.alcances}
    ordenados = sorted(alcances - {ALCANCE_GLOBAL_NO_INDICE})
    if ALCANCE_GLOBAL_NO_INDICE in alcances:
        return (ALCANCE_GLOBAL_NO_INDICE, *ordenados)
    return tuple(ordenados)


def _secao_do_alcance(alcance: str, notas: Sequence[NotaDeAprendizado]) -> list[str]:
    """As notas que valem para o alcance, uma linha cada, com link para a nota."""
    linhas = [f"## {alcance}", ""]
    for nota in notas:
        if alcance in nota.alcances:
            marca = "" if nota.esta_vigente else " (substituída)"
            linhas.append(f"- [[{nota.id}]] {nota.afirmacao}{marca}")
    linhas.append("")
    return linhas
