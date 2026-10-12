"""O estado do laço lido do livro-razão: o Goal, as fatias, as dúvidas e as verificações.

É daqui que o laço decide o próximo passo a cada chamada, e é por isso que ele
retoma: nada do que importa fica só na memória do processo. A fila é simples e
calculada aqui: fatia pendente ou interrompida em andamento, com as
dependências concluídas e sem dúvida aberta, na ordem do plano.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from graphow.core import aceite as a
from graphow.core.models import NoGrafo
from graphow.core.types import PapelAutor, StatusQuestion, TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.leitura_das_verificacoes import (
    AchadoRegistrado,
    VerificacaoRegistrada,
    achados_das_revisoes,
    verificacoes_do_goal,
)
from graphow.orquestrador.pedidos_do_humano import (
    PEDIDO_MAIS_CICLOS,
    PEDIDO_REFAZER_ACEITE,
    DecisaoDoAgente,
    PedidoDoHumano,
    ler_decisoes_do_agente,
    ler_pedidos,
)
from graphow.projection.graph_view import GrafoView

# O teste de aceite errado que o executor do modo autônomo apontou (orquestrador/decisoes_do_agente.py).
CAMPO_TESTE_ERRADO: str = "teste_errado"

STATUS_NA_FILA: frozenset[str] = frozenset({m.STATUS_PENDENTE, m.STATUS_EM_ANDAMENTO})


@dataclass(frozen=True)
class DuvidaRegistrada:
    """Uma Question que o orquestrador abriu para uma fatia, e o que o humano respondeu."""

    id: str
    pergunta: str
    status: str
    resposta: str
    criterio_do_teste: str = ""
    decisao_do_teste: str = ""

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
    achados_de_revisao: tuple[AchadoRegistrado, ...] = ()

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
class MarcoRegistrado:
    """Um marco do plano gravado: as fatias dele, os critérios que a verificação dele julga e se é o final."""

    id: str
    titulo: str
    fatias: tuple[str, ...]
    criterios: tuple[str, ...]
    final: bool

    def contem(self, fatia: FatiaRegistrada, primeiro: bool) -> bool:
        """A fatia é deste marco; a fatia de antes dos marcos é do primeiro."""
        marco = fatia.texto(m.CAMPO_MARCO)
        return marco == self.id or (not marco and primeiro)


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
    pedidos: tuple[PedidoDoHumano, ...] = ()
    decisoes_do_agente: tuple[DecisaoDoAgente, ...] = ()

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
    def aceite(self) -> Mapping[str, Any] | None:
        """Os testes de aceite gravados (commit, comando, arquivos e o aceite de cada critério), quando já há."""
        dados = self.propriedades.get(m.CAMPO_ACEITE)
        return dados if isinstance(dados, Mapping) else None

    def arquivos_protegidos(self) -> tuple[str, ...]:
        """Os arquivos dos testes de aceite: o executor não os toca, e a suíte do plano roda sem eles."""
        arquivos = (self.aceite or {}).get("arquivos")
        return tuple(str(arquivo) for arquivo in arquivos) if isinstance(arquivos, list) else ()

    @property
    def fechado(self) -> bool:
        """O Goal já fechou."""
        return self.status == m.STATUS_CONCLUIDO

    @property
    def cancelado(self) -> bool:
        """O humano cancelou o Goal."""
        return self.status == a.STATUS_CANCELADO

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

    def achado(self, id_achado: str) -> AchadoRegistrado | None:
        """O nó Achado de qualquer verificação do Goal, pelo id."""
        return next((achado for v in self.verificacoes for achado in v.achados if achado.id == id_achado), None)

    @property
    def ultima_verificacao(self) -> VerificacaoRegistrada | None:
        """A verificação mais recente."""
        return self.verificacoes[-1] if self.verificacoes else None

    def marcos(self) -> tuple[MarcoRegistrado, ...]:
        """Os marcos do plano, em ordem; o plano sem marcos (o de antes da fase 2) é um marco só, o final."""
        plano = self.plano or {}
        gravados = [item for item in plano.get("marcos", []) if isinstance(item, Mapping)]
        todos = tuple(str(c["id"]) for c in plano.get("criterios", []))
        if not gravados:
            return (MarcoRegistrado("M1", "O Goal inteiro", tuple(str(f) for f in plano.get("fatias", [])), todos, True),)
        return tuple(
            MarcoRegistrado(str(item["id"]), str(item.get("titulo", "")), tuple(str(f) for f in item.get("fatias", [])),
                            todos if posicao == len(gravados) - 1 else tuple(str(c) for c in item.get("criterios", [])),
                            posicao == len(gravados) - 1)
            for posicao, item in enumerate(gravados)
        )

    def fatias_do_marco(self, marco: MarcoRegistrado) -> tuple[FatiaRegistrada, ...]:
        """As fatias do marco, as de correção inclusive."""
        primeiro = self.marcos()[0].id == marco.id
        return tuple(fatia for fatia in self.fatias if marco.contem(fatia, primeiro))

    def verificacoes_do_marco(self, marco: MarcoRegistrado) -> tuple[VerificacaoRegistrada, ...]:
        """As verificações do marco, da mais antiga à mais nova."""
        return tuple(verificacao for verificacao in self.verificacoes if verificacao.marco == marco.id)

    def marco_atual(self) -> MarcoRegistrado:
        """O primeiro marco sem verificação limpa que ainda tem o que fazer; com todos encerrados, o final.

        O marco intermediário que gastou os ciclos de correção com bloqueante
        aberto não para o Goal: os bloqueantes seguem abertos, o laço vai aos
        marcos seguintes, e a verificação final os cobra de novo.
        """
        marcos = self.marcos()
        encerrados = (any(v.limpa for v in self.verificacoes_do_marco(marco)) or self.marco_esgotado(marco) for marco in marcos)
        return next((marco for marco, encerrado in zip(marcos, encerrados) if not encerrado), marcos[-1])

    def limite_de_ciclos(self, marco: MarcoRegistrado) -> int:
        """Quantos ciclos de correção o marco tem: os dois de todo marco, mais os que o humano deu a ele."""
        dados = sum(p.ciclos for p in self.pedidos if p.acao == PEDIDO_MAIS_CICLOS and p.alvo == marco.id)
        return m.MAXIMO_DE_CICLOS_DE_CORRECAO + dados

    def pedidos_pendentes(self, acao: str) -> tuple[PedidoDoHumano, ...]:
        """Os pedidos com a ação dada que o laço ainda não atendeu: os do humano e os de refazer um teste de aceite.

        A dúvida do executor que diz que um teste de aceite está errado só pede
        o refazer quando o humano responde que sim (`refazer`), com a resposta
        como motivo; no modo autônomo, o `teste_errado` do executor pede o
        refazer sozinho (orquestrador/decisoes_do_agente.py).
        """
        atendidos = self.propriedades.get(a.CAMPO_PEDIDOS_ATENDIDOS)
        feitos = set(atendidos) if isinstance(atendidos, list) else set()
        duvidas = (PedidoDoHumano(d.id, PEDIDO_REFAZER_ACEITE, d.resposta, alvo=d.criterio_do_teste, fatia=f.id)
                   for f in self.fatias for d in f.duvidas if d.criterio_do_teste and not d.aberta and d.decisao_do_teste == "refazer")
        automaticos = (PedidoDoHumano(str(t["id"]), PEDIDO_REFAZER_ACEITE, f"o executor da fatia {f.codigo} diz que o teste de "
                                      f"{t['criterio']} esta errado: {t.get('argumento', '')}", alvo=str(t["criterio"]), fatia=f.id)
                       for f in self.fatias if isinstance(t := f.propriedades.get(CAMPO_TESTE_ERRADO), Mapping) and t.get("id"))
        candidatos = (*self.pedidos, *duvidas, *automaticos)
        return tuple(pedido for pedido in candidatos if pedido.acao == acao and pedido.id not in feitos)

    def marco_esgotado(self, marco: MarcoRegistrado) -> bool:
        """O marco intermediário gastou os ciclos, e a verificação depois do último ainda tem bloqueante: ele não tem o que fazer."""
        verificacoes = self.verificacoes_do_marco(marco)
        if marco.final or not verificacoes or any(v.limpa for v in verificacoes):
            return False
        corrigida = any(fatia.texto(m.CAMPO_CORRIGE) == verificacoes[-1].id for fatia in self.fatias)
        return self.ciclos_do_marco(marco) >= self.limite_de_ciclos(marco) and not corrigida

    def bloqueantes_de_outros_marcos(self, marco: MarcoRegistrado) -> tuple[AchadoRegistrado, ...]:
        """Os bloqueantes ainda abertos que as verificações dos outros marcos deixaram: a final os cobra de novo."""
        return tuple(achado for v in self.verificacoes if v.marco != marco.id for achado in v.bloqueantes()
                     if achado.estado == a.ESTADO_ABERTO)

    def corrigidos(self, marco: MarcoRegistrado) -> tuple[str, ...]:
        """Os Achados que uma correção entregou e que a verificação limpa do marco resolve; na final, os do Goal inteiro."""
        verificacoes = self.verificacoes if marco.final else self.verificacoes_do_marco(marco)
        return tuple(achado.id for v in verificacoes for achado in v.achados if achado.estado == a.ESTADO_CORRIGIDO)

    def ciclos_do_marco(self, marco: MarcoRegistrado) -> int:
        """Quantos ciclos de correção o marco já abriu: as verificações dele de onde nasceram fatias de correção."""
        return len({fatia.texto(m.CAMPO_CORRIGE) for fatia in self.fatias_do_marco(marco) if fatia.texto(m.CAMPO_CORRIGE)})

    def prontas(self, marco: MarcoRegistrado | None = None) -> tuple[FatiaRegistrada, ...]:
        """As fatias que podem rodar agora, na ordem do plano; com o marco dado, só as dele."""
        concluidas = {fatia.id for fatia in self.fatias if fatia.status == m.STATUS_CONCLUIDO}
        candidatas = self.fatias if marco is None else self.fatias_do_marco(marco)
        return tuple(
            fatia for fatia in candidatas
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
        verificacoes=verificacoes_do_goal(view, id_goal),
        plano_aprovado=_plano_aprovado_pelo_humano(goal),
        pedidos=ler_pedidos(view, id_goal),
        decisoes_do_agente=ler_decisoes_do_agente(view, id_goal),
    )


def _plano_aprovado_pelo_humano(goal: NoGrafo) -> bool:
    """O portão do plano do orquestrador: a aprovação que o humano gravou no Goal, dos testes de aceite que estão nele.

    O humano aprova junto o plano e os testes de aceite. A aprovação de um
    commit que não é o dos testes de aceite gravados (a do plano de antes da
    fase 2, que não tinha testes) não vale para eles.
    """
    aprovacao = goal.obter_propriedade(m.CAMPO_APROVACAO_DO_PLANO)
    aceite = goal.obter_propriedade(m.CAMPO_ACEITE)
    alvo = aceite.get("commit") if isinstance(aceite, Mapping) else None
    humano = isinstance(aprovacao, Mapping) and aprovacao.get("papel") == PapelAutor.HUMANO.value
    return humano and (alvo is None or aprovacao.get("documento") == alvo)


def _fatias(view: GrafoView, id_goal: str) -> tuple[FatiaRegistrada, ...]:
    """As Tasks do orquestrador sob o Goal, na ordem do plano."""
    tarefas = [view.obter_no(a.destino_id) for a in view.obter_arestas_saida(id_goal, TipoAresta.DECOMPOE)]
    do_orquestrador = [no for no in tarefas if no is not None and no.tipo == TipoNo.TASK and no.obter_propriedade(m.CAMPO_FATIA)
                       and not no.obter_propriedade(m.CAMPO_SUBSTITUIDA)]
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
        achados_de_revisao=achados_das_revisoes(view, no.id),
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
            criterio_do_teste=str(q.obter_propriedade(m.CAMPO_CRITERIO_DO_TESTE) or ""),
            decisao_do_teste=_decisao_do_teste(q),
        )
        for q in validas
    )


def _decisao_do_teste(questao: NoGrafo) -> str:
    """O que o humano decidiu sobre o teste dito errado: `refazer` ou `manter`, pela propriedade ou pela primeira palavra da resposta."""
    gravada = str(questao.obter_propriedade("decisao_do_teste") or "").strip().lower()
    palavras = str(questao.obter_propriedade(m.CAMPO_RESPOSTA) or "").strip().lower().split()
    primeira = palavras[0].strip(":.,;-") if palavras else ""
    return gravada if gravada in ("refazer", "manter") else primeira if primeira in ("refazer", "manter") else ""


def setor_do_goal(view: GrafoView, id_goal: str) -> str:
    """O Setor que contém a Sessao que produziu o Goal; vazio quando não há."""
    for producao in view.obter_arestas_entrada(id_goal, TipoAresta.PRODUZ):
        contencoes = view.obter_arestas_entrada(producao.origem_id, TipoAresta.CONTEM)
        if contencoes:
            return contencoes[0].origem_id
    return ""
