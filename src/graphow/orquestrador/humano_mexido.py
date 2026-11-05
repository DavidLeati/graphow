"""O que a conferência achou no repositório do humano, e como a parada e a Note o dizem.

A conferência (orquestrador/conferencia_do_humano.py) separa a perda do
avanço e devolve um `HumanoMexido`: as duas listas, a salvaguarda de antes, os
não rastreados que sumiram e o que rodou enquanto o repositório mudou
(`Durante`, que a janela da foto põe: orquestrador/janela_do_humano.py). A
perda para o laço em FALHA (`RepositorioDoHumanoMexido`) com a mensagem desta
página: o que se perdeu, a salvaguarda, os comandos que a recuperam e quem
pode ter mexido. Quando quem mudou o que se perdeu foi só o código que o
agente escreveu e o orquestrador rodou fora da sessão (um teste de aceite, a
suíte), a mensagem diz isso, e não que foi a sessão.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.orquestrador.salvaguarda_do_humano import Salvaguarda, comandos_de_recuperacao

MOTIVO_DA_PARADA: str = "repositorio_do_humano_mexido"
LIMITE_DE_MUDANCAS_NA_PARADA: int = 20


@dataclass(frozen=True)
class Durante:
    """O que rodou enquanto o repositório mudou: o texto da parada e da Note; se foi só o código do agente que o orquestrador
    rodou fora da sessão, e as sessões da janela que não mexeram no que mudou."""

    texto: str = ""
    fora_da_sessao: bool = False
    sessoes: str = ""


@dataclass(frozen=True)
class HumanoMexido:
    """O que mudou no repositório do humano durante a janela, separado em perda e avanço, e a salvaguarda de antes dela.

    `soltos_perdidos` são os não rastreados que sumiram, os que a árvore da salvaguarda devolve; `git_mexido` diz que um
    arquivo que muda o git mudou, e `arvore_conferida`, que a foto de depois rodou (não roda quando aquele mudou);
    `cabeca_de_antes`, o HEAD de antes da sessão quando ela o trocou ou pôs o conteúdo de outro commit na árvore ou no
    índice: o `stash apply` vale sobre ele.
    """

    repositorio: Path
    perdas: tuple[str, ...]
    avancos: tuple[str, ...]
    salvaguarda: Salvaguarda
    soltos_perdidos: tuple[str, ...] = ()
    git_mexido: bool = False
    arvore_conferida: bool = True
    cabeca_de_antes: str = ""
    durante: Durante = Durante()

    @property
    def recuperar(self) -> tuple[str, ...]:
        """Os comandos que devolvem o de antes da sessão: o `fetch` da pasta da salvaguarda, o `stash apply` do rastreado e o
        `restore` do não rastreado."""
        return comandos_de_recuperacao(self.repositorio, self.salvaguarda, self.soltos_perdidos)

    def durante_o(self, papel: str) -> str:
        """O que rodou enquanto o repositório mudou; sem o que a janela disse, a sessão do papel."""
        return self.durante.texto or f"a sessao do {papel}"


# Quem guarda no livro-razão o repositório do humano que mudou: o papel, a fatia (vazia fora delas) e o que mudou.
RegistroDoHumanoMexido = Callable[[str, str, HumanoMexido], None]


class RepositorioDoHumanoMexido(GraphowError):
    """O repositório do humano perdeu trabalho durante a sessão de papel, ou o código do agente que o orquestrador rodou: o
    laço para em FALHA."""


def resumo(mudancas: tuple[str, ...]) -> tuple[str, ...]:
    """As primeiras mudanças e quantas sobram."""
    sobra = len(mudancas) - LIMITE_DE_MUDANCAS_NA_PARADA
    return (*mudancas[:LIMITE_DE_MUDANCAS_NA_PARADA], *([f"e mais {sobra}"] if sobra > 0 else []))


def mensagem_da_parada(mexido: HumanoMexido, papel: str) -> str:
    """O motivo, o que rodou, a perda, a salvaguarda, os comandos que a recuperam e quem pode ter mexido."""
    partes = ([f"o commit {mexido.salvaguarda.stash} (as mudancas rastreadas)"] if mexido.salvaguarda.stash else []) + (
        [f"a arvore {mexido.salvaguarda.soltos} (os nao rastreados)"] if mexido.salvaguarda.soltos and mexido.soltos_perdidos else [])
    recuperar = ", depois ".join(f"`{comando}`" for comando in mexido.recuperar)
    voltar = (f" A sessao trocou o HEAD ou pos na arvore o conteudo de outro commit: o `stash apply` vale sobre o HEAD de antes "
              f"({mexido.cabeca_de_antes}), com a arvore e o indice iguais a ele; volte a ele antes."
              if mexido.cabeca_de_antes and mexido.salvaguarda.stash else "")
    salvaguarda = (f"A salvaguarda de antes da sessao e {' e '.join(partes)}, guardada fora do repositorio, em "
                   f"{mexido.salvaguarda.pasta}: recupere com {recuperar}.{voltar}" if partes
                   else "Antes da sessao nao havia o que salvaguardar desses arquivos.")
    return (f"{MOTIVO_DA_PARADA}: o repositorio do humano ({mexido.repositorio}) "
            f"{'teve mudado o que o git roda' if mexido.git_mexido else 'perdeu trabalho'} durante {mexido.durante_o(papel)}: "
            f"{'; '.join(resumo(mexido.perdas))}. {salvaguarda}{_aviso_do_git(mexido)} Se foi voce quem mexeu nesse meio tempo, "
            f"confira e rode o Goal de novo; se nao, {_quem_mexeu(mexido.durante)} mexeu fora do clone do Goal, e o que foi feito "
            "la nao foi desfeito.")


def _quem_mexeu(durante: Durante) -> str:
    """Quem mexeu, se não foi o humano: a sessão, ou o código do agente que o orquestrador rodou fora dela."""
    if not durante.fora_da_sessao:
        return "a sessao"
    return "o codigo que o agente escreveu, rodado pelo orquestrador fora da sessao" + (
        f", e nao {durante.sessoes}," if durante.sessoes else "")


def _aviso_do_git(mexido: HumanoMexido) -> str:
    """O aviso dos arquivos que mudam o git: sem salvaguarda, e antes de qualquer git no repositório, inclusive a recuperação."""
    if not mexido.git_mexido:
        return ""
    conferida = "" if mexido.arvore_conferida else (" A conferencia parou antes de rodar git nesse repositorio: a arvore e o "
                                                     "indice nao foram conferidos.")
    return (f"{conferida} Os arquivos que mudam o que o git roda nao tem salvaguarda: confira-os e desfaca a mudanca antes de "
            "rodar qualquer git nesse repositorio, inclusive os comandos de recuperacao, que rodariam o que foi plantado.")
