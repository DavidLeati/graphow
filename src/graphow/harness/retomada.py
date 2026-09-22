"""A vista de retomada: o que o hook de início imprime para o agente ler antes de trabalhar.

O ambiente injeta no contexto do agente o que o hook de SessionStart escreve na
saída padrão. Até aqui eram três linhas de recibo, e a memória ficava no banco
à espera de alguém chamar `ler_vista`; dezessete sessões passaram sem que
ninguém chamasse. A vista de retomada é curta e sempre igual na forma: onde a
sessão mora, os aprendizados que valem aqui, o que a sessão anterior deixou
(fechamento, condensação, ou a Task de condensar que ninguém pegou) e o
protocolo. É o que faz a memória chegar sem depender de skill instalada nem de
CLAUDE.md que fale dela.
"""

from collections import Counter
from dataclasses import dataclass

from graphow.context.fechamento import CAMPO_CORPO, localizar_condensacao
from graphow.context.memoria import (
    PedidoDeMemoria,
    formatar_aprendizado,
    montar_secao_de_aprendizados,
    substituto_promovido,
)
from graphow.context.protocolo import montar_protocolo
from graphow.core.models import NoGrafo
from graphow.core.types import StatusSessao, StatusTask, TipoAresta, TipoNo
from graphow.projection.fechamento import FechamentoDeSubarvore
from graphow.projection.graph_view import GrafoView
from graphow.reactive.condensacao import (
    eh_tarefa_de_condensacao,
    produzidos_pela_sessao,
    tem_condensacao_pendente,
    tem_trabalho_a_condensar,
)

TITULO_DA_VISTA: str = "Memoria do graphow para esta sessao"
TITULO_DOS_APRENDIZADOS: str = "### Aprendizados aplicaveis"
TITULO_DA_SESSAO_ANTERIOR: str = "### Sessao anterior"
TITULO_DA_SESSAO_RETOMADA: str = "### Esta sessao (retomada)"
LIMITE_DE_APRENDIZADOS: int = 12
LIMITE_DE_CARACTERES_DA_CONDENSACAO: int = 600
SEM_APRENDIZADOS: str = (
    "- nenhum aprendizado registrado para este projeto ainda: "
    "o que aprender aqui entra por `registrar_aprendizado`."
)
SEM_SESSAO_ANTERIOR: str = "- nenhuma sessao anterior neste Setor: esta e a primeira."
SEM_REGISTROS: str = "  sem registros alem da telemetria: a sessao nao deixou Evidence, Decision nem Note."


@dataclass(frozen=True)
class PedidoDeRetomada:
    """O que a vista precisa: a projeção, a sessão que abre e o Setor em que ela mora."""

    view: GrafoView
    id_sessao: str
    id_setor: str


def montar_vista_de_retomada(pedido: PedidoDeRetomada) -> tuple[str, ...]:
    """As linhas da vista, prontas para a saída padrão do hook; vazia se o Setor não existe."""
    setor = pedido.view.obter_no(pedido.id_setor)
    if setor is None:
        return ()
    return (
        f"## {TITULO_DA_VISTA}",
        _linha_de_onde(setor, pedido),
        *_linhas_de_aprendizados(setor, pedido.view),
        *_linhas_da_sessao_anterior(pedido),
        *_linhas_da_sessao_retomada(pedido),
        "",
        *montar_protocolo(id_sessao=pedido.id_sessao),
    )


def _linha_de_onde(setor: NoGrafo, pedido: PedidoDeRetomada) -> str:
    """Onde a sessão mora, com os ids que as ferramentas pedem."""
    pais = pedido.view.obter_arestas_entrada(setor.id, TipoAresta.CONTEM)
    projeto = pedido.view.obter_no(pais[0].origem_id) if pais else None
    onde = f"Projeto {projeto.rotulo} ({projeto.id})" if projeto is not None else "Sem projeto"
    return f"{onde} | Setor {setor.rotulo} ({setor.id}) | Sessao {pedido.id_sessao}"


def _linhas_de_aprendizados(setor: NoGrafo, view: GrafoView) -> tuple[str, ...]:
    """Os promovidos que alcançam o Setor e os nascidos nele ainda sem promoção, os mais novos primeiro."""
    secao = montar_secao_de_aprendizados(PedidoDeMemoria(alvo=setor, view=view))
    locais = _aprendizados_locais(setor, view, excluidos=frozenset(secao.ids_incluidos))
    linhas = [*secao.linhas, *(formatar_aprendizado(no, view) for no in locais)]
    if not linhas:
        return (TITULO_DOS_APRENDIZADOS, SEM_APRENDIZADOS)
    excedente = len(linhas) - LIMITE_DE_APRENDIZADOS
    mantidas = linhas[:LIMITE_DE_APRENDIZADOS]
    if excedente > 0:
        mantidas.append(f"- ... e mais {excedente} (use `ler_vista` no Setor ou `buscar`)")
    return (TITULO_DOS_APRENDIZADOS, *mantidas)


def _aprendizados_locais(setor: NoGrafo, view: GrafoView, *, excluidos: frozenset[str]) -> tuple[NoGrafo, ...]:
    """Aprendizados nascidos nas sessões deste Setor e ainda em vigor: até a promoção, valem só onde nasceram."""
    sessoes = view.obter_filhos_por_contencao(setor.id)
    nascidos = [
        no
        for sessao in sessoes
        for no in produzidos_pela_sessao(sessao.id, view)
        if no.tipo == TipoNo.APRENDIZADO and no.id not in excluidos and substituto_promovido(no.id, view) is None
    ]
    return tuple(sorted(nascidos, key=lambda no: (-no.ordem.seq_criacao, no.id)))


def _linhas_da_sessao_anterior(pedido: PedidoDeRetomada) -> tuple[str, ...]:
    """O que a sessão mais recente do Setor deixou, e se a condensação dela ficou por fazer."""
    anterior = _sessao_anterior(pedido)
    if anterior is None:
        return (TITULO_DA_SESSAO_ANTERIOR, SEM_SESSAO_ANTERIOR)
    cabecalho = f"- [{anterior.id}] {anterior.rotulo}"
    return (TITULO_DA_SESSAO_ANTERIOR, cabecalho, *_descrever_sessao(anterior, pedido.view))


def _sessao_anterior(pedido: PedidoDeRetomada) -> NoGrafo | None:
    """A sessão mais recente do Setor que não é a que está abrindo."""
    outras = [
        no
        for no in pedido.view.obter_filhos_por_contencao(pedido.id_setor)
        if no.tipo == TipoNo.SESSAO and no.id != pedido.id_sessao
    ]
    return max(outras, key=lambda no: (no.ordem.seq_criacao, no.id), default=None)


def _linhas_da_sessao_retomada(pedido: PedidoDeRetomada) -> tuple[str, ...]:
    """Quando a sessão já existia e já registrou trabalho, diz o que ela mesma deixou."""
    sessao = pedido.view.obter_no(pedido.id_sessao)
    if sessao is None or not tem_trabalho_a_condensar(sessao.id, pedido.view):
        return ()
    return (TITULO_DA_SESSAO_RETOMADA, *_descrever_sessao(sessao, pedido.view))


def _descrever_sessao(sessao: NoGrafo, view: GrafoView) -> tuple[str, ...]:
    """Balanço, fechamento e condensação em poucas linhas; ou a constatação de que nada foi registrado."""
    if not tem_trabalho_a_condensar(sessao.id, view):
        return (SEM_REGISTROS,)
    linhas = [f"  {_balanco(sessao, view)}", *(f"  {linha}" for linha in _fechamento(sessao, view).descrever())]
    nota = localizar_condensacao(sessao.id, view)
    if nota is not None:
        corpo = str(nota.obter_propriedade(CAMPO_CORPO, "")).strip() or nota.rotulo
        linhas.append(f"  condensacao [{nota.id}]: {_recortar(corpo)}")
    elif tem_condensacao_pendente(sessao.id, view):
        pendente = _tarefa_de_condensacao_pendente(sessao, view)
        linhas.append(f"  condensacao pendente: Task {pendente}: assuma-a e escreva a Note de condensacao.")
    return tuple(linhas)


def _balanco(sessao: NoGrafo, view: GrafoView) -> str:
    """Status e contagem por tipo do que a sessão produziu, sem a telemetria e sem a Task de condensar."""
    status = str(sessao.obter_propriedade("status", StatusSessao.ATIVA.value))
    contagem = Counter(
        no.tipo.value
        for no in produzidos_pela_sessao(sessao.id, view)
        if no.tipo != TipoNo.RUN and not eh_tarefa_de_condensacao(no)
    )
    registros = ", ".join(f"{total} {tipo}" for tipo, total in sorted(contagem.items()))
    return f"status {status} | {registros}"


def _fechamento(sessao: NoGrafo, view: GrafoView) -> FechamentoDeSubarvore:
    """O esqueleto determinístico do rollup, ou um vazio quando a sessão não contém nada."""
    resumo = view.obter_resumo(sessao.id)
    return resumo.fechamento if resumo is not None else FechamentoDeSubarvore()


def _tarefa_de_condensacao_pendente(sessao: NoGrafo, view: GrafoView) -> str:
    """O id da Task de condensar ainda aberta, para o agente assumi-la sem procurar."""
    pendentes = [
        no.id
        for no in produzidos_pela_sessao(sessao.id, view)
        if eh_tarefa_de_condensacao(no)
        and str(no.obter_propriedade("status", StatusTask.PENDENTE.value)) != StatusTask.CONCLUIDO.value
    ]
    return pendentes[0] if pendentes else ""


def _recortar(texto: str) -> str:
    """Uma linha só, cortada no limite: a condensação inteira fica para `ler_vista`."""
    plano = " ".join(texto.split())
    if len(plano) <= LIMITE_DE_CARACTERES_DA_CONDENSACAO:
        return plano
    return plano[: LIMITE_DE_CARACTERES_DA_CONDENSACAO - 3] + "..."
