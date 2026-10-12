"""O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal.

Com as fatias do marco concluídas, o marco é verificado por uma sessão nova
do verificador (orquestrador/verificacao_do_marco.py). Cada Achado bloqueante
vira fatia de correção do marco, até dois ciclos por marco; esgotado o
limite, o laço para com o motivo, e os bloqueantes seguem abertos. O marco
segue quando a verificação dele sai limpa; o último marco é a verificação
final, sobre o Goal inteiro, e o Goal só fecha quando ela não tem bloqueante
e vale para o commit atual: a verificação foi feita no commit do código da
ponta da branch (o commit que só mudou o documento do Goal não conta). O
kernel recusa o fechamento que não tiver essa prova. No modo autônomo o
orquestrador integra por fast-forward na base e fecha; no supervisionado,
para com "pronto para integrar", e a chamada seguinte vê a branch integrada e
fecha.

O documento é sincronizado com as pendências a cada passo depois da
verificação, e por isso a queda entre o lote e o commit do documento não perde
acompanhamento.
"""

from pathlib import Path

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import MAXIMO_DE_CICLOS_DE_CORRECAO, ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.git_do_goal import FalhaDoGitDoGoal, GitDoGoal, integrar_por_fast_forward, remover_area
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado, VerificacaoRegistrada
from graphow.orquestrador.verificacao_do_marco import sincronizar_documento, verificar_marco


def verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Com as fatias do marco concluídas: verifica o commit atual, abre correções, segue ao próximo marco ou fecha."""
    verificacoes = estado.verificacoes_do_marco(marco)
    ultima = verificacoes[-1] if verificacoes else None
    if ultima is None or not _vale_para_o_commit_atual(contexto, ultima) or _ja_corrigida(estado, ultima):
        return verificar_marco(contexto, estado, marco)
    sincronizar_documento(contexto, estado.pendencias, numero=len(estado.verificacoes))
    if ultima.limpa:
        return _fechar(contexto) if marco.final else None
    return _corrigir(contexto, estado, ultima, marco=marco)


def _vale_para_o_commit_atual(contexto: ContextoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação foi feita no commit do código atual: o que veio depois dela só mexeu no documento do Goal.

    É a mesma conta que o kernel faz contra a ponta da branch gravada no Goal
    (kernel/fechamento_do_goal.py); a verificação de antes da fase 2, sem o
    commit do código, não vale mais e é refeita.
    """
    return bool(verificacao.commit_do_codigo) and verificacao.commit_do_codigo == contexto.commit_do_codigo()


def _ja_corrigida(estado: EstadoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação rejeitada já teve as correções dela, todas concluídas: verificar de novo."""
    correcoes = [fatia for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == verificacao.id]
    return not verificacao.limpa and bool(correcoes) and all(f.status == m.STATUS_CONCLUIDO for f in correcoes)


def _corrigir(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, ultima: VerificacaoRegistrada, *, marco: MarcoRegistrado
) -> Parada | None:
    """Os bloqueantes viram fatias de correção do marco, enquanto ele tiver ciclo; sem ciclo, o laço para."""
    bloqueantes = ultima.bloqueantes()
    ciclos = estado.ciclos_do_marco(marco)
    if ciclos >= MAXIMO_DE_CICLOS_DE_CORRECAO:
        titulos = "; ".join(achado.texto("titulo") for achado in bloqueantes)
        return Parada(
            contexto.id_goal,
            MotivoDaParada.BLOQUEANTES_RESTANTES,
            f"Depois de {MAXIMO_DE_CICLOS_DE_CORRECAO} ciclos de correcao no marco {marco.id}, a verificacao {ultima.id} ainda tem "
            f"{len(bloqueantes)} bloqueante(s): {titulos}. Eles seguem como Achados abertos e nas pendencias do Goal; "
            "o Goal fica aberto, e o kernel nao o fecha enquanto houver bloqueante aberto.",
        )
    ordem = max((fatia.ordem for fatia in estado.fatias), default=0)
    contexto.livro.criar_correcoes(ultima.id, bloqueantes, ciclo=ciclos + 1, ordem=ordem, marco=marco.id)
    return None


def _fechar(contexto: ContextoDoGoal) -> Parada:
    """Integra no modo autônomo, ou espera o humano integrar no supervisionado; fecha quando integrado."""
    configuracao = contexto.configuracao
    repositorio = Path(configuracao.repositorio)
    head = contexto.git.head()
    if configuracao.modo == m.MODO_AUTONOMO:
        try:
            integrado = integrar_por_fast_forward(repositorio, configuracao.ramo, configuracao.base)
        except FalhaDoGitDoGoal as erro:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA, f"A integracao nao foi possivel: {erro.formatar_para_llm()}")
        return _fechar_integrado(contexto, integrado)
    if GitDoGoal(repositorio).e_ancestral(head, configuracao.base):
        return _fechar_integrado(contexto, GitDoGoal(repositorio).rodar("rev-parse", configuracao.base).strip())
    return Parada(
        contexto.id_goal,
        MotivoDaParada.PRONTO_PARA_INTEGRAR,
        f"Pronto para integrar: a verificacao limpa vale para {head[:12]}. Integre com "
        f"`git -C \"{repositorio}\" merge --ff-only {configuracao.ramo}` (na base {configuracao.base}) e rode de novo para fechar.",
    )


def _fechar_integrado(contexto: ContextoDoGoal, integrado: str) -> Parada:
    """Fecha o Goal e tira a área de trabalho, que já cumpriu o papel."""
    contexto.livro.fechar(integrado)
    removida = remover_area(contexto.area)
    sobra = "" if removida else f" A area {contexto.area} ficou no disco (o git nao a removeu)."
    return Parada(contexto.id_goal, MotivoDaParada.FECHADO, f"Goal fechado: {contexto.configuracao.base} em {integrado[:12]}.{sobra}")
