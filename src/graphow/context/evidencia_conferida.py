"""A Evidence na vista com a conferência dela na ponta, logo depois do id.

A vista lista a Evidence como memória do trabalho, e o agente a lia como fato
vigente mesmo quando o arquivo que ela afirma já tinha mudado. Agora a linha
da Evidence sobre código leva o estado da conferência
(orquestrador/conferencia_na_leitura.py): `desatualizada (mudaram: ...)`,
`sem ancora: <motivo>`, `nao conferida: <motivo>` (sem repositório à mão, que
é o caso da Evidence dos agentes do MCP) ou `vigente`. O motivo diz se ela foi
gravada sem commit, se o objeto não existe mais ou se o clone do Goal foi
removido. A Evidence que não fala de código segue sem marca. A marca vem antes
do rótulo, como o aviso de conteúdo não confiável: o rótulo é de quem escreveu
e não a empurra para o fim da linha.
"""

from collections.abc import Callable, Sequence

from graphow.context.secoes import PrioridadeRetencao, SecaoContexto, em_uma_linha, formatar_no_em_linha
from graphow.core.models import NoGrafo
from graphow.orquestrador.conferencia_da_evidencia import ConferenciaDaEvidencia
from graphow.orquestrador.conferencia_na_leitura import marca_da_conferencia

Conferir = Callable[[NoGrafo], ConferenciaDaEvidencia | None]


def formatar_evidencia_em_linha(no: NoGrafo, conferencia: ConferenciaDaEvidencia | None) -> str:
    """A linha do nó, com o estado da conferência (e o motivo, quando há) entre colchetes depois do id."""
    linha = formatar_no_em_linha(no)
    if conferencia is None:
        return linha
    cabeca = f"- [{em_uma_linha(no.id)}]"
    return f"{cabeca} [{em_uma_linha(marca_da_conferencia(conferencia))}]{linha.removeprefix(cabeca)}"


def montar_secao_de_evidencias(
    titulo: str, nos: Sequence[NoGrafo], ordens: tuple[int, PrioridadeRetencao], *, conferir: Conferir
) -> SecaoContexto:
    """A seção de Evidence, cada uma conferida na hora da leitura."""
    ordem_exibicao, prioridade = ordens
    return SecaoContexto(
        titulo=titulo,
        linhas=tuple(formatar_evidencia_em_linha(no, conferir(no)) for no in nos),
        ordem_exibicao=ordem_exibicao,
        prioridade_retencao=prioridade,
        ids_incluidos=tuple(no.id for no in nos),
    )
