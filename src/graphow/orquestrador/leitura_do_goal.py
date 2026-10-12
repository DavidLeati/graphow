"""O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações.

É daqui que o laço decide o próximo passo a cada chamada, e é por isso que ele
retoma: nada do que importa fica só na memória do processo. A fila é simples e
calculada aqui: fatia pendente ou interrompida em andamento, com as
dependências concluídas e sem dúvida aberta, na ordem do plano.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusQuestion, TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.projection.graph_view import GrafoView

STATUS_NA_FILA: frozenset[str] = frozenset({m.STATUS_PENDENTE, m.STATUS_EM_ANDAMENTO})


@dataclass(frozen=True)
class DuvidaRegistrada:
    """Uma Question que o orquestrador abriu para uma fatia, e o que o humano respondeu."""

    id: str
    pergunta: str
    status: str
    resposta: str

    @property
    def aberta(self) -> bool:
        """Ainda espera o humano."""
        return self.status == StatusQuestion.ABERTA.value


@dataclass(frozen=True)
class FatiaRegistrada:
    """Uma fatia do Goal como o livro-razão a guarda."""

    id: str
    codigo: str
    titulo: str
    status: str
    ordem: int
    propriedades: Mapping[str, Any]
    depende_de: tuple[str, ...] = ()
    duvidas: tuple[DuvidaRegistrada, ...] = ()

    def texto(self, chave: str) -> str:
        """Uma propriedade de texto da fatia."""
        return str(self.propriedades.get(chave) or "")

    def lista(self, chave: str) -> tuple[str, ...]:
        """Uma propriedade de lista de textos da fatia."""
        valor = self.propriedades.get(chave)
        return tuple(str(item) for item in valor) if isinstance(valor, list) else ()

    @property
    def tentativas(self) -> int:
        """Quantas sessões de executor a fatia já abriu, dúvidas inclusive."""
        valor = self.propriedades.get(m.CAMPO_TENTATIVAS)
        return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0

    @property
    def falhas(self) -> int:
        """Quantas tentativas falharam (a saída inválida, a suíte vermelha, a sessão interrompida); a dúvida não conta."""
        valor = self.propriedades.get(m.CAMPO_FALHAS)
        return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0

    @property
    def duvida_aberta(self) -> DuvidaRegistrada | None:
        """A dúvida que pausa a fatia, quando há."""
        return next((duvida for duvida in self.duvidas if duvida.aberta), None)


@dataclass(frozen=True)
class VerificacaoRegistrada:
    """Uma verificação do Goal: em que commit, com que veredito e o que achou."""

    id: str
    commit: str
    veredito: str
    ciclo: int
    propriedades: Mapping[str, Any]
    commit_do_codigo: str = ""

    @property
    def limpa(self) -> bool:
        """Sem bloqueante."""
        return self.veredito == m.VEREDITO_LIMPO

    def lista(self, chave: str) -> list[dict[str, Any]]:
        """Os bloqueantes ou os acompanhamentos gravados."""
        valor = self.propriedades.get(chave)
        return [dict(item) for item in valor if isinstance(item, Mapping)] if isinstance(valor, list) else []


@dataclass(frozen=True)
class EstadoDoGoal:
    """Tudo o que o laço lê do Goal para decidir o passo seguinte."""

    id_goal: str
    rotulo: str
    status: str
    propriedades: Mapping[str, Any]
    fatias: tuple[FatiaRegistrada, ...] = ()
    verificacoes: tuple[VerificacaoRegistrada, ...] = ()
    plano_aprovado: bool = False

    @property
    def configuracao(self) -> m.ConfiguracaoDoGoal | None:
        """A configuração do laço, quando o orquestrador já conduz o Goal."""
        dados = self.propriedades.get(m.CAMPO_ORQUESTRACAO)
        return m.ConfiguracaoDoGoal.de_json(dados) if isinstance(dados, Mapping) else None

    @property
    def plano(self) -> Mapping[str, Any] | None:
        """O plano gravado, quando já há."""
        dados = self.propriedades.get(m.CAMPO_PLANO)
        return dados if isinstance(dados, Mapping) else None

    @property
    def fechado(self) -> bool:
        """O Goal já fechou."""
        return self.status == m.STATUS_CONCLUIDO

    @property
    def ciclos_de_correcao(self) -> int:
        """Quantos ciclos de correção a verificação já abriu."""
        valor = self.propriedades.get(m.CAMPO_CICLOS)
        return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0

    @property
    def pendencias(self) -> list[dict[str, Any]]:
        """As pendências gravadas no Goal."""
        valor = self.propriedades.get(m.CAMPO_PENDENCIAS)
        return [dict(item) for item in valor if isinstance(item, Mapping)] if isinstance(valor, list) else []

    @property
    def ultima_verificacao(self) -> VerificacaoRegistrada | None:
        """A verificação mais recente."""
        return self.verificacoes[-1] if self.verificacoes else None

    def prontas(self) -> tuple[FatiaRegistrada, ...]:
        """As fatias que podem rodar agora, na ordem do plano."""
        concluidas = {fatia.id for fatia in self.fatias if fatia.status == m.STATUS_CONCLUIDO}
        return tuple(
            fatia for fatia in self.fatias
            if fatia.status in STATUS_NA_FILA and set(fatia.depende_de) <= concluidas and fatia.duvida_aberta is None
        )

    def pausadas(self) -> tuple[FatiaRegistrada, ...]:
        """As fatias paradas numa dúvida aberta."""
        return tuple(fatia for fatia in self.fatias if fatia.duvida_aberta is not None)

    def bloqueadas(self) -> tuple[FatiaRegistrada, ...]:
        """As fatias que viraram pendência depois da segunda falha."""
        return tuple(fatia for fatia in self.fatias if fatia.status == m.STATUS_BLOQUEADO)


def ler_estado(view: GrafoView, id_goal: str) -> EstadoDoGoal | None:
    """O estado do Goal no grafo; None quando o Goal não existe."""
    goal = view.obter_no(id_goal)
    if goal is None or goal.tipo != TipoNo.GOAL:
        return None
    return EstadoDoGoal(
        id_goal=id_goal,
        rotulo=goal.rotulo,
        status=str(goal.obter_propriedade(m.CAMPO_STATUS) or ""),
        propriedades=goal.propriedades,
        fatias=_fatias(view, id_goal),
        verificacoes=_verificacoes(view, id_goal),
        plano_aprovado=_plano_aprovado_pelo_humano(goal),
    )


def _plano_aprovado_pelo_humano(goal: NoGrafo) -> bool:
    """O portão do plano do orquestrador: a aprovação que o humano gravou no Goal."""
    aprovacao = goal.obter_propriedade(m.CAMPO_APROVACAO_DO_PLANO)
    return isinstance(aprovacao, Mapping) and aprovacao.get("papel") == PapelAutor.HUMANO.value


def _fatias(view: GrafoView, id_goal: str) -> tuple[FatiaRegistrada, ...]:
    """As Tasks do orquestrador sob o Goal, na ordem do plano."""
    tarefas = [view.obter_no(a.destino_id) for a in view.obter_arestas_saida(id_goal, TipoAresta.DECOMPOE)]
    do_orquestrador = [no for no in tarefas if no is not None and no.tipo == TipoNo.TASK and no.obter_propriedade(m.CAMPO_FATIA)]
    fatias = [_fatia(view, no) for no in do_orquestrador]
    return tuple(sorted(fatias, key=lambda fatia: (fatia.ordem, fatia.id)))


def _fatia(view: GrafoView, no: NoGrafo) -> FatiaRegistrada:
    """A Task como fatia, com as dependências e as dúvidas."""
    ordem = no.obter_propriedade(m.CAMPO_ORDEM)
    return FatiaRegistrada(
        id=no.id,
        codigo=str(no.obter_propriedade(m.CAMPO_FATIA)),
        titulo=no.rotulo,
        status=str(no.obter_propriedade(m.CAMPO_STATUS) or m.STATUS_PENDENTE),
        ordem=ordem if isinstance(ordem, int) else 0,
        propriedades=no.propriedades,
        depende_de=tuple(sorted(a.destino_id for a in view.obter_arestas_saida(no.id, TipoAresta.DEPENDE_DE))),
        duvidas=_duvidas(view, no.id),
    )


def _duvidas(view: GrafoView, id_task: str) -> tuple[DuvidaRegistrada, ...]:
    """As Questions que bloqueiam a fatia, na ordem em que nasceram."""
    questoes = [view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(id_task, TipoAresta.BLOQUEIA)]
    validas = sorted((q for q in questoes if q is not None), key=lambda q: (q.ordem.seq_criacao, q.id))
    return tuple(
        DuvidaRegistrada(
            id=q.id,
            pergunta=str(q.obter_propriedade(m.CAMPO_PERGUNTA) or q.rotulo),
            status=str(q.obter_propriedade("status") or StatusQuestion.ABERTA.value),
            resposta=str(q.obter_propriedade(m.CAMPO_RESPOSTA) or ""),
        )
        for q in validas
    )


def _verificacoes(view: GrafoView, id_goal: str) -> tuple[VerificacaoRegistrada, ...]:
    """As Evidence de verificação ligadas ao Goal, da mais antiga à mais nova."""
    evidencias = [view.obter_no(a.origem_id) for a in view.obter_arestas_entrada(id_goal, TipoAresta.DERIVA_DE)]
    do_goal = [e for e in evidencias if e is not None and e.obter_propriedade("acao") == m.ACAO_DA_VERIFICACAO]
    ordenadas = sorted(do_goal, key=lambda e: (e.ordem.seq_criacao, e.id))
    return tuple(
        VerificacaoRegistrada(
            id=e.id,
            commit=str(e.obter_propriedade(m.CAMPO_COMMIT) or ""),
            veredito=str(e.obter_propriedade(m.CAMPO_VEREDITO) or ""),
            ciclo=int(e.obter_propriedade(m.CAMPO_CICLO) or 0),
            propriedades=e.propriedades,
            commit_do_codigo=str(e.obter_propriedade(m.CAMPO_COMMIT_DO_CODIGO) or ""),
        )
        for e in ordenadas
    )


def setor_do_goal(view: GrafoView, id_goal: str) -> str:
    """O Setor que contém a Sessao que produziu o Goal; vazio quando não há."""
    for producao in view.obter_arestas_entrada(id_goal, TipoAresta.PRODUZ):
        contencoes = view.obter_arestas_entrada(producao.origem_id, TipoAresta.CONTEM)
        if contencoes:
            return contencoes[0].origem_id
    return ""
