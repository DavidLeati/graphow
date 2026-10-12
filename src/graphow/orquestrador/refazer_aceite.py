"""Refazer o aceite de um critério: o autor de aceite reescreve os testes dele, com o motivo do humano no briefing.

O teste de aceite errado travava o Goal: o executor não pode mexer nele, e
nada o refazia. Com `--refazer-aceite C3 --motivo` (ou com a resposta do
humano à dúvida do executor que diz que o teste de C3 está errado), uma
sessão nova do autor de aceite reescreve só os testes de C3, em `aceite/`,
com o motivo e os testes atuais no briefing. O orquestrador confere a forma,
que nada fora dos arquivos de C3 em `aceite/` mudou e que cada teste novo
roda: verde, ou vermelho pela asserção dele (a implementação pode já estar
lá, ou não). Conferido, commita com o trailer da revisão do aceite, troca no
Goal o aceite de C3 (o commit do aceite passa a ser este) e liga o Criterio
aos testes novos. No modo supervisionado, a aprovação valia para o commit
anterior do aceite: o portão volta, e o humano aprova os testes refeitos.
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_autor_de_aceite
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.esquemas import PAPEL_AUTOR_DE_ACEITE
from graphow.orquestrador.git_do_goal import commit_da_fatia, descartar_mudancas, mensagem_do_orquestrador
from graphow.orquestrador.configuracao_do_aceite import configuracao_do_aceite
from graphow.orquestrador.gravacao_do_aceite import AceiteParaGravar, commit_da_configuracao, gravar_aceite, gravar_aceite_proposto
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.pedidos_do_humano import PedidoDoHumano
from graphow.orquestrador.replanejamento import atendidos_com
from graphow.orquestrador.saida_do_aceite import AceiteDoCriterio, SaidaDoAceite, conferir_forma, dentro_do_aceite, e_cache, rodar_testes
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite
from graphow.orquestrador.verificacao_do_marco import nos_do_plano

CHAVE_DO_REFEITO: str = "refeito"


def refazer_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None:
    """Uma sessão do autor de aceite refaz os testes do critério do pedido; commita e grava, ou diz por que não deu."""
    atual = SaidaDoAceite.do_livro(estado.aceite)
    id_revisao = f"{m.id_do_aceite(contexto.id_goal, m.versao_do_plano(estado.propriedades))}-r{_revisoes(estado) + 1}"
    feito = commit_da_fatia(contexto.area, id_revisao, contexto.configuracao.base)
    if feito is None:
        sem_orcamento = contexto.sem_orcamento()
        if sem_orcamento is not None:
            return sem_orcamento
        novo, problemas = _sessao(contexto, estado, pedido, atual=atual)
        if novo is None:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA,
                          f"Os testes refeitos de {pedido.alvo} nao conferiram: " + "; ".join(problemas))
        gravar_aceite_proposto(contexto.livro, {CHAVE_DO_REFEITO: _em_json(novo), "pedido": pedido.id})
        assunto = f"Refaz os testes de aceite de {pedido.alvo} do Goal {contexto.configuracao.slug}"
        commit = contexto.commitar(mensagem_do_orquestrador(assunto, f"Pedido do humano: {pedido.motivo}", id_goal=contexto.id_goal,
                                                            id_task=id_revisao), vazio_permitido=True)
    else:
        proposto = estado.propriedades.get(m.CAMPO_ACEITE_PROPOSTO)
        refeito = proposto.get(CHAVE_DO_REFEITO) if isinstance(proposto, Mapping) else None
        novo, commit = SaidaDoAceite.do_livro(refeito if isinstance(refeito, Mapping) else estado.aceite), feito.hash
    _gravar(contexto, estado, novo, commit=commit, pedido=pedido)
    return None


def _em_json(saida: SaidaDoAceite) -> dict[str, Any]:
    """O aceite refeito como o Goal o guarda, para a retomada depois do commit."""
    return {"comando": saida.comando_aceite, "resumo": saida.resumo,
            "criterios": [{"id": criterio.id, **criterio.em_json()} for criterio in saida.criterios]}


def _revisoes(estado: EstadoDoGoal) -> int:
    """Quantas vezes o aceite deste plano já foi refeito."""
    valor = (estado.aceite or {}).get("revisoes")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


def _sessao(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano, *,
            atual: SaidaDoAceite) -> tuple[SaidaDoAceite | None, tuple[str, ...]]:
    """A sessão do autor, conferida; o aceite inteiro com o critério refeito, ou os problemas."""
    guarda: dict[str, SaidaDoAceite] = {}

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel, tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s)

    def conferir(dados: Mapping[str, Any]) -> tuple[str, ...]:
        refeito = SaidaDoAceite.de_json(dados)
        problemas = _conferir(contexto, estado, refeito, pedido=pedido, rodar=rodar)
        guarda["aceite"] = _com_o_refeito(atual, refeito, pedido.alvo)
        return problemas

    resposta = contexto.sessoes.rodar(PedidoDePapel(
        papel=PAPEL_AUTOR_DE_ACEITE, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=_revisoes(estado) + 2,
        briefing=briefing_do_refazer(estado, pedido, atual), conferir=conferir, orcamento_restante_usd=contexto.restante()))
    if resposta.dados is None:
        descartar_mudancas(contexto.area, contexto.patch(f"aceite-refeito-{pedido.alvo}"))
        return None, resposta.problemas
    return guarda["aceite"], ()


def _conferir(contexto: ContextoDoGoal, estado: EstadoDoGoal, refeito: SaidaDoAceite, *, pedido: PedidoDoHumano,
              rodar: Any) -> tuple[str, ...]:
    """Só o critério do pedido, com a forma do aceite, mexendo só nos arquivos dele em aceite/, e cada teste rodando direito."""
    criterio = pedido.alvo
    if [c.id for c in refeito.criterios] != [criterio]:
        return (f"devolva so o criterio {criterio} em 'criterios'",)
    tipos = {str(c["id"]): str(c["verificacao"]) for c in (estado.plano or {}).get("criterios", []) if str(c["id"]) == criterio}
    mudados = [c for c in contexto.git.caminhos_mudados() if not e_cache(c)]
    alheios = _arquivos_dos_outros(estado, criterio)
    problemas = [*conferir_forma(refeito, tipos, contexto.area, mudados=mudados),
                 *(f"{caminho} e teste de outro criterio: refaca so os de {criterio}" for caminho in mudados if caminho in alheios)]
    if problemas:
        return tuple(problemas)
    with configuracao_do_aceite(contexto.area, commit_da_configuracao(estado.aceite)):
        execucoes = rodar_testes(refeito, rodar)
    return tuple(f"o teste {e.teste} de {criterio} nao passa e nao falha numa assercao dele: {motivo}"
                 for e in execucoes if not e.passou and (motivo := e.vermelho_invalido()))


def _arquivos_dos_outros(estado: EstadoDoGoal, criterio: str) -> set[str]:
    """Os arquivos de aceite dos outros critérios: o autor que refaz um critério não os toca."""
    atual = SaidaDoAceite.do_livro(estado.aceite)
    return {teste.arquivo for c, teste in atual.testes() if c.id != criterio and dentro_do_aceite(teste.arquivo)}


def _com_o_refeito(atual: SaidaDoAceite, refeito: SaidaDoAceite, criterio: str) -> SaidaDoAceite:
    """O aceite inteiro com o critério trocado pelo refeito, e o comando de todos que o autor devolveu."""
    novo: AceiteDoCriterio = refeito.criterios[0] if refeito.criterios else AceiteDoCriterio(criterio)
    criterios = tuple(novo if c.id == criterio else c for c in atual.criterios)
    return replace(atual, criterios=criterios, comando_aceite=refeito.comando_aceite or atual.comando_aceite)


def _gravar(contexto: ContextoDoGoal, estado: EstadoDoGoal, novo: SaidaDoAceite, *, commit: str, pedido: PedidoDoHumano) -> None:
    """O aceite novo no Goal (o commit dele é o da revisão), o Criterio ligado aos testes novos e o pedido atendido."""
    anteriores = [str(a) for a in (estado.aceite or {}).get("arquivos", [])]
    arquivos = tuple(dict.fromkeys([*anteriores, *(teste.arquivo for _, teste in novo.testes())]))
    versao = m.versao_do_plano(estado.propriedades)
    gravar_aceite(contexto.livro, AceiteParaGravar(
        novo, commit, arquivos, [], nos_do_plano(estado.plano or {}), id_do_aceite=f"{m.id_do_aceite(contexto.id_goal, versao)}-r{_revisoes(estado) + 1}",
        revisoes=_revisoes(estado) + 1, atendidos=tuple(atendidos_com(estado, pedido.id)), so=(pedido.alvo,),
        commit_da_configuracao=commit_da_configuracao(estado.aceite)))


def briefing_do_refazer(estado: EstadoDoGoal, pedido: PedidoDoHumano, atual: SaidaDoAceite) -> str:
    """O pedido ao autor: o de sempre, mais o critério a refazer, os testes atuais dele e o motivo do humano."""
    do_criterio = atual.do_criterio(pedido.alvo)
    testes = [f"- {t.arquivo}::{t.nome} (`{t.comando}`)" for t in (do_criterio.testes if do_criterio else ())]
    return "\n\n".join([
        f"# Refazer os testes de aceite de {pedido.alvo}",
        f"O humano pediu que os testes de aceite de {pedido.alvo} sejam refeitos. Motivo do humano: {pedido.motivo}",
        "Testes atuais de " + pedido.alvo + ":\n" + ("\n".join(testes) or "(nenhum)"),
        f"Reescreva so os testes de {pedido.alvo}: pode mudar os arquivos dele em aceite/ e criar novos ali; nao toque nos "
        "testes dos outros criterios nem em nada fora de aceite/. A implementacao pode ja existir: cada teste novo tem de "
        "passar, ou falhar numa assercao dele. Devolva em 'criterios' so a entrada de " + pedido.alvo + ", e o comando_aceite de todos.",
        briefing_do_autor_de_aceite(estado),
    ])
