"""O documento do Goal no repositório: `docs/goals/<slug>.md`, a spec com o plano e as pendências.

Um texto só, duas leituras: o mesmo plano que o livro-razão guarda vai
commitado na branch do Goal, onde o humano o revisa como revisa código. As
pendências (os acompanhamentos que a verificação achou e os bloqueantes que
sobraram depois dos dois ciclos de correção) entram numa seção própria, que o
orquestrador reescreve a cada verificação.

O documento sempre se grava com as quebras de linha normalizadas (LF), e só
quando o texto normalizado muda: a pendência que traz a saída de um runner do
Windows (CRLF) fazia o texto lido, que o Python já normaliza, parecer
diferente do gravado; o orquestrador regravava os mesmos bytes, o git não via
mudança, e o commit falhava em toda rodada.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.saidas import Plano

PASTA_DOS_DOCUMENTOS: str = "docs/goals"
TITULO_DAS_PENDENCIAS: str = "## Pendencias"
TITULO_DO_ACEITE: str = "## Testes de aceite"
TITULO_DOS_RETIRADOS: str = "## Criterios retirados pelo humano"
TITULO_DAS_DECISOES_DO_AGENTE: str = "## Decisoes do agente (para o humano revisar)"


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


def com_retirados(documento: str, linhas: Sequence[str]) -> str:
    """O documento com a seção dos critérios retirados pelo humano logo antes das pendências (reescrita, se já havia)."""
    return com_secao(documento, TITULO_DOS_RETIRADOS, linhas)


def com_secao(documento: str, titulo: str, linhas: Sequence[str]) -> str:
    """O documento com a seção dada (reescrita, se já havia) logo antes das pendências, e as outras seções como estavam."""
    corpo, separador, resto = documento.partition(f"\n{TITULO_DAS_PENDENCIAS}\n")
    antes, _, depois = corpo.partition(f"\n{titulo}\n")
    seguinte = depois.find("\n## ")
    sobra = depois[seguinte:] if depois and seguinte >= 0 else ""
    corpo = (antes + sobra).rstrip("\n")
    secao = "\n".join([titulo, "", *linhas])
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


def normalizar_quebras(texto: str) -> str:
    """O texto com toda quebra de linha (CRLF, CR) como LF."""
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def gravar_se_mudou(caminho: Path, conteudo: str) -> bool:
    """Grava o texto com as quebras normalizadas, só quando ele difere do que está no arquivo; diz se gravou."""
    novo = normalizar_quebras(conteudo)
    if caminho.is_file() and normalizar_quebras(caminho.read_text(encoding="utf-8")) == novo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(novo, encoding="utf-8", newline="\n")
    return True


def escrever_documento(area: Path, slug: str, conteudo: str) -> Path:
    """Grava o documento na área do Goal, se ele mudou, e devolve o caminho."""
    caminho = area / caminho_do_documento(slug)
    gravar_se_mudou(caminho, conteudo)
    return caminho
