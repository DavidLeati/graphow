"""A revisão por fatia, só na fatia de risco: uma sessão nova julga o diff contra os critérios dela antes do commit.

Na auditoria, as 20 revisões por Task aprovaram de primeira: conferiam o que o
condutor escreveu, com os testes do executor. A prova passou a ser o aceite,
escrito antes por outra sessão, e o verificador de cada marco. A revisão por
fatia sobra onde o erro não seria pego por eles: a fatia que o planejador
marcou como risco (julgamento de domínio, mudança que atravessa partes) e a
que já falhou uma vez. Nas outras, não há revisão.

Com a suíte verde, antes do commit, uma sessão nova do revisor lê a mudança,
que está na área fora de commit, e devolve `aprovado` ou `rejeitado` com os
problemas. O veredito vira Evidence que deriva da fatia, e cada problema da
rejeição, um nó Achado que deriva dela, com a gravidade que o código decide
(o que toca critério ou decisão é bloqueante), e não uma Note. A rejeição é
uma falha da tentativa, com os problemas no briefing da seguinte; a revisão
que aprova a fatia depois resolve os bloqueantes que ela abriu. O revisor não
muda a entrega: o orquestrador fotografa a mudança antes da sessão e, se ela
não for a mesma depois, devolve a área ao que o executor deixou.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_revisor
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.esquemas import PAPEL_REVISOR
from graphow.orquestrador.git_do_goal import GitDoGoal, descartar_mudancas
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta, propriedade
from graphow.orquestrador.saida_do_verificador import ORIGEM_DA_REVISAO, Achado
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.verificacao_do_marco import nos_do_plano

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


def revisar_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao) -> "str | Parada | RejeicaoDaRevisao":
    """A revisão da mudança fora de commit: vazio quando aprovada, os problemas quando rejeitada, ou a parada."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    foto = _fotografar(contexto.area)
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_REVISOR, id_goal=contexto.id_goal, pasta=contexto.area, fatia=pedido.fatia.id, tentativa=pedido.tentativa,
            briefing=briefing_do_revisor(estado, pedido.fatia, contexto.git.caminhos_mudados(), motivo=pedido.motivo),
            conferir=_conferir, orcamento_restante_usd=contexto.restante(),
        )
    )
    desfeito = _restaurar(contexto, foto, pedido)
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA,
                      f"A revisao da fatia de risco {pedido.fatia.codigo} nao conferiu: " + "; ".join(resposta.problemas))
    dados = {**resposta.dados, "motivo": pedido.motivo, "observacao": desfeito}
    contexto.livro.registrar_revisao(pedido.fatia.id, pedido.tentativa, dados=dados,
                                     achados=operacoes_dos_achados(contexto.livro, estado, pedido, dados=dados))
    return "" if resposta.dados.get("veredito") == VEREDITO_APROVADO else RejeicaoDaRevisao(_problemas(resposta.dados))


@dataclass(frozen=True)
class RejeicaoDaRevisao:
    """A revisão rejeitou a entrega: os problemas, para a tentativa seguinte; eles já estão nos Achados da revisão."""

    texto: str


def operacoes_dos_achados(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeRevisao, *,
                          dados: Mapping[str, Any]) -> list[ItemPatch]:
    """Na rejeição, cada problema vira nó Achado da revisão, com a gravidade do código; na aprovação, os de antes se resolvem.

    O Achado deriva da Evidence da revisão e fere o critério e a decisão que o
    problema toca, como o da verificação; o bloqueante nasce aberto e é o que a
    tentativa seguinte corrige. A revisão que aprova a fatia resolve os
    bloqueantes que as revisões anteriores dela abriram.
    """
    id_evidencia = m.id_da_revisao(pedido.fatia.id, pedido.tentativa)
    if dados.get("veredito") == VEREDITO_APROVADO:
        return [propriedade(id_achado, a.CAMPO_ESTADO, a.ESTADO_RESOLVIDO) for id_achado in _abertos_das_revisoes(pedido.fatia)]
    feriveis = _feriveis(livro, estado)
    operacoes: list[ItemPatch] = []
    for indice, item in enumerate((p for p in dados.get("problemas", []) if isinstance(p, Mapping)), start=1):
        achado = replace(Achado.de_json(item), origem=ORIGEM_DA_REVISAO)
        estado_inicial = a.ESTADO_ABERTO if achado.gravidade == a.GRAVIDADE_BLOQUEANTE else a.ESTADO_DO_ACOMPANHAMENTO
        id_achado = f"achado-{id_evidencia}-{indice}"
        propriedades = {**achado.em_json(), a.CAMPO_ESTADO: estado_inicial, "revisao": id_evidencia,
                        a.CAMPO_MARCO: pedido.fatia.texto(m.CAMPO_MARCO)}
        operacoes += livro.produzido(id_achado, TipoNo.ACHADO, f"[{achado.gravidade}] {achado.titulo}", propriedades=propriedades)
        operacoes.append(aresta(id_achado, id_evidencia, TipoAresta.DERIVA_DE))
        operacoes += [aresta(id_achado, feriveis[codigo], TipoAresta.FERE) for codigo in achado.toca if codigo in feriveis]
    return operacoes


def _feriveis(livro: LivroRazaoDoGoal, estado: EstadoDoGoal) -> dict[str, str]:
    """O nó de cada critério e decisão do plano que um Achado pode ferir (o Criterio e a Decision)."""
    view = livro.view()
    return {codigo: id_no for codigo, id_no in nos_do_plano(estado.plano or {}).items()
            if id_no and (no := view.obter_no(id_no)) is not None and no.tipo in (TipoNo.CRITERIO, TipoNo.DECISION)}


def _abertos_das_revisoes(fatia: FatiaRegistrada) -> list[str]:
    """Os Achados bloqueantes ainda abertos das revisões anteriores da fatia."""
    return [achado.id for achado in fatia.achados_de_revisao if achado.bloqueante and achado.estado == a.ESTADO_ABERTO]


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

