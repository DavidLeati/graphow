"""Refazer o aceite de um critério: o autor de aceite reescreve os testes dele, com o motivo do humano no briefing.

O teste de aceite errado travava o Goal: o executor não pode mexer nele, e
nada o refazia. Com `--refazer-aceite C3 --motivo` (ou com a resposta do
humano à dúvida do executor que diz que o teste de C3 está errado), uma
sessão nova do autor de aceite reescreve só os testes de C3, em `aceite/`,
com o motivo e os testes atuais no briefing. O orquestrador confere a forma,
que nada fora dos arquivos de C3 em `aceite/` mudou e que cada teste novo
roda na ponta: verde, ou vermelho pela asserção dele (a implementação pode já
estar lá, ou não). E o teste novo tem de falhar numa asserção contra o código
de antes da implementação (orquestrador/vermelho_do_refeito.py): o que nasce
verde, escrito depois da fatia, não prova nada. O que não falha antes volta ao
autor uma vez, com o motivo; se persistir, fica o teste antigo (um commit
vazio, como quando o autor o mantém), e o desacordo vai à verificação: pela
fatia que apontou o teste ou, no pedido do humano, pelo Goal. Conferido,
commita com o trailer da revisão do aceite, troca no Goal o aceite de C3 (o
commit do aceite passa a ser este) e liga o Criterio aos testes novos. No modo
supervisionado, a aprovação valia para o commit anterior do aceite: o portão
volta, e o humano aprova os testes refeitos.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_autor_de_aceite
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.decisoes_do_agente import (
    CAMPO_CRITERIOS_REFEITOS,
    CAMPO_REFEITO_SEM_VERMELHO,
    CAMPO_RESPOSTA_DO_AUTOR,
    PREFIXO_DO_PEDIDO_AUTOMATICO,
)
from graphow.orquestrador.esquemas import PAPEL_AUTOR_DE_ACEITE
from graphow.orquestrador.git_do_goal import arquivos_do_commit, commit_da_fatia, descartar_mudancas, mensagem_do_orquestrador
from graphow.orquestrador.livro_razao import propriedade
from graphow.orquestrador.aceite_intocado import forcar_o_aceite_no_indice
from graphow.orquestrador.gravacao_do_aceite import AceiteParaGravar, commit_da_configuracao, gravar_aceite, gravar_aceite_proposto
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.pedidos_do_humano import PedidoDoHumano
from graphow.orquestrador.replanejamento import atendidos_com
from graphow.orquestrador.saida_do_aceite import (
    PASTA_DO_ACEITE,
    AceiteDoCriterio,
    SaidaDoAceite,
    conferir_forma,
    dentro_do_aceite,
    e_cache,
    rodar_testes,
)
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.suite import ResultadoDaSuite, rodar_suite
from graphow.orquestrador.verificacao_do_marco import nos_do_plano
from graphow.orquestrador.vermelho_do_refeito import conferir_o_vermelho_de_antes

CHAVE_DO_REFEITO: str = "refeito"
CHAVE_SEM_VERMELHO: str = "sem_vermelho"


@dataclass(frozen=True)
class Refeito:
    """O que a sessão do autor deu: o aceite novo, ou os problemas; `sem_vermelho` diz por que ficou o teste antigo."""

    aceite: SaidaDoAceite | None
    problemas: tuple[str, ...] = ()
    sem_vermelho: str = ""


def refazer_aceite(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano) -> Parada | None:
    """Uma sessão do autor de aceite refaz os testes do critério do pedido; commita e grava, ou diz por que não deu."""
    id_revisao = f"{m.id_do_aceite(contexto.id_goal, m.versao_do_plano(estado.propriedades))}-r{_revisoes(estado) + 1}"
    feito = commit_da_fatia(contexto.area, id_revisao, contexto.configuracao.base)
    if feito is None:
        sem_orcamento = contexto.sem_orcamento()
        if sem_orcamento is not None:
            return sem_orcamento
        refeito = _sessao(contexto, estado, pedido, atual=SaidaDoAceite.do_livro(estado.aceite))
        if refeito.aceite is None:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA,
                          f"Os testes refeitos de {pedido.alvo} nao conferiram: " + "; ".join(refeito.problemas))
        novo, sem_vermelho = refeito.aceite, refeito.sem_vermelho
        commit = _commitar(contexto, pedido, novo, sem_vermelho=sem_vermelho, id_revisao=id_revisao)
    else:
        (novo, sem_vermelho), commit = _do_proposto(estado), feito.hash
    _gravar(contexto, estado, novo, commit=commit, pedido=pedido, sem_vermelho=sem_vermelho)
    if pedido.fatia:
        _responder_a_fatia(contexto, estado, pedido, commit=commit, resumo=novo.resumo)
    return None


def _commitar(contexto: ContextoDoGoal, pedido: PedidoDoHumano, novo: SaidaDoAceite, *, sem_vermelho: str, id_revisao: str) -> str:
    """O refeito no Goal, para a retomada, e o commit dele; o que fica com o teste antigo commita vazio, com o porquê."""
    gravar_aceite_proposto(contexto.livro, {CHAVE_DO_REFEITO: _em_json(novo), "pedido": pedido.id, CHAVE_SEM_VERMELHO: sem_vermelho})
    slug = contexto.configuracao.slug
    assunto, corpo = ((f"Mantem os testes de aceite de {pedido.alvo} do Goal {slug}", sem_vermelho) if sem_vermelho else
                      (f"Refaz os testes de aceite de {pedido.alvo} do Goal {slug}", f"Pedido do humano: {pedido.motivo}"))
    forcar_o_aceite_no_indice(contexto.area)
    mensagem = mensagem_do_orquestrador(assunto, corpo, id_goal=contexto.id_goal, id_task=id_revisao)
    return contexto.commitar(mensagem, vazio_permitido=True, caminhos=(PASTA_DO_ACEITE,))


def _do_proposto(estado: EstadoDoGoal) -> tuple[SaidaDoAceite, str]:
    """Na retomada depois do commit, o refeito que o Goal guardou antes dele e o porquê de ter ficado o teste antigo."""
    proposto = estado.propriedades.get(m.CAMPO_ACEITE_PROPOSTO)
    guardado: Mapping[str, Any] = proposto if isinstance(proposto, Mapping) else {}
    refeito = guardado.get(CHAVE_DO_REFEITO)
    novo = SaidaDoAceite.do_livro(refeito if isinstance(refeito, Mapping) else estado.aceite)
    return novo, str(guardado.get(CHAVE_SEM_VERMELHO) or "")


def _em_json(saida: SaidaDoAceite) -> dict[str, Any]:
    """O aceite refeito como o Goal o guarda, para a retomada depois do commit."""
    return {"comando": saida.comando_aceite, "resumo": saida.resumo,
            "criterios": [{"id": criterio.id, **criterio.em_json()} for criterio in saida.criterios]}


def _revisoes(estado: EstadoDoGoal) -> int:
    """Quantas vezes o aceite deste plano já foi refeito."""
    valor = (estado.aceite or {}).get("revisoes")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


def _sessao(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano, *, atual: SaidaDoAceite) -> Refeito:
    """A sessão do autor, conferida na ponta e contra o código de antes; o aceite inteiro com o critério refeito, ou os problemas."""
    guarda: dict[str, Any] = {}

    def rodar(comando: str) -> ResultadoDaSuite:
        return rodar_suite(contexto.area, comando, contexto.banco_descartavel,
                           tempo_limite_s=contexto.opcoes.tempo_limite_da_suite_s, do_aceite=True)

    def conferir(dados: Mapping[str, Any]) -> tuple[str, ...]:
        refeito = SaidaDoAceite.de_json(dados)
        problemas = _conferir(contexto, estado, refeito, pedido=pedido, rodar=rodar)
        guarda["aceite"] = _com_o_refeito(atual, refeito, pedido.alvo)
        refez = not problemas and _refez(contexto, atual, refeito, criterio=pedido.alvo)
        guarda["antes"] = conferir_o_vermelho_de_antes(contexto, estado, refeito, criterio=pedido.alvo) if refez else ()
        return (*problemas, *guarda["antes"])

    resposta = contexto.sessoes.rodar(PedidoDePapel(
        papel=PAPEL_AUTOR_DE_ACEITE, id_goal=contexto.id_goal, pasta=contexto.area, tentativa=_revisoes(estado) + 2,
        briefing=briefing_do_refazer(estado, pedido, atual), conferir=conferir, orcamento_restante_usd=contexto.restante()))
    if resposta.dados is None:
        descartar_mudancas(contexto.area, contexto.patch(f"aceite-refeito-{pedido.alvo}"))
        return _sem_o_refeito(atual, pedido, resposta.problemas, antes=guarda.get("antes", ()))
    return Refeito(guarda["aceite"])


def _refez(contexto: ContextoDoGoal, atual: SaidaDoAceite, refeito: SaidaDoAceite, *, criterio: str) -> bool:
    """O autor mudou os testes do critério (os arquivos em aceite/ ou a lista); devolvê-los iguais é mantê-los."""
    anterior = atual.do_criterio(criterio)
    mudou_arquivo = any(dentro_do_aceite(caminho) and not e_cache(caminho) for caminho in contexto.git.caminhos_mudados())
    return mudou_arquivo or (anterior.testes if anterior else ()) != refeito.criterios[0].testes


def _sem_o_refeito(atual: SaidaDoAceite, pedido: PedidoDoHumano, problemas: Sequence[str], *, antes: Sequence[str]) -> Refeito:
    """Os problemas da sessão; quando sobrou só o vermelho que faltou antes, fica o teste antigo, com o porquê."""
    if not antes or tuple(problemas) != tuple(antes):
        return Refeito(None, tuple(problemas))
    porque = (f"O teste refeito de {pedido.alvo} nao falhou numa assercao contra o codigo de antes da implementacao, nem "
              "depois de voltar ao autor de aceite com o motivo; fica o teste antigo. " + "; ".join(antes))
    return Refeito(replace(atual, resumo=porque), tuple(antes), porque)


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
    return replace(atual, criterios=criterios, comando_aceite=refeito.comando_aceite or atual.comando_aceite,
                   resumo=refeito.resumo or atual.resumo)


def _gravar(contexto: ContextoDoGoal, estado: EstadoDoGoal, novo: SaidaDoAceite, *, commit: str, pedido: PedidoDoHumano,
            sem_vermelho: str = "") -> None:
    """O aceite novo no Goal (o commit dele é o da revisão), o Criterio ligado aos testes novos e o pedido atendido."""
    if sem_vermelho and not pedido.fatia:
        _registrar_o_desacordo(contexto, estado, pedido, porque=sem_vermelho)
    anteriores = [str(a) for a in (estado.aceite or {}).get("arquivos", [])]
    arquivos = tuple(dict.fromkeys([*anteriores, *(teste.arquivo for _, teste in novo.testes())]))
    versao = m.versao_do_plano(estado.propriedades)
    gravar_aceite(contexto.livro, AceiteParaGravar(
        novo, commit, arquivos, [], nos_do_plano(estado.plano or {}), id_do_aceite=f"{m.id_do_aceite(contexto.id_goal, versao)}-r{_revisoes(estado) + 1}",
        revisoes=_revisoes(estado) + 1, atendidos=tuple(atendidos_com(estado, pedido.id)), so=(pedido.alvo,),
        commit_da_configuracao=commit_da_configuracao(estado.aceite)))


def _registrar_o_desacordo(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano, *, porque: str) -> None:
    """O refazer do humano que ficou com o teste antigo: sem fatia que o leve, o desacordo vai ao Goal, e dali à verificação."""
    valor = estado.propriedades.get(CAMPO_REFEITO_SEM_VERMELHO)
    anteriores = [dict(item) for item in (valor if isinstance(valor, list) else [])
                  if isinstance(item, Mapping) and item.get("pedido") != pedido.id]
    desacordo = {"criterio": pedido.alvo, "pedido": pedido.id, "motivo": pedido.motivo, "porque": porque}
    contexto.livro.gravar([propriedade(contexto.id_goal, CAMPO_REFEITO_SEM_VERMELHO, [*anteriores, desacordo])],
                          f"O teste refeito de {pedido.alvo} nao falhou antes da implementacao: fica o antigo")


def _responder_a_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, pedido: PedidoDoHumano, *, commit: str, resumo: str) -> None:
    """A fatia que apontou o teste errado recebe o que o autor fez (refez ou manteve, e o porquê); o refazer do agente conta uma vez."""
    mudou = any(dentro_do_aceite(caminho) for caminho in arquivos_do_commit(contexto.area, commit))
    resposta = {"criterio": pedido.alvo, "mudou": mudou, "resumo": resumo, "pedido": pedido.id}
    operacoes = [propriedade(pedido.fatia, CAMPO_RESPOSTA_DO_AUTOR, resposta)]
    if pedido.id.startswith(PREFIXO_DO_PEDIDO_AUTOMATICO):
        refeitos = [str(c) for c in estado.propriedades.get(CAMPO_CRITERIOS_REFEITOS) or []]
        operacoes.append(propriedade(estado.id_goal, CAMPO_CRITERIOS_REFEITOS, [*refeitos, pedido.alvo]))
    contexto.livro.gravar(operacoes, f"Resposta do autor de aceite sobre o teste de {pedido.alvo} a fatia {pedido.fatia}")


def briefing_do_refazer(estado: EstadoDoGoal, pedido: PedidoDoHumano, atual: SaidaDoAceite) -> str:
    """O pedido ao autor: o de sempre, mais o critério a refazer, os testes atuais dele e o motivo do humano."""
    do_criterio = atual.do_criterio(pedido.alvo)
    testes = [f"- {t.arquivo}::{t.nome} (`{t.comando}`)" for t in (do_criterio.testes if do_criterio else ())]
    return "\n\n".join([
        f"# Refazer os testes de aceite de {pedido.alvo}",
        f"Pediu-se que os testes de aceite de {pedido.alvo} sejam refeitos. Motivo: {pedido.motivo}",
        "Se o teste esta certo, mantenha-o (devolva os mesmos testes, sem mudar os arquivos) e diga por que no resumo: "
        "o executor recebe a sua resposta, e a verificacao julga o desacordo." if pedido.fatia else "",
        "Testes atuais de " + pedido.alvo + ":\n" + ("\n".join(testes) or "(nenhum)"),
        f"Reescreva so os testes de {pedido.alvo}: pode mudar os arquivos dele em aceite/ e criar novos ali; nao toque nos "
        "testes dos outros criterios nem em nada fora de aceite/. A implementacao pode ja existir: aqui, cada teste novo tem de "
        "passar, ou falhar numa assercao dele; e o orquestrador o roda tambem contra o codigo de antes da implementacao (o "
        f"commit anterior a primeira fatia que cobre {pedido.alvo}), onde ele tem de falhar numa assercao dele: o teste que "
        "ja nasce verde nao prova o criterio. Devolva em 'criterios' so a entrada de " + pedido.alvo + ", e o comando_aceite de todos.",
        briefing_do_autor_de_aceite(estado),
    ])
