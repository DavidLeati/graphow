"""O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal.

Com as fatias do marco concluídas, o marco é verificado por uma sessão nova
do verificador (orquestrador/verificacao_do_marco.py). Os Achados bloqueantes
viram a fatia de correção do marco, todos os do ciclo numa fatia só, até
dois ciclos por marco. O marco segue quando a verificação dele sai limpa;
o marco intermediário que esgota os ciclos também segue, com os bloqueantes
abertos, para que os marcos seguintes rodem. O último marco é a verificação
final, sobre o Goal inteiro: ela cobra de novo os bloqueantes que os outros
marcos deixaram, e os das verificações dela que deixaram de valer, com os
ciclos dela, e só esgotados esses o laço para, em bloqueantes restantes. O Goal
só fecha quando não há bloqueante aberto e a verificação final limpa vale
para o commit atual: a verificação foi feita no commit do código da
ponta da branch (o commit que só mudou o documento do Goal não conta). O
kernel recusa o fechamento que não tiver essa prova. No modo autônomo o
orquestrador integra por fast-forward na base e fecha; no supervisionado,
para com "pronto para integrar", e a chamada seguinte vê a branch integrada e
fecha. A base que andou desde que a branch do Goal saiu dela ganha antes o
rebase da branch, a suíte e, se o rebase mudou arquivo de critério, a
verificação final de novo (orquestrador/base_que_andou.py). Logo antes de
integrar, o laço relê o Goal: o cancelamento que chegou no meio do passo
impede a integração; o que chegou depois dessa releitura e antes do
fast-forward fica numa nota do Goal, que segue cancelado
(orquestrador/cancelamento_tardio.py).

O documento é sincronizado com as pendências a cada passo depois da
verificação, e por isso a queda entre o lote e o commit do documento não perde
acompanhamento.
"""

from collections.abc import Sequence
from pathlib import Path

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.base_que_andou import base_andou, rebasear_o_goal
from graphow.orquestrador.cancelamento_tardio import anotar_o_cancelamento_tardio
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.git_do_goal import FalhaDoGitDoGoal, GitDoGoal, remover_area
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado, VerificacaoRegistrada
from graphow.orquestrador.refs_do_humano import integrar_por_fast_forward
from graphow.orquestrador.registro_do_rebase import equivalentes_da_ponta
from graphow.orquestrador.salvaguarda_do_humano import PASTA_DA_SALVAGUARDA
from graphow.orquestrador.verificacao_do_marco import sincronizar_documento, verificar_marco


def verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Com as fatias do marco concluídas: verifica o commit atual, abre correções, segue ao próximo marco ou fecha."""
    verificacoes = estado.verificacoes_do_marco(marco)
    ultima = verificacoes[-1] if verificacoes else None
    if ultima is None or not _vale_para_o_commit_atual(contexto, estado, ultima) or _ja_corrigida(estado, ultima):
        return verificar_marco(contexto, estado, marco)
    sincronizar_documento(contexto, estado.pendencias, numero=len(estado.verificacoes))
    carregados = estado.bloqueantes_de_antes(ultima) if marco.final else ()
    if ultima.limpa and not carregados:
        return _fechar(contexto, estado, marco) if marco.final else None
    return _corrigir(contexto, estado, ultima, marco=marco)


def _vale_para_o_commit_atual(contexto: ContextoDoGoal, estado: EstadoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação foi feita no commit do código atual, ou num que o rebase deu por equivalente a ele.

    O que veio depois dela só mexeu no documento do Goal, ou foi o rebase que
    não mudou arquivo de critério (`equivalente_a` na ponta,
    orquestrador/base_que_andou.py). É a mesma conta que o kernel faz contra a
    ponta da branch gravada no Goal (kernel/fechamento_do_goal.py); a
    verificação de antes da fase 2, sem o commit do código, não vale mais e é
    refeita.
    """
    atual = contexto.commit_do_codigo()
    return bool(verificacao.commit_do_codigo) and verificacao.commit_do_codigo in (atual, *equivalentes_da_ponta(estado.propriedades, atual))


def _ja_corrigida(estado: EstadoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação já teve as correções dela (as dos bloqueantes dela e, na final, as dos que ela cobrou), todas concluídas."""
    correcoes = [fatia for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == verificacao.id]
    return bool(correcoes) and all(f.status == m.STATUS_CONCLUIDO for f in correcoes)


def _corrigir(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, ultima: VerificacaoRegistrada, *, marco: MarcoRegistrado
) -> Parada | None:
    """Os bloqueantes (na final, também os das outras verificações) viram fatias de correção enquanto o marco tiver ciclo.

    Sem ciclo, o marco intermediário segue (o laço vai ao marco seguinte), e a
    final para: não há mais o que executar.
    """
    bloqueantes = (*ultima.bloqueantes_abertos(), *(estado.bloqueantes_de_antes(ultima) if marco.final else ()))
    if not bloqueantes:
        return _so_criterio_reprovado(contexto, ultima)
    ciclos = estado.ciclos_do_marco(marco)
    if ciclos < estado.limite_de_ciclos(marco):
        ordem = max((fatia.ordem for fatia in estado.fatias), default=0)
        contexto.livro.criar_correcoes(ultima.id, bloqueantes, ciclo=ciclos + 1, ordem=ordem, marco=marco.id)
        return None
    if not marco.final:
        return None
    return _bloqueantes_restantes(contexto, ultima, bloqueantes, ciclos=ciclos, marco=marco)


def _bloqueantes_restantes(
    contexto: ContextoDoGoal, ultima: VerificacaoRegistrada, bloqueantes: Sequence[AchadoRegistrado], *, ciclos: int,
    marco: MarcoRegistrado,
) -> Parada:
    """A final sem ciclo com bloqueante aberto: as saídas do humano, e o aviso de que o descarte não aprova o critério reprovado."""
    titulos = "; ".join(achado.texto("titulo") for achado in bloqueantes)
    reprovados = (f" A verificacao {ultima.id} reprova {', '.join(ultima.reprovados)}: descartar os achados nao fecha o Goal, "
                  f"e so `--retirar-criterio <criterio> --motivo \"...\"` ou `--refazer-aceite <criterio>` tiram o criterio "
                  f"reprovado da frente.") if ultima.reprovados else ""
    return Parada(
        contexto.id_goal,
        MotivoDaParada.BLOQUEANTES_RESTANTES,
        f"Depois de {ciclos} ciclos de correcao na verificacao final ({marco.id}), ainda ha {len(bloqueantes)} bloqueante(s): "
        f"{titulos}. Eles seguem como Achados abertos e nas pendencias do Goal; o Goal fica aberto, e o kernel nao o fecha "
        f"enquanto houver bloqueante aberto. Saidas do humano: `graphow orquestrar --goal {contexto.id_goal} --mais-ciclos 1 "
        f"--motivo \"...\"` (mais um ciclo de correcao), `--descartar-achado <id> --motivo \"...\"` (aceita o achado: "
        + ", ".join(achado.id for achado in bloqueantes) + ") ou `--cancelar --motivo \"...\"`." + reprovados,
    )


def _so_criterio_reprovado(contexto: ContextoDoGoal, ultima: VerificacaoRegistrada) -> Parada:
    """A verificação sem bloqueante aberto, mas com critério reprovado: o descarte não aprova critério, e o laço para."""
    criterios = ", ".join(ultima.reprovados)
    return Parada(
        contexto.id_goal, MotivoDaParada.BLOQUEANTES_RESTANTES,
        f"A verificacao {ultima.id} reprova {criterios}, e os achados que os feriam foram descartados: o descarte nao aprova "
        f"criterio. Para fechar sem eles: `graphow orquestrar --goal {contexto.id_goal} --retirar-criterio <criterio> --motivo "
        f"\"...\"`; se o teste de aceite esta errado, `--refazer-aceite <criterio> --motivo \"...\"`; ou `--cancelar`.",
    )


def _fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Integra no modo autônomo, ou espera o humano integrar no supervisionado; fecha quando integrado.

    A verificação final que ficou limpa porque o humano descartou o
    bloqueante dela não resolveu, ao ser gravada, os achados que as correções
    tinham entregue: eles se resolvem agora, confirmados por ela. A base que
    andou ganha o rebase da branch do Goal (orquestrador/base_que_andou.py), e
    o passo seguinte volta aqui: a conferência da base é sempre a de logo
    antes de integrar.
    """
    contexto.livro.resolver(estado.corrigidos(marco), f"Achados corrigidos confirmados pela verificacao final do Goal {contexto.id_goal}")
    configuracao = contexto.configuracao
    repositorio = Path(configuracao.repositorio)
    head = contexto.git.head()
    andou = _branch_andou(repositorio, configuracao.ramo, head)
    if andou:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, andou)
    if GitDoGoal(repositorio).e_ancestral(head, configuracao.base):
        return _cancelado_depois_da_leitura(contexto) or _fechar_integrado(
            contexto, GitDoGoal(repositorio).rodar("rev-parse", configuracao.base).strip())
    if base_andou(contexto):
        return rebasear_o_goal(contexto, estado)
    cancelado = _cancelado_depois_da_leitura(contexto)
    if cancelado is not None or configuracao.modo != m.MODO_AUTONOMO:
        return cancelado or _pronto_para_integrar(contexto, head)
    return _integrar(contexto, repositorio, head)


def _pronto_para_integrar(contexto: ContextoDoGoal, head: str) -> Parada:
    """A parada do supervisionado: a verificação limpa vale para a ponta, e o humano integra o hash dela.

    O comando leva o hash, e não o nome da branch: a branch que anda depois
    da verificação não leva à base, por ele, um commit que ninguém verificou
    (revisão da T3f2).
    """
    configuracao = contexto.configuracao
    return Parada(
        contexto.id_goal,
        MotivoDaParada.PRONTO_PARA_INTEGRAR,
        f"Pronto para integrar: a verificacao limpa vale para {head[:12]}. Integre com "
        f"`git -C \"{configuracao.repositorio}\" merge --ff-only {head}` (na base {configuracao.base}) e rode de "
        f"novo para fechar.",
    )


def _integrar(contexto: ContextoDoGoal, repositorio: Path, head: str) -> Parada | None:
    """O fast-forward da base até o commit verificado, e o fechamento; a base que andou no meio volta ao rebase.

    A branch do Goal que andou no repositório do humano depois de
    `_branch_andou` (no fetch da base, na releitura do cancelamento) recusa a
    integração (orquestrador/refs_do_humano.py), e o laço para com o mesmo
    motivo da conferência de antes: o commit novo não foi verificado.
    """
    configuracao = contexto.configuracao
    try:
        integrado = integrar_por_fast_forward(repositorio, configuracao.ramo, configuracao.base, verificado=head)
    except FalhaDoGitDoGoal as erro:
        andou = _branch_andou(repositorio, configuracao.ramo, head)
        if andou:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA, andou)
        if base_andou(contexto):
            return None
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, f"A integracao nao foi possivel: {erro.formatar_para_llm()}")
    return _cancelamento_tardio(contexto, integrado) or _fechar_integrado(contexto, integrado)


def _cancelamento_tardio(contexto: ContextoDoGoal, integrado: str) -> Parada | None:
    """O cancelamento que chegou depois da releitura e antes do fast-forward: a nota no livro-razão, e o Goal fica cancelado."""
    estado = contexto.estado()
    if not estado.cancelado:
        return None
    texto = (f"O cancelamento chegou depois da releitura de antes do fast-forward: {contexto.configuracao.base} ja estava em "
             f"{integrado[:12]}, com o trabalho do Goal, quando ele foi lido.")
    return anotar_o_cancelamento_tardio(contexto.livro, estado, integrado=integrado, texto=texto)


def _branch_andou(repositorio: Path, ramo: str, head: str) -> str:
    """A branch do Goal no repositório do humano não é mais a ponta que a verificação viu; vazio quando é.

    O fechamento confere a ponta real no git, e não só a que o livro-razão
    guarda: o commit que o humano fez na branch do Goal depois da verificação
    entraria na base sem ter sido verificado.
    """
    real = GitDoGoal(repositorio).tentar("rev-parse", "--verify", "--quiet", f"refs/heads/{ramo}").saida.strip()
    if real == head:
        return ""
    return (
        f"A branch {ramo} no repositorio esta em {real[:12] or '(nenhum commit)'}, e a verificacao final valeu para "
        f"{head[:12]}: alguem a mudou fora do orquestrador depois da verificacao. O Goal nao fecha; volte a branch a "
        f"{head[:12]}, ou cancele o Goal com `--cancelar --motivo`."
    )


def _cancelado_depois_da_leitura(contexto: ContextoDoGoal) -> Parada | None:
    """O cancelamento que chegou depois da leitura do passo: o laço relê o Goal logo antes de integrar, e não integra.

    Na revisão da T3b (achado 7), o `--cancelar` gravado durante o passo não
    era visto até o passo seguinte: o fast-forward levava o Goal à base, e o
    fechamento sobrescrevia o cancelamento.
    """
    estado = contexto.estado()
    if not estado.cancelado:
        return None
    motivo = str(estado.propriedades.get(a.CAMPO_MOTIVO_DO_CANCELAMENTO, ""))
    return Parada(contexto.id_goal, MotivoDaParada.CANCELADO,
                  f"O Goal {contexto.id_goal} foi cancelado antes da integracao, que nao aconteceu: {motivo}")


def _fechar_integrado(contexto: ContextoDoGoal, integrado: str) -> Parada:
    """Fecha o Goal e tira a área de trabalho, que já cumpriu o papel, e a salvaguarda do repositório do humano, salvo a que
    uma Note do Goal ainda cita (`_sobra_da_salvaguarda`)."""
    contexto.livro.fechar(integrado)
    sobra = ("" if remover_area(contexto.area) else f" A area {contexto.area} ficou no disco (o git nao a removeu).")
    return Parada(contexto.id_goal, MotivoDaParada.FECHADO,
                  f"Goal fechado: {contexto.configuracao.base} em {integrado[:12]}.{sobra}{_sobra_da_salvaguarda(contexto)}")


def _sobra_da_salvaguarda(contexto: ContextoDoGoal) -> str:
    """O que a mensagem do fechamento diz da salvaguarda: a que uma Note do Goal ainda cita fica, e a mensagem diz onde e por
    quê; a outra sai, e só vai na mensagem se o disco a segurar.

    A salvaguarda serve enquanto uma parada ou uma Note do Goal pode citá-la para recuperar (ou ver) o de antes de uma
    sessão. A perda para o laço em FALHA, e a parada sugere rodar de novo; o Goal que então fecha não pode levar a pasta
    que o `recuperar` da Note usa, porque o humano pode não ter recuperado ainda. O avanço não para o laço, e o Goal fecha
    na mesma chamada: o `checkout -- .` seguido de um retoque é avanço, e a pasta que o `ver_o_de_antes` da Note cita é a
    única cópia do trabalho que saiu. Nos dois casos ela fica, a mensagem diz onde, e o humano a apaga quando quiser
    (orquestrador/salvaguarda_do_humano.py).
    """
    salvaguarda = contexto.pasta / PASTA_DA_SALVAGUARDA
    citada = _o_que_cita_a_salvaguarda(contexto)
    if not citada:
        return "" if remover_area(salvaguarda) else f" A salvaguarda {salvaguarda} ficou no disco."
    return f" A salvaguarda {salvaguarda} fica no disco: {citada}. Apague a pasta quando quiser." if salvaguarda.is_dir() else ""


def _o_que_cita_a_salvaguarda(contexto: ContextoDoGoal) -> str:
    """Por que a pasta da salvaguarda fica: uma Note do Goal a cita (`guardada_em`) com a perda, que o `recuperar` dela
    devolve, ou com o conteúdo de antes do que avançou, que o `ver_o_de_antes` dela mostra; vazio quando nenhuma a cita.

    A Note do avanço sem o que mostrar (arquivo novo, ref nova, troca de HEAD) não segura a pasta.
    """
    view, sessao = contexto.livro.view(), contexto.livro.id_sessao
    produzidos = (view.obter_no(saida.destino_id) for saida in view.obter_arestas_saida(sessao, TipoAresta.PRODUZ))
    notas = [no for no in produzidos if no is not None and no.tipo == TipoNo.NOTE and no.obter_propriedade("guardada_em")]
    if any(nota.obter_propriedade("acao") == m.ACAO_DO_HUMANO_MEXIDO and nota.obter_propriedade("perdas") for nota in notas):
        return "a Note da perda no repositorio do humano a cita para recuperar o trabalho"
    if any(nota.obter_propriedade("acao") == m.ACAO_DO_HUMANO_QUE_AVANCOU and nota.obter_propriedade("ver_o_de_antes") for nota in notas):
        return "a Note do avanco no repositorio do humano a cita para ver o conteudo de antes do que mudou"
    return ""
