"""A fatia de conflito: no modo autônomo, o rebase que deu conflito, ou deixou vermelho a suíte ou o aceite, vira trabalho do executor.

No supervisionado, o laço para (orquestrador/base_que_andou.py). No autônomo
não há quem resolva, e o orquestrador abre uma fatia no marco final,
`<marco>.R<n>`, com os arquivos em conflito e o diff do conflito no objetivo
(que o briefing do executor mostra inteiro). Sem conflito, quando o vermelho
é o que impede, o alvo são os arquivos do Goal que os testes vermelhos cobrem,
e o que só a base mudou vai no objetivo como contexto: a tentativa que o muda
é recusada, e o executor que só resolve mexendo nele diz isso com `falhou`, e
a fatia vira pendência (revisão da T3g2, G2). Antes de cada tentativa, a área
e o índice recebem a árvore da ponta do Goal com a base nova mesclada
(`merge-tree`, com os marcadores no conflito), fora de commit, e o HEAD fica
onde estava: a tentativa que falha volta a área ao commit, como toda fatia, e
nada se perde. O índice fica na árvore mesclada até o commit, que sai dele
como a conferência (`arvore_da_area`): o arquivo que a base nova rastreia e o
.gitignore ignora chega à branch (revisão da T3g2, G1 e G3).

Nessa fatia, a referência da tentativa é a árvore mesclada, e não o HEAD
antigo do Goal (`referencia_da_fatia`). O selo do `.claude/` e dos CLAUDE.md
volta a ela, que traz o da base nova (orquestrador/trava_do_git.py); as
recusas comparam contra ela, e o que a base trouxe (o aceite de outro Goal, o
conftest do humano) não é da fatia. Depois da sessão, todo arquivo que a base
mudou e o Goal não precisa estar como na base nova: a fatia que desfaz o
trabalho do humano é recusada (`desfaz_a_base`). Nos arquivos que os dois
mudaram, a mudança da base precisa continuar no resultado: `git merge-tree
--merge-base=<base antiga> <base nova> <resultado>` devolve o próprio
resultado, e a fatia que tira dali a linha que a base pôs é recusada com o
arquivo e o que a base poria de volta (revisão da T3g3 e da T3g4, V1). A
suíte e os testes de aceite rodam na área resolvida; o aceite vermelho também
recusa a tentativa (orquestrador/vermelho_do_rebase.py).

O commit da fatia leva o trabalho do Goal inteiro sobre a base nova e os
commits de antes da primeira fatia (o plano e os testes de aceite), refeitos
sobre ela (`antes_das_fatias_sobre`): a história da branch passa a ser a base
nova, esses commits e o da fatia, verde pela suíte da fatia, e o laço segue
com o commit do aceite que tem a base. O livro-razão registra esse rebase como o limpo, antes de as refs
andarem (orquestrador/registro_do_rebase.py, com `fatia_de_conflito`), e as
fatias e os Artifact de antes passam a apontar para o commit dela. O commit
do código muda, a verificação final roda de novo, e o Goal integra por
fast-forward.
"""

from collections.abc import Mapping, Sequence

from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal
from graphow.orquestrador.correcoes import normalizar_caminho
from graphow.orquestrador.documento_do_goal import caminho_do_documento
from graphow.orquestrador.git_do_goal import SEM_ASPAS, FalhaDoGitDoGoal, GitDoGoal, commits_entre
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.livro_razao import aresta
from graphow.orquestrador.rebase_no_clone import (
    ConflitoNoRebase,
    RebaseNoClone,
    arquivos_entre,
    arvore_da_area,
    arvore_mesclada,
    antes_das_fatias_sobre,
    commit_sobre,
    mover_as_refs,
)
from graphow.orquestrador.registro_do_rebase import registrar_o_rebase
from graphow.orquestrador.saida_do_aceite import dentro_do_aceite
from graphow.orquestrador.tipo_da_verificacao import arquivos_por_criterio
from graphow.orquestrador.vermelho_do_rebase import Vermelho, aceite_vermelho

CAMPO_CONFLITO: str = "conflito_com_a_base"
LIMITE_DO_DIFF: int = 6000
MODELO_DO_CONFLITO: str = "opus"
COMO_RESOLVER: str = (
    "Nesta fatia, a area traz o trabalho do Goal com a base nova mesclada, fora de commit: os arquivos em conflito tem os "
    "marcadores <<<<<<< (o lado do Goal), ======= e >>>>>>> (o lado da base). Resolva cada conflito mantendo o que o Goal "
    "entregou e o que a base trouxe, sem regredir criterio nenhum, tire os marcadores e deixe a suite e os testes de aceite "
    "verdes. Nao desfaca a base: o arquivo que a base mudou e o Goal nao fica como na base, e o orquestrador commita a area "
    "sobre ela."
)
COMO_MANTER_A_BASE: str = (
    "O orquestrador recusa a tentativa: mantenha cada linha que a base pos ou tirou, tambem nos arquivos que o Goal e a base "
    "mudaram, e mude so o que e do Goal. A mudanca colada a uma linha da base o git le como conflito com ela: deixe uma "
    "linha intacta entre as duas."
)


def abrir_fatia_de_conflito(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, conflito: ConflitoNoRebase, *, vermelho: Vermelho | None = None
) -> str:
    """A fatia do marco final que resolve o conflito com a base nova; devolve o id da Task."""
    marco = estado.marcos()[-1]
    codigo = f"{marco.id}.R{1 + sum(1 for fatia in estado.fatias if _conflito_da(fatia))}"
    arvore, em_conflito = arvore_mesclada(contexto.area, conflito.antes, conflito.base_depois)
    arquivos = conflito.arquivos or em_conflito or _alvo_sem_conflito(contexto, estado, conflito, vermelho=vermelho)
    propriedades = {
        m.CAMPO_STATUS: m.STATUS_PENDENTE, m.CAMPO_FATIA: codigo, m.CAMPO_MARCO: marco.id, m.CAMPO_TENTATIVAS: 0,
        m.CAMPO_ORDEM: max((fatia.ordem for fatia in estado.fatias), default=0) + 1,
        m.CAMPO_OBJETIVO: _objetivo(contexto, conflito, arvore=arvore, arquivos=arquivos, vermelho=vermelho),
        m.CAMPO_CRITERIOS: _criterios_dos_arquivos(contexto, estado, arquivos), m.CAMPO_ARQUIVOS_ALVO: list(arquivos),
        m.CAMPO_MODELO: MODELO_DO_CONFLITO,
        CAMPO_CONFLITO: {"base": conflito.base_depois, "base_antes": conflito.base_antes, "ponta": conflito.antes,
                         "arquivos": list(arquivos), "motivo": vermelho.motivo if vermelho is not None else "conflito"},
    }
    id_task = m.id_da_fatia(contexto.configuracao.slug, codigo)
    titulo = f"Conflito com a base {contexto.configuracao.base}: " + (", ".join(arquivos[:3]) or "suite vermelha")
    contexto.livro.gravar([*contexto.livro.produzido(id_task, TipoNo.TASK, titulo, propriedades=propriedades),
                           aresta(contexto.id_goal, id_task, TipoAresta.DECOMPOE)], f"Fatia de conflito {codigo} do Goal {contexto.id_goal}")
    return id_task


def _objetivo(
    contexto: ContextoDoGoal, conflito: ConflitoNoRebase, *, arvore: str, arquivos: Sequence[str], vermelho: Vermelho | None
) -> str:
    """O objetivo da fatia: o que o rebase encontrou, como resolver, o diff da ponta do Goal à área mesclada e, no vermelho, o que
    só a base mudou, como contexto."""
    problema = f"{vermelho.resumo}:\n{vermelho.detalhe}" if vermelho is not None else f"deu conflito em {', '.join(arquivos)}."
    da_base = _contexto_da_base(contexto.git, conflito, arvore) if vermelho is not None else ""
    return (f"A base {contexto.configuracao.base} andou para {conflito.base_depois[:12]} desde que a branch do Goal saiu dela, "
            f"e o rebase da branch sobre ela {problema}\n\n{COMO_RESOLVER}{da_base}\n\nO diff do conflito, da ponta do Goal a "
            f"area mesclada:\n```\n{_diff(contexto.git, conflito.antes, arvore, arquivos=arquivos)}\n```")


def _alvo_sem_conflito(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, conflito: ConflitoNoRebase, *, vermelho: Vermelho | None
) -> tuple[str, ...]:
    """Sem arquivo em conflito, o alvo: os arquivos do Goal que os testes vermelhos cobrem; sem eles, os do Goal inteiro.

    O que só a base mudou não é alvo: `desfaz_a_base` recusa a tentativa que
    o muda. O documento do Goal e os testes de aceite também não, porque
    nenhuma fatia os escreve.
    """
    documento = caminho_do_documento(contexto.configuracao.slug)
    do_goal = [caminho for caminho in arquivos_entre(contexto.git, conflito.base_antes, conflito.antes)
               if caminho != documento and not dentro_do_aceite(caminho)]
    por_criterio = arquivos_por_criterio(estado, contexto.git)
    criterios = vermelho.criterios if vermelho is not None else ()
    cobertos = {normalizar_caminho(caminho) for criterio in criterios for caminho in por_criterio.get(criterio, ())}
    return tuple(caminho for caminho in do_goal if normalizar_caminho(caminho) in cobertos) or tuple(do_goal)


def _contexto_da_base(git: GitDoGoal, conflito: ConflitoNoRebase, arvore: str) -> str:
    """No vermelho, o que só a base mudou: não é alvo, e o executor que só resolve mexendo nele devolve `falhou`."""
    so_da_base = _so_da_base(git, conflito.base_depois, conflito.antes)
    if not so_da_base:
        return ""
    return (f"\n\nA base mudou, e o Goal nao, {', '.join(so_da_base)}: e contexto, e nao alvo. Esses arquivos ficam como na "
            "base (a tentativa que os muda e recusada); resolva o vermelho nos arquivos do Goal. Se ele so se resolve mexendo "
            "num deles, nao mexa: devolva `falhou` e diga isso no resumo; a fatia que falha assim vira pendencia, com esse motivo, "
            f"para o humano. O que a base mudou neles:\n```\n{_diff(git, conflito.antes, arvore, arquivos=so_da_base)}\n```")


def _diff(git: GitDoGoal, antes: str, depois: str, *, arquivos: Sequence[str]) -> str:
    """O diff dos arquivos dados, cortado no limite; vazio sem arquivo (sem caminho, o diff seria o da base inteira)."""
    return git.tentar(*SEM_ASPAS, "diff", antes, depois, "--", *arquivos).saida[:LIMITE_DO_DIFF] if arquivos else ""


def _so_da_base(git: GitDoGoal, base: str, ponta: str) -> tuple[str, ...]:
    """Os arquivos que a base mudou desde que a branch do Goal saiu dela e o Goal não mudou."""
    antes = git.rodar("merge-base", ponta, base).strip()
    do_goal = set(arquivos_entre(git, antes, ponta))
    return tuple(caminho for caminho in arquivos_entre(git, antes, base) if caminho not in do_goal)


def _criterios_dos_arquivos(contexto: ContextoDoGoal, estado: EstadoDoGoal, arquivos: Sequence[str]) -> list[str]:
    """Os critérios do plano cujos arquivos estão no conflito."""
    alvo = {normalizar_caminho(caminho) for caminho in arquivos}
    por_criterio = arquivos_por_criterio(estado, contexto.git)
    return [criterio for criterio, seus in por_criterio.items() if alvo & {normalizar_caminho(caminho) for caminho in seus}]


def _conflito_da(fatia: FatiaRegistrada) -> Mapping[str, object] | None:
    """O conflito que a fatia resolve; None na fatia que não é de conflito."""
    conflito = fatia.propriedades.get(CAMPO_CONFLITO)
    return conflito if isinstance(conflito, Mapping) else None


def referencia_da_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str:
    """Contra o que a tentativa se compara: o HEAD; na fatia de conflito, a árvore da ponta do Goal com a base nova mesclada."""
    conflito, head = _conflito_da(fatia), contexto.git.head()
    return head if conflito is None else arvore_mesclada(contexto.area, head, str(conflito.get("base", "")))[0]


def preparar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> str:
    """A referência da tentativa; na fatia de conflito, a área e o índice a recebem, fora de commit, com o HEAD onde estava."""
    referencia = referencia_da_fatia(contexto, fatia)
    if _conflito_da(fatia) is not None:
        contexto.git.rodar("read-tree", "--reset", "-u", referencia)
    return referencia


def desfaz_a_base(contexto: ContextoDoGoal, fatia: FatiaRegistrada, mudados: Sequence[str], *, referencia: str) -> str:
    """Na fatia de conflito, o erro da área que desfaz o que a base nova trouxe; vazio quando a mudança da base continua nela.

    O arquivo que só a base mudou vem dela na árvore mesclada: o que difere
    dela desfaz o que o humano, ou outro Goal, commitou na base. Nos arquivos
    que os dois mudaram, a conferência é a do texto (`_base_fora_do_resultado`).
    """
    conflito = _conflito_da(fatia)
    if conflito is None:
        return ""
    git, base = contexto.git, str(conflito.get("base", ""))
    so_da_base = set(_so_da_base(git, base, git.head()))
    desfeitos = [caminho for caminho in mudados if caminho in so_da_base]
    if not desfeitos:
        return _base_fora_do_resultado(contexto, base, referencia=referencia)
    return (f"a fatia de conflito desfez o que a base nova ({base[:12]}) trouxe em {', '.join(desfeitos)}: a base mudou esses "
            "arquivos e o Goal nao, e eles ficam como na base, porque sao trabalho do humano ou de outro Goal. O orquestrador "
            "recusa a tentativa: resolva so o conflito, sem tocar no que a base mudou fora dele.")


def _base_fora_do_resultado(contexto: ContextoDoGoal, base: str, *, referencia: str) -> str:
    """O erro do resultado de onde saiu parte da mudança da base nova, com os arquivos e o que ela poria de volta; vazio sem.

    `git merge-tree --merge-base=<base antiga> <base nova> <resultado>`
    devolve a própria árvore do resultado quando a mudança da base continua
    nele; o arquivo em que a mescla difere é o de onde a fatia a tirou, como a
    linha que a base pôs num arquivo que os dois mudaram (revisão da T3g3 e
    da T3g4, V1). A base antiga é a de onde a branch do Goal saiu.
    """
    git, head = contexto.git, contexto.git.head()
    antiga = git.rodar("merge-base", head, base).strip()
    em_conflito = frozenset(arvore_mesclada(contexto.area, head, base)[1])
    resultado = arvore_da_area(contexto.area, referencia)
    tirados, diff = _fora_do_resultado(git, resultado, antiga=antiga, base=base, em_conflito=em_conflito)
    if not tirados:
        return ""
    return (f"a fatia aberta pelo rebase tirou do resultado parte do que a base nova ({base[:12]}) trouxe em "
            f"{', '.join(tirados)}: `git merge-tree --merge-base={antiga[:12]} {base[:12]} <resultado>` nao devolve o "
            f"resultado, porque a mudanca da base nesses arquivos nao esta mais nele. {COMO_MANTER_A_BASE} O que a base poria "
            f"de volta no resultado:\n```\n{diff[:LIMITE_DO_DIFF]}\n```")


def _fora_do_resultado(
    git: GitDoGoal, resultado: str, *, antiga: str, base: str, em_conflito: frozenset[str]
) -> tuple[tuple[str, ...], str]:
    """Os arquivos em que a mescla da base nova no resultado difere dele, e o diff do que ela muda.

    Nos arquivos que o rebase deixou em conflito, a resolução difere da base
    por definição: neles a mescla favorece o resultado (`-Xtheirs`) e confere
    só o que a base mudou fora do trecho em conflito.
    """
    tirados: list[str] = []
    diff = ""
    mesclas: list[tuple[tuple[str, ...], bool]] = [((), False), *([(("-Xtheirs",), True)] if em_conflito else [])]
    for opcoes, dos_conflitos in mesclas:
        mescla = _mescla_da_base(git, resultado, antiga=antiga, base=base, opcoes=opcoes)
        aqui = [caminho for caminho in arquivos_entre(git, resultado, mescla) if (caminho in em_conflito) == dos_conflitos]
        tirados += aqui
        diff += _diff(git, resultado, mescla, arquivos=aqui)
    return tuple(tirados), diff


def _mescla_da_base(git: GitDoGoal, resultado: str, *, antiga: str, base: str, opcoes: Sequence[str] = ()) -> str:
    """A árvore da mescla da base nova no resultado, desde a base antiga (no conflito, com os marcadores)."""
    feito = git.tentar(*SEM_ASPAS, "merge-tree", "--write-tree", *opcoes, f"--merge-base={antiga}", base, resultado)
    arvore = feito.saida.split("\n", 1)[0].strip()
    if feito.codigo not in (0, 1) or not arvore:
        raise FalhaDoGitDoGoal("o git nao mesclou a base nova no resultado da fatia", {"base": base[:12], "erro": feito.erro.strip()})
    return arvore


def aceite_da_fatia(contexto: ContextoDoGoal, estado: EstadoDoGoal, fatia: FatiaRegistrada, *, numero: int) -> str:
    """Na fatia de conflito, os testes de aceite na área resolvida: o erro do vermelho, ou vazio; nas outras fatias, vazio."""
    if _conflito_da(fatia) is None:
        return ""
    vermelho = aceite_vermelho(contexto, estado, contexto.patch(f"{fatia.id}-t{numero}-aceite"))
    return "" if vermelho is None else f"a area resolvida {vermelho.resumo}. {vermelho.detalhe}"


def commitar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada, mensagem: str, *, referencia: str) -> str:
    """O commit da fatia; o da de conflito, da árvore que a conferência julgou sobre a referência, vai sobre a base nova e é
    registrado como rebase antes de as refs andarem."""
    conflito = _conflito_da(fatia)
    if conflito is None:
        return contexto.commitar(mensagem, vazio_permitido=True)
    base, git = str(conflito.get("base", "")), contexto.git
    antes = git.head()
    antigos = tuple(reversed(commits_entre(contexto.area, base, antes)))
    pai, refeitos = antes_das_fatias_sobre(contexto.area, base, antigos)
    novo = commit_sobre(contexto.area, mensagem, pai=pai, referencia=referencia)
    feito = RebaseNoClone(git.rodar("merge-base", antes, base).strip(), base, antes, novo,
                          tuple((commit.hash, refeitos.get(commit.hash, novo)) for commit in antigos), arquivos_entre(git, antes, novo))
    registrar_o_rebase(contexto, contexto.estado(), feito, conflito=fatia.id)
    mover_as_refs(contexto.area_do_goal, antes, novo)
    contexto.registrar_ponta()
    return novo
