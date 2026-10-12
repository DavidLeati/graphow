"""As verificações do Goal e os nós Achado delas e das revisões de risco, como o laço os lê do livro-razão.

A verificação é a Evidence que deriva do Goal com a ação da verificação; o
Achado é o nó que deriva dela, ou da Evidence da revisão de risco de uma
fatia, com a gravidade que o código decidiu e o estado (aberto, corrigido,
resolvido, descartado; o acompanhamento, pendente). A ordem é a do log. Só
conta o que nasceu de um lote do orquestrador: a verificação ou o Achado que
outro papel gravasse não é do laço, e ele não o lê.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.projection.graph_view import GrafoView


def do_orquestrador(no: NoGrafo | None) -> bool:
    """O nó nasceu de um lote do orquestrador: o laço só lê a verificação, o Achado e a revisão que ele mesmo gravou."""
    return no is not None and no.proveniencia.papel == PapelAutor.ORQUESTRADOR.value


@dataclass(frozen=True)
class AchadoRegistrado:
    """Um nó Achado de uma verificação do Goal: a gravidade que o código decidiu, o estado e o que ele é."""

    id: str
    verificacao: str
    gravidade: str
    estado: str
    propriedades: Mapping[str, Any]

    def texto(self, chave: str) -> str:
        """Uma propriedade de texto do achado."""
        return str(self.propriedades.get(chave) or "")

    def lista(self, chave: str) -> tuple[str, ...]:
        """Uma propriedade de lista de textos do achado."""
        valor = self.propriedades.get(chave)
        return tuple(str(item) for item in valor) if isinstance(valor, list) else ()

    @property
    def bloqueante(self) -> bool:
        """O código o decidiu bloqueante."""
        return self.gravidade == a.GRAVIDADE_BLOQUEANTE


@dataclass(frozen=True)
class VerificacaoRegistrada:
    """Uma verificação do Goal: em que commit, com que veredito e o que achou."""

    id: str
    commit: str
    veredito: str
    ciclo: int
    propriedades: Mapping[str, Any]
    commit_do_codigo: str = ""
    achados: tuple[AchadoRegistrado, ...] = ()
    marco: str = ""
    reprovados: tuple[str, ...] = ()

    def bloqueantes(self) -> tuple[AchadoRegistrado, ...]:
        """Os nós Achado bloqueantes desta verificação."""
        return tuple(achado for achado in self.achados if achado.bloqueante)

    def bloqueantes_abertos(self) -> tuple[AchadoRegistrado, ...]:
        """Os bloqueantes ainda não encerrados: o resolvido e o que o humano descartou não contam."""
        return tuple(achado for achado in self.bloqueantes() if achado.estado not in a.ESTADOS_QUE_ENCERRAM_O_BLOQUEANTE)

    @property
    def limpa(self) -> bool:
        """Sem bloqueante, ou com todo bloqueante dela encerrado (resolvido, ou descartado pelo humano), e sem critério reprovado.

        O laço lê o estado do Achado, e não o veredito velho da Evidence: o
        bloqueante que o humano descartou não segura mais o marco. Mas o
        descarte não aprova critério: o critério que ela julgou `nao_atende` ou
        `parcial` (e que o humano não retirou) a deixa suja.
        """
        encerrada = self.veredito == m.VEREDITO_LIMPO or (bool(self.bloqueantes()) and not self.bloqueantes_abertos())
        return encerrada and not self.reprovados




def verificacoes_do_goal(view: GrafoView, id_goal: str) -> tuple[VerificacaoRegistrada, ...]:
    """As Evidence de verificação ligadas ao Goal, da mais antiga à mais nova."""
    evidencias = [view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(id_goal, TipoAresta.DERIVA_DE)]
    do_goal = [e for e in evidencias if do_orquestrador(e) and e.obter_propriedade("acao") == m.ACAO_DA_VERIFICACAO]
    ordenadas = sorted(do_goal, key=lambda e: (e.ordem.seq_criacao, e.id))
    ativos = criterios_ativos(view, id_goal)
    return tuple(
        VerificacaoRegistrada(
            id=e.id,
            commit=str(e.obter_propriedade(m.CAMPO_COMMIT) or ""),
            veredito=str(e.obter_propriedade(m.CAMPO_VEREDITO) or ""),
            ciclo=int(e.obter_propriedade(m.CAMPO_CICLO) or 0),
            propriedades=e.propriedades,
            commit_do_codigo=str(e.obter_propriedade(m.CAMPO_COMMIT_DO_CODIGO) or ""),
            achados=achados_da_evidencia(view, e.id),
            marco=str(e.obter_propriedade(m.CAMPO_MARCO) or ""),
            reprovados=_reprovados(e.obter_propriedade(m.CAMPO_PARECERES), ativos),
        )
        for e in ordenadas
    )


def criterios_ativos(view: GrafoView, id_goal: str) -> frozenset[str]:
    """Os nós Criterio que escopam o Goal e que o humano não retirou (por uma Decision dele)."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_goal, TipoAresta.ESCOPA))
    return frozenset(no.id for no in origens if no is not None and no.tipo == TipoNo.CRITERIO and not retirado_pelo_humano(view, no))


def retirado_pelo_humano(view: GrafoView, criterio: NoGrafo) -> bool:
    """O Criterio traz a retirada por uma Decision que o humano gravou."""
    retirada = criterio.obter_propriedade(a.CAMPO_RETIRADO)
    decisao = view.obter_no(str(retirada.get("decisao", ""))) if isinstance(retirada, Mapping) else None
    return decisao is not None and decisao.tipo == TipoNo.DECISION and decisao.proveniencia.papel == PapelAutor.HUMANO.value


def _reprovados(pareceres: object, ativos: frozenset[str]) -> tuple[str, ...]:
    """Os códigos dos critérios ativos que o parecer não deu como `atende`."""
    itens = [p for p in pareceres if isinstance(p, Mapping)] if isinstance(pareceres, list) else []
    return tuple(str(p.get("id")) for p in itens if str(p.get("no", "")) in ativos and p.get("veredito") != a.VEREDITO_QUE_ATENDE)


def achados_da_evidencia(view: GrafoView, id_evidencia: str) -> tuple[AchadoRegistrado, ...]:
    """Os nós Achado que derivam da verificação, na ordem dos ids."""
    origens = (view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_evidencia, TipoAresta.DERIVA_DE))
    nos = sorted((no for no in origens if do_orquestrador(no) and no.tipo == TipoNo.ACHADO), key=lambda no: (no.ordem.seq_criacao, no.id))
    return tuple(
        AchadoRegistrado(no.id, id_evidencia, str(no.obter_propriedade(a.CAMPO_GRAVIDADE) or ""),
                         str(no.obter_propriedade(a.CAMPO_ESTADO) or ""), no.propriedades)
        for no in nos
    )


def achados_das_revisoes(view: GrafoView, id_task: str) -> tuple[AchadoRegistrado, ...]:
    """Os nós Achado das revisões de risco da fatia, da revisão mais antiga à mais nova."""
    revisoes = [view.obter_no(aresta.origem_id) for aresta in view.obter_arestas_entrada(id_task, TipoAresta.DERIVA_DE)]
    do_risco = sorted((r for r in revisoes if do_orquestrador(r) and r.obter_propriedade("acao") == a.ACAO_DA_REVISAO_DE_RISCO),
                      key=lambda r: (r.ordem.seq_criacao, r.id))
    return tuple(achado for revisao in do_risco for achado in achados_da_evidencia(view, revisao.id))
