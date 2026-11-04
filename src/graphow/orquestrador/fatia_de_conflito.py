"""A fatia de conflito: no modo autônomo, o rebase que deu conflito, ou deixou a suíte vermelha, vira trabalho do executor.

No supervisionado, o laço para (orquestrador/base_que_andou.py). No autônomo
não há quem resolva, e o orquestrador abre uma fatia no marco final,
`<marco>.R<n>`, com os arquivos em conflito e o diff do conflito no objetivo
(que o briefing do executor mostra inteiro). Antes de cada tentativa, a área
recebe a árvore da ponta do Goal com a base nova mesclada (`merge-tree`, com
os marcadores no conflito), fora de commit, e o HEAD fica onde estava: a
tentativa que falha volta a área ao commit, como toda fatia, e nada se perde.

O commit da fatia tem a base nova como pai e leva o trabalho do Goal inteiro:
a história da branch passa a ser a base nova e esse commit, verde pela suíte
da fatia. O livro-razão registra esse rebase como o limpo, antes de as refs
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
from graphow.orquestrador.git_do_goal import SEM_ASPAS, commits_entre
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, FatiaRegistrada
from graphow.orquestrador.livro_razao import aresta
from graphow.orquestrador.rebase_no_clone import (
    ConflitoNoRebase,
    RebaseNoClone,
    arquivos_entre,
    arvore_mesclada,
    commit_sobre,
    mover_as_refs,
)
from graphow.orquestrador.registro_do_rebase import registrar_o_rebase
from graphow.orquestrador.suite import ResultadoDaSuite
from graphow.orquestrador.tipo_da_verificacao import arquivos_por_criterio

CAMPO_CONFLITO: str = "conflito_com_a_base"
LIMITE_DO_DIFF: int = 6000
MODELO_DO_CONFLITO: str = "opus"
COMO_RESOLVER: str = (
    "Nesta fatia, a area traz o trabalho do Goal com a base nova mesclada, fora de commit: os arquivos em conflito tem os "
    "marcadores <<<<<<< (o lado do Goal), ======= e >>>>>>> (o lado da base). Resolva cada conflito mantendo o que o Goal "
    "entregou e o que a base trouxe, sem regredir criterio nenhum, tire os marcadores e deixe a suite verde. Nao desfaca a "
    "base: o orquestrador commita a area sobre ela."
)


def abrir_fatia_de_conflito(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, conflito: ConflitoNoRebase, *, suite: ResultadoDaSuite | None = None
) -> str:
    """A fatia do marco final que resolve o conflito com a base nova; devolve o id da Task."""
    marco = estado.marcos()[-1]
    codigo = f"{marco.id}.R{1 + sum(1 for fatia in estado.fatias if _conflito_da(fatia))}"
    arvore, em_conflito = arvore_mesclada(contexto.area, conflito.antes, conflito.base_depois)
    arquivos = conflito.arquivos or em_conflito or arquivos_entre(contexto.git, conflito.base_antes, conflito.base_depois)
    propriedades = {
        m.CAMPO_STATUS: m.STATUS_PENDENTE, m.CAMPO_FATIA: codigo, m.CAMPO_MARCO: marco.id, m.CAMPO_TENTATIVAS: 0,
        m.CAMPO_ORDEM: max((fatia.ordem for fatia in estado.fatias), default=0) + 1,
        m.CAMPO_OBJETIVO: _objetivo(contexto, conflito, arvore=arvore, arquivos=arquivos, suite=suite),
        m.CAMPO_CRITERIOS: _criterios_dos_arquivos(contexto, estado, arquivos), m.CAMPO_ARQUIVOS_ALVO: list(arquivos),
        m.CAMPO_MODELO: MODELO_DO_CONFLITO,
        CAMPO_CONFLITO: {"base": conflito.base_depois, "base_antes": conflito.base_antes, "ponta": conflito.antes,
                         "arquivos": list(arquivos), "motivo": "suite_vermelha" if suite is not None else "conflito"},
    }
    id_task = m.id_da_fatia(contexto.configuracao.slug, codigo)
    titulo = f"Conflito com a base {contexto.configuracao.base}: " + (", ".join(arquivos[:3]) or "suite vermelha")
    contexto.livro.gravar([*contexto.livro.produzido(id_task, TipoNo.TASK, titulo, propriedades=propriedades),
                           aresta(contexto.id_goal, id_task, TipoAresta.DECOMPOE)], f"Fatia de conflito {codigo} do Goal {contexto.id_goal}")
    return id_task


def _objetivo(
    contexto: ContextoDoGoal, conflito: ConflitoNoRebase, *, arvore: str, arquivos: Sequence[str], suite: ResultadoDaSuite | None
) -> str:
    """O objetivo da fatia: o que o rebase encontrou, como resolver e o diff da ponta do Goal à área mesclada."""
    diff = contexto.git.tentar(*SEM_ASPAS, "diff", conflito.antes, arvore, "--", *arquivos).saida[:LIMITE_DO_DIFF]
    problema = f"deixou a suite vermelha:\n{suite.descrever()}" if suite is not None else f"deu conflito em {', '.join(arquivos)}."
    return (f"A base {contexto.configuracao.base} andou para {conflito.base_depois[:12]} desde que a branch do Goal saiu dela, "
            f"e o rebase da branch sobre ela {problema}\n\n{COMO_RESOLVER}\n\nO diff do conflito, da ponta do Goal a area "
            f"mesclada:\n```\n{diff}\n```")


def _criterios_dos_arquivos(contexto: ContextoDoGoal, estado: EstadoDoGoal, arquivos: Sequence[str]) -> list[str]:
    """Os critérios do plano cujos arquivos estão no conflito."""
    alvo = {normalizar_caminho(caminho) for caminho in arquivos}
    por_criterio = arquivos_por_criterio(estado, contexto.git)
    return [criterio for criterio, seus in por_criterio.items() if alvo & {normalizar_caminho(caminho) for caminho in seus}]


def _conflito_da(fatia: FatiaRegistrada) -> Mapping[str, object] | None:
    """O conflito que a fatia resolve; None na fatia que não é de conflito."""
    conflito = fatia.propriedades.get(CAMPO_CONFLITO)
    return conflito if isinstance(conflito, Mapping) else None


def preparar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada) -> None:
    """Na fatia de conflito, a área recebe a ponta do Goal com a base nova mesclada, fora de commit; nas outras, nada."""
    conflito = _conflito_da(fatia)
    if conflito is None:
        return
    arvore, _ = arvore_mesclada(contexto.area, contexto.git.head(), str(conflito.get("base", "")))
    contexto.git.rodar("read-tree", "--reset", "-u", arvore)
    contexto.git.rodar("reset", "-q")


def commitar_a_fatia(contexto: ContextoDoGoal, fatia: FatiaRegistrada, mensagem: str) -> str:
    """O commit da fatia; o da fatia de conflito vai sobre a base nova, registrado como rebase antes de as refs andarem."""
    conflito = _conflito_da(fatia)
    if conflito is None:
        return contexto.commitar(mensagem, vazio_permitido=True)
    base, git = str(conflito.get("base", "")), contexto.git
    antes = git.head()
    novo = commit_sobre(contexto.area, mensagem, pai=base)
    antigos = tuple(reversed(commits_entre(contexto.area, base, antes)))
    feito = RebaseNoClone(git.rodar("merge-base", antes, base).strip(), base, antes, novo,
                          tuple((commit.hash, novo) for commit in antigos), arquivos_entre(git, antes, novo))
    registrar_o_rebase(contexto, contexto.estado(), feito, conflito=fatia.id)
    mover_as_refs(contexto.area_do_goal, antes, novo)
    contexto.registrar_ponta()
    return novo
