"""A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit.

Na auditoria, as 20 revisões por Task aprovaram de primeira: conferiam o que o
condutor escreveu, com os testes do executor. A prova passou a ser o aceite,
escrito antes por outra sessão, e o verificador de cada marco. A revisão por
fatia sobra onde o erro não seria pego por eles: a fatia que o planejador
marcou como risco (julgamento de domínio, mudança que atravessa partes) e a
que já falhou uma vez. Nas outras, não há revisão.

Com a suíte verde, antes do commit, uma sessão nova do revisor lê a mudança,
que está na área fora de commit, e devolve `aprovado` ou `rejeitado` com os
problemas. O veredito vira Evidence que deriva da fatia. A rejeição é uma
falha da tentativa, com os problemas no briefing da seguinte. O revisor não
muda a entrega: o orquestrador fotografa a mudança antes da sessão e, se ela
não for a mesma depois, devolve a área ao que o executor deixou.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_revisor
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.esquemas import PAPEL_REVISOR
from graphow.orquestrador.git_do_goal import GitDoGoal, descartar_mudancas
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel

VEREDITO_APROVADO: str = "aprovado"


def de_risco(fatia: FatiaRegistrada) -> str:
    """Por que a fatia é de risco; vazio quando não é e não tem revisão."""
    if fatia.propriedades.get(m.CAMPO_RISCO) is True:
        return "o planejador a marcou como risco: " + (fatia.texto(m.CAMPO_MOTIVO_DO_RISCO) or "sem motivo dito")
    return "uma tentativa anterior dela falhou" if fatia.falhas else ""


@dataclass(frozen=True)
class PedidoDeRevisao:
    """A fatia a revisar, a tentativa em curso e por que ela é de risco."""

    fatia: FatiaRegistrada
    tentativa: int
    motivo: str


def revisar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> str | Parada:
    """A revisão da mudança fora de commit: vazio quando aprovada, os problemas quando rejeitada, ou a parada."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    foto = _fotografar(contexto.area)
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_REVISOR, id_goal=contexto.id_goal, pasta=contexto.area, fatia=pedido.fatia.id, tentativa=pedido.tentativa,
            briefing=briefing_do_revisor(estado, pedido.fatia, contexto.git.caminhos_mudados()),
            conferir=_conferir, orcamento_restante_usd=contexto.restante(),
        )
    )
    desfeito = _restaurar(contexto, foto, pedido)
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA,
                      f"A revisao da fatia de risco {pedido.fatia.codigo} nao conferiu: " + "; ".join(resposta.problemas))
    contexto.livro.registrar_revisao(pedido.fatia.id, pedido.tentativa, dados={**resposta.dados, "motivo": pedido.motivo,
                                                                                "observacao": desfeito})
    return "" if resposta.dados.get("veredito") == VEREDITO_APROVADO else _problemas(resposta.dados)


def _conferir(dados: Mapping[str, Any]) -> tuple[str, ...]:
    """A rejeição diz os problemas."""
    sem_problema = dados.get("veredito") != VEREDITO_APROVADO and not dados.get("problemas")
    return ("veredito rejeitado sem nenhum problema em 'problemas'",) if sem_problema else ()


def _fotografar(area: Path) -> str:
    """A mudança fora de commit inteira, arquivos novos inclusive, como patch; a área fica como estava."""
    git = GitDoGoal(area)
    git.rodar("add", "-A")
    foto = git.rodar("diff", "--cached", "--binary", "HEAD")
    git.rodar("reset", "-q")
    return foto


def _restaurar(contexto: ContextoDoGoal, foto: str, pedido: PedidoDeRevisao) -> str:
    """A área volta à mudança que o executor deixou, se o revisor mexeu nela; diz o que desfez."""
    if _fotografar(contexto.area) == foto:
        return ""
    descartar_mudancas(contexto.area, contexto.patch(f"{pedido.fatia.id}-t{pedido.tentativa}-revisor"))
    if foto:
        arquivo = contexto.patch(f"{pedido.fatia.id}-t{pedido.tentativa}-antes-do-revisor")
        arquivo.write_text(foto, encoding="utf-8", newline="\n")
        GitDoGoal(contexto.area).rodar("apply", "--binary", str(arquivo))
    return "o revisor mexeu na area; ela voltou ao que o executor deixou"


def _problemas(dados: Mapping[str, Any]) -> str:
    """Os problemas da revisão que rejeitou, para o briefing da tentativa seguinte."""
    itens = [item for item in dados.get("problemas", []) if isinstance(item, Mapping)]
    linhas = [
        f"- {item.get('titulo', '')}: {item.get('descricao', '')} Prova: {item.get('prova', '')}"
        + (f" (local: {item['local']})" if item.get("local") else "")
        + (f" Toca: {', '.join(item.get('criterios', []))}" if item.get("criterios") else "")
        for item in itens
    ]
    return "a revisao da fatia de risco rejeitou a entrega: " + str(dados.get("resumo", "")) + "\n" + "\n".join(linhas)

