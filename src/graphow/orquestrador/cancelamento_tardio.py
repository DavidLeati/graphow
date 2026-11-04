"""O cancelamento tardio: o humano cancela o Goal quando a base já tem o trabalho dele, e o livro-razão guarda isso.

Logo antes de integrar, o laço relê o Goal (orquestrador/verificacao_do_goal.py):
o cancelamento que chegou no meio do passo impede o fast-forward. Da releitura
ao fast-forward ainda há uma janela. O cancelamento que cai nela não impede a
integração, mas não some: a releitura de logo depois grava, numa Evidence que
deriva do Goal (ancorada no commit integrado) e na nota `cancelamento_tardio`
do Goal (só do orquestrador, no kernel), que a base já tinha o Goal quando o
cancelamento foi lido. O orquestrador não fecha o Goal por cima do
cancelamento do humano: ele fica cancelado.

O processo que cai logo depois do fast-forward, com o cancelamento chegando
nesse intervalo, não chega à releitura (revisão da T3g3, T3). A execução
seguinte, que para em `cancelado` no começo do laço, antes confere se a ponta
do Goal que o livro-razão guarda, um commit do orquestrador para ele, já está
na base do repositório do humano. Se está e a nota ainda não existe, grava a
mesma nota, e só então para.
"""

from collections.abc import Mapping
from pathlib import Path

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import MotivoDaParada, Parada
from graphow.orquestrador.git_do_goal import TRAILER_DO_GOAL, GitDoGoal
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta, propriedade

ACAO_DO_CANCELAMENTO_TARDIO: str = "cancelamento_tardio"


def anotar_o_cancelamento_tardio(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, *, integrado: str, texto: str) -> Parada:
    """A Evidence e a nota no Goal de que a base já tinha o trabalho dele, até `integrado`, quando o cancelamento foi lido."""
    configuracao, id_goal = estado.configuracao, livro.id_goal
    base = configuracao.base if configuracao is not None else ""
    motivo = str(estado.propriedades.get(a.CAMPO_MOTIVO_DO_CANCELAMENTO, ""))
    id_nota, rotulo = f"cancelamento-tardio-{id_goal}", f"Cancelamento do Goal {id_goal} depois da integracao"
    nota = {"acao": ACAO_DO_CANCELAMENTO_TARDIO, "base": base, m.CAMPO_COMMIT: integrado, "motivo": motivo, "texto": texto}
    livro.gravar([*livro.produzido(id_nota, TipoNo.EVIDENCE, rotulo, propriedades=nota),
                  aresta(id_nota, id_goal, TipoAresta.DERIVA_DE),
                  propriedade(id_goal, a.CAMPO_CANCELAMENTO_TARDIO, {"evidencia": id_nota, "integrado": integrado, "texto": texto})],
                 rotulo)
    return Parada(id_goal, MotivoDaParada.CANCELADO,
                  f"O Goal {id_goal} foi cancelado tarde ({motivo}): o cancelamento chegou quando a base {base} ja tinha o "
                  f"trabalho dele, em {integrado[:12]}. O Goal fica cancelado, com a nota ({id_nota}). Para tirar o trabalho "
                  f"dele da base: `git revert` dos commits do Goal em {base}.")


def cancelamento_ja_integrado(livro: LivroRazaoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """No Goal cancelado, a nota que a queda logo depois do fast-forward não deixou gravar; None quando não há o que anotar.

    Só anota a ponta gravada no livro-razão que é um commit do orquestrador
    para este Goal (o trailer `Graphow-Goal`) e que está na história da base:
    o Goal cancelado antes do primeiro commit tem a ponta na base, e nada
    dele chegou lá.
    """
    configuracao, ponta = estado.configuracao, estado.propriedades.get(a.CAMPO_PONTA_DO_RAMO)
    commit = str(ponta.get(m.CAMPO_COMMIT, "")) if isinstance(ponta, Mapping) else ""
    if configuracao is None or not commit or estado.propriedades.get(a.CAMPO_CANCELAMENTO_TARDIO):
        return None
    if not _commit_do_goal_na_base(Path(configuracao.repositorio), commit, base=configuracao.base, id_goal=livro.id_goal):
        return None
    texto = (f"Na retomada, o Goal estava cancelado e a base {configuracao.base} ja tinha a ponta dele ({commit[:12]}): o "
             "trabalho do Goal chegou a base antes de o cancelamento ser lido (o fast-forward da execucao que caiu logo "
             "depois dele, ou uma integracao por fora do orquestrador).")
    return anotar_o_cancelamento_tardio(livro, estado, integrado=commit, texto=texto)


def _commit_do_goal_na_base(repositorio: Path, commit: str, *, base: str, id_goal: str) -> bool:
    """O commit é do orquestrador para o Goal (trailer `Graphow-Goal`) e está na história da base do repositório do humano."""
    git = GitDoGoal(repositorio)
    trailers = git.tentar("log", "-1", f"--format=%(trailers:key={TRAILER_DO_GOAL},valueonly,unfold)", commit, "--")
    do_goal = trailers.codigo == 0 and id_goal in (linha.strip() for linha in trailers.saida.splitlines())
    return do_goal and git.e_ancestral(commit, f"refs/heads/{base}")
