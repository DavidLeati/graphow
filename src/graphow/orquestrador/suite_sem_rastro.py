"""A suíte que o orquestrador roda não deixa rastro na área: o que ela escreve nunca entra num commit do laço.

As recusas por código (a sombra do runner, o hook do pytest no conftest.py, o
que mexe em `aceite/`) olham a área antes da suíte, e o commit da fatia fazia
`git add -A` depois dela. Na sonda L2 da revisão da T2k+T2l, um
`verificar.py` que gerava um conftest.py com `pytest_pyfunc_call` o levava à
base sem recusa, no commit da fatia e no "Registra as pendencias"; na K4, a
suíte que reescrevia um arquivo a cada rodada o punha em cada commit, e o
arquivo passava a contar como de critério e como código.

Agora a árvore que as recusas conferiram é guardada antes da suíte (um
`git write-tree`, sem mudar o HEAD) e, depois dela, a área volta a ela: o que
a suíte criou ou mudou vai a um .patch, para quem quiser ver, e sai da área.
Os arquivos ignorados pelo git ficam como estão (dependências instaladas,
caches): não entram em commit nenhum.

O índice volta ao que era, e não ao HEAD (revisão da T3g2, G1 e G3): é ele
que diz o que está rastreado. O arquivo que a referência rastreia e o
.gitignore ignora (o `.claude/settings.json` que o humano commitou com
`git add -f`) só segue no `git add -A` enquanto está no índice. Na fatia de
conflito, o índice é a árvore mesclada, que o HEAD antigo do Goal não tem: o
`reset` o tirava dali, e o commit levava outra árvore que a conferida.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from graphow.orquestrador.git_do_goal import GitDoGoal


@contextmanager
def sem_o_que_a_suite_escreve(area: Path, arquivo_patch: Path) -> Iterator[None]:
    """Guarda a árvore da área antes do bloco e a devolve depois dele, com o que o bloco escreveu no .patch dado."""
    indice = GitDoGoal(area).rodar("write-tree").strip()
    arvore = guardar_a_arvore(area)
    try:
        yield
    finally:
        voltar_a_arvore(area, arvore, arquivo_patch, indice=indice)


def guardar_a_arvore(area: Path) -> str:
    """O hash da árvore da área como está, os arquivos novos inclusive; o índice fica como estava."""
    git = GitDoGoal(area)
    indice = git.rodar("write-tree").strip()
    git.rodar("add", "-A")
    arvore = git.rodar("write-tree").strip()
    git.rodar("read-tree", "--reset", indice)
    return arvore


def voltar_a_arvore(area: Path, arvore: str, arquivo_patch: Path, *, indice: str) -> bool:
    """A área de volta à árvore dada, sem tocar nos ignorados, e o índice ao dado; o que mudou vai ao .patch. Diz se havia o que desfazer."""
    git = GitDoGoal(area)
    git.rodar("read-tree", "--reset", indice)
    git.rodar("add", "-A")
    mudou = git.rodar("write-tree").strip() != arvore
    if mudou:
        arquivo_patch.parent.mkdir(parents=True, exist_ok=True)
        arquivo_patch.write_bytes(git.bytes_de("diff", "--cached", "--binary", arvore))
        git.rodar("read-tree", "--reset", "-u", arvore)
        git.rodar("clean", "-q", "-fd")
    git.rodar("read-tree", "--reset", indice)
    return mudou
