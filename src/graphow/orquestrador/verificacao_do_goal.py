"""O fim de cada marco: a verificação dele, as fatias de correção e, no último, o fechamento do Goal.

Com as fatias do marco concluídas, o marco é verificado por uma sessão nova
do verificador (orquestrador/verificacao_do_marco.py). Os Achados bloqueantes
viram fatias de correção do marco, os do mesmo arquivo juntos numa fatia só,
até dois ciclos por marco. O marco segue quando a verificação dele sai limpa;
o marco intermediário que esgota os ciclos também segue, com os bloqueantes
abertos, para que os marcos seguintes rodem. O último marco é a verificação
final, sobre o Goal inteiro: ela cobra de novo os bloqueantes que os outros
marcos deixaram, com os ciclos dela, e só esgotados esses o laço para. O Goal
só fecha quando não há bloqueante aberto e a verificação final limpa vale
para o commit atual: a verificação foi feita no commit do código da
ponta da branch (o commit que só mudou o documento do Goal não conta). O
kernel recusa o fechamento que não tiver essa prova. No modo autônomo o
orquestrador integra por fast-forward na base e fecha; no supervisionado,
para com "pronto para integrar", e a chamada seguinte vê a branch integrada e
fecha.

O documento é sincronizado com as pendências a cada passo depois da
verificação, e por isso a queda entre o lote e o commit do documento não perde
acompanhamento.
"""

from collections.abc import Sequence
from pathlib import Path

from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.git_do_goal import FalhaDoGitDoGoal, GitDoGoal, integrar_por_fast_forward, remover_area
from graphow.orquestrador.leitura_das_verificacoes import AchadoRegistrado
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, MarcoRegistrado, VerificacaoRegistrada
from graphow.orquestrador.verificacao_do_marco import sincronizar_documento, verificar_marco


def verificar_ou_fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada | None:
    """Com as fatias do marco concluídas: verifica o commit atual, abre correções, segue ao próximo marco ou fecha."""
    verificacoes = estado.verificacoes_do_marco(marco)
    ultima = verificacoes[-1] if verificacoes else None
    if ultima is None or not _vale_para_o_commit_atual(contexto, ultima) or _ja_corrigida(estado, ultima):
        return verificar_marco(contexto, estado, marco)
    sincronizar_documento(contexto, estado.pendencias, numero=len(estado.verificacoes))
    carregados = estado.bloqueantes_de_outros_marcos(marco) if marco.final else ()
    if ultima.limpa and not carregados:
        return _fechar(contexto, estado, marco) if marco.final else None
    return _corrigir(contexto, estado, ultima, marco=marco)


def _vale_para_o_commit_atual(contexto: ContextoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação foi feita no commit do código atual: o que veio depois dela só mexeu no documento do Goal.

    É a mesma conta que o kernel faz contra a ponta da branch gravada no Goal
    (kernel/fechamento_do_goal.py); a verificação de antes da fase 2, sem o
    commit do código, não vale mais e é refeita.
    """
    return bool(verificacao.commit_do_codigo) and verificacao.commit_do_codigo == contexto.commit_do_codigo()


def _ja_corrigida(estado: EstadoDoGoal, verificacao: VerificacaoRegistrada) -> bool:
    """A verificação já teve as correções dela (as dos bloqueantes dela e, na final, as dos que ela cobrou), todas concluídas."""
    correcoes = [fatia for fatia in estado.fatias if fatia.texto(m.CAMPO_CORRIGE) == verificacao.id]
    return bool(correcoes) and all(f.status == m.STATUS_CONCLUIDO for f in correcoes)


def _corrigir(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, ultima: VerificacaoRegistrada, *, marco: MarcoRegistrado
) -> Parada | None:
    """Os bloqueantes (na final, também os dos outros marcos) viram fatias de correção enquanto o marco tiver ciclo.

    Sem ciclo, o marco intermediário segue (o laço vai ao marco seguinte), e a
    final para: não há mais o que executar.
    """
    bloqueantes = (*ultima.bloqueantes_abertos(), *(estado.bloqueantes_de_outros_marcos(marco) if marco.final else ()))
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


def _fechar(contexto: ContextoDoGoal, estado: EstadoDoGoal, marco: MarcoRegistrado) -> Parada:
    """Integra no modo autônomo, ou espera o humano integrar no supervisionado; fecha quando integrado.

    A verificação final que ficou limpa porque o humano descartou o
    bloqueante dela não resolveu, ao ser gravada, os achados que as correções
    tinham entregue: eles se resolvem agora, confirmados por ela.
    """
    contexto.livro.resolver(estado.corrigidos(marco), f"Achados corrigidos confirmados pela verificacao final do Goal {contexto.id_goal}")
    configuracao = contexto.configuracao
    repositorio = Path(configuracao.repositorio)
    head = contexto.git.head()
    andou = _branch_andou(repositorio, configuracao.ramo, head)
    if andou:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, andou)
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


def _fechar_integrado(contexto: ContextoDoGoal, integrado: str) -> Parada:
    """Fecha o Goal e tira a área de trabalho, que já cumpriu o papel."""
    contexto.livro.fechar(integrado)
    removida = remover_area(contexto.area)
    sobra = "" if removida else f" A area {contexto.area} ficou no disco (o git nao a removeu)."
    return Parada(contexto.id_goal, MotivoDaParada.FECHADO, f"Goal fechado: {contexto.configuracao.base} em {integrado[:12]}.{sobra}")
