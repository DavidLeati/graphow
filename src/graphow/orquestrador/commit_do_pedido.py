"""O commit do pedido do humano: só os caminhos que o pedido escreveu, e nunca a área inteira.

O pedido (retirar critério, recusar o plano, refazer o aceite) commitava com
`git add -A`, e o que a área tivesse fora de commit ia junto. Na sonda 2 da
revisão da T2i+T2g, a fatia caiu no meio da sessão do executor, e o commit
da retirada levou o trabalho pela metade, um conftest.py com
`pytest_pyfunc_call` inclusive; a tentativa seguinte, comparando com o
próprio HEAD, não o recusava, e no modo autônomo ele chegava à base. Agora
o commit leva só o que o pedido escreveu: o documento do Goal na retirada e
`aceite/` na recusa do plano (que o tira) e no refazer (que o reescreve). O
resto fica fora do commit, para quem é dono dele: a fatia interrompida o
guarda no .patch dela antes do pedido (orquestrador/execucao_da_fatia.py).
"""

from collections.abc import Sequence
from pathlib import Path

from graphow.orquestrador.git_do_goal import IDENTIDADE_DE_RESERVA, GitDoGoal


def commitar_so(area: Path, mensagem: str, caminhos: Sequence[str], *, vazio_permitido: bool = False) -> str:
    """Só o que mudou nos caminhos dados, num commit do orquestrador; o resto da área fica fora dele. Devolve o hash.

    `git commit --only` leva o que está na árvore nesses caminhos e ignora o
    que o índice tem nos outros. O caminho que o git não conhece (nem na
    árvore, nem no índice, nem no HEAD), como o `aceite/` de um plano só de
    checagens, sai do pathspec, que o git recusaria; sem caminho conhecido, o
    commit sai vazio, quando vale. O `git add` só apresenta ao git o arquivo
    novo: com o caminho que o .gitignore ignora, ele sai com erro e adiciona
    o resto mesmo assim (o ignorado de `aceite/` já foi forçado ao índice).
    """
    git = GitDoGoal(area)
    no_disco = [caminho for caminho in caminhos if (area / caminho).exists()]
    if no_disco:
        git.tentar("add", "--", *no_disco)
    conhecidos = [caminho for caminho in caminhos
                  if git.tentar("ls-files", "--error-unmatch", "--with-tree=HEAD", "--", caminho).codigo == 0]
    identidade = () if git.tentar("config", "user.email").saida.strip() else IDENTIDADE_DE_RESERVA
    vazio = ["--allow-empty"] if vazio_permitido else []
    git.rodar(*identidade, "commit", "-q", "--only", *vazio, "-m", mensagem, *(["--", *conhecidos] if conhecidos else []))
    return git.head()
