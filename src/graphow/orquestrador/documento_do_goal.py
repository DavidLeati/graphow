"""O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências.

Um texto só, duas leituras: o mesmo plano que o livro-razão guarda vai
commitado na branch do Goal, onde o humano o revisa como revisa código. As
pendências (os acompanhamentos que a verificação achou e os bloqueantes que
sobraram depois dos dois ciclos de correção) entram numa seção própria, que o
orquestrador reescreve a cada verificação.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.saidas import Plano

PASTA_DOS_DOCUMENTOS: str = "docs/goals"
TITULO_DAS_PENDENCIAS: str = "## Pendencias"
TITULO_DO_ACEITE: str = "## Testes de aceite"


def caminho_do_documento(slug: str) -> str:
    """O caminho do documento do Goal, relativo à raiz do repositório."""
    return f"{PASTA_DOS_DOCUMENTOS}/{slug}.md"


def renderizar_documento(id_goal: str, configuracao: m.ConfiguracaoDoGoal, plano: Plano, *, spec: str) -> str:
    """O documento do Goal recém-planejado, sem pendências ainda."""
    cabecalho = (
        f"> Goal `{id_goal}` do graphow, escrito pelo `graphow orquestrar`. Modo {configuracao.modo}, "
        f"branch `{configuracao.ramo}` criada de `{configuracao.base}`. Suite: `{plano.comando_suite}`."
    )
    linhas = [
        f"# {plano.titulo}", "", cabecalho, "",
        "## Criterios de aceite", *(f"- **{c.id}** ({c.verificacao}): {c.texto}" for c in plano.criterios), "",
        "## Decisoes", *(f"- **{d.id}**: {d.texto} Motivo: {d.motivo}" for d in plano.decisoes), "",
        "## Plano", *_tabela_do_plano(plano), "",
        "## Marcos", *_linhas_dos_marcos(plano), "",
        "## Fora do escopo", *(f"- {item}" for item in plano.fora_do_escopo or ("nada registrado",)), "",
        "## Spec", "", spec.strip(), "",
        TITULO_DAS_PENDENCIAS, "", "Nenhuma ate agora.", "",
    ]
    return "\n".join(linhas)


def _linhas_dos_marcos(plano: Plano) -> list[str]:
    """Cada marco com as fatias e os critérios que a verificação dele julga; o último é a verificação final."""
    ultimo = plano.marcos[-1].id if plano.marcos else ""
    return [
        f"- **{marco.id}** {marco.titulo}: fatias {', '.join(marco.fatias)}; "
        + ("verificacao final, sobre o Goal inteiro" if marco.id == ultimo else f"verifica {', '.join(plano.criterios_do_marco(marco.id))}")
        for marco in plano.marcos
    ]


def _tabela_do_plano(plano: Plano) -> list[str]:
    """As fatias numa tabela Markdown."""
    return [
        "| Fatia | Titulo | Criterios | Depende de | Arquivos |",
        "| :--- | :--- | :--- | :--- | :--- |",
        *(
            f"| {f.id} | {f.titulo}{' (risco)' if f.risco else ''} | {', '.join(f.criterios)} | {', '.join(f.depende_de) or '-'} | "
            f"{', '.join(f.arquivos) or '-'} |"
            for f in plano.fatias
        ),
    ]


def com_aceite(documento: str, linhas: Sequence[str]) -> str:
    """O documento com a seção dos testes de aceite logo antes das pendências (reescrita, se já havia)."""
    corpo, separador, resto = documento.partition(f"\n{TITULO_DAS_PENDENCIAS}\n")
    corpo = corpo.split(f"\n{TITULO_DO_ACEITE}\n")[0].rstrip("\n")
    secao = "\n".join([TITULO_DO_ACEITE, "", *linhas])
    return f"{corpo}\n\n{secao}\n" + (f"\n{TITULO_DAS_PENDENCIAS}\n{resto}" if separador else "")


def com_pendencias(documento: str, pendencias: Sequence[Mapping[str, Any]]) -> str:
    """O documento com a seção de pendências reescrita."""
    corpo = documento.split(f"\n{TITULO_DAS_PENDENCIAS}\n")[0].rstrip("\n")
    itens = [_linha_da_pendencia(item) for item in pendencias] or ["Nenhuma ate agora."]
    return "\n".join([corpo, "", TITULO_DAS_PENDENCIAS, "", *itens, ""])


def _linha_da_pendencia(item: Mapping[str, Any]) -> str:
    """Uma pendência com a gravidade, o local e a origem."""
    local = f" ({item['local']})" if item.get("local") else ""
    achado = f", Achado {item['achado']}" if item.get("achado") else ""
    return f"- [{item.get('gravidade', 'pendencia')}] {item.get('titulo', '')}{local}: {item.get('descricao', '')} " \
           f"Origem: {item.get('origem', '')}{achado}."


def escrever_documento(area: Path, slug: str, conteudo: str) -> Path:
    """Grava o documento na área do Goal e devolve o caminho."""
    caminho = area / caminho_do_documento(slug)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")
    return caminho
