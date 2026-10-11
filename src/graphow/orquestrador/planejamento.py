"""O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão.

O planejador lê a spec e o código e devolve critérios, decisões, o comando da
suíte e as fatias. O orquestrador confere, escreve `docs/goals/<slug>.md` na
área do Goal, commita e grava o plano. No Goal que veio do gerente, os
critérios e as decisões que o humano fixou ficam com o mesmo id e o mesmo nó.
"""

from collections.abc import Mapping
from typing import Any

from graphow.core.types import PapelAutor
from graphow.orquestrador.briefing import briefing_do_planejador
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, escrever_documento, renderizar_documento
from graphow.orquestrador.esquemas import PAPEL_PLANEJADOR
from graphow.orquestrador.git_do_goal import commitar, descartar_mudancas, restaurar_head
from graphow.orquestrador.gravacao_do_plano import PlanoParaGravar, gravar_plano
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.modelo_do_goal import CAMPO_SPEC
from graphow.orquestrador.saidas import IdsFixados, Plano, conferir_plano
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel
from graphow.orquestrador.spec_do_goal import SpecDoGoal, montar_spec_do_goal


def planejar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """Roda o planejador e grava o plano; a parada diz por que não deu."""
    sem_orcamento = contexto.sem_orcamento()
    if sem_orcamento is not None:
        return sem_orcamento
    fixos = _spec_fixada(contexto, estado)
    head = contexto.git.head()
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_PLANEJADOR,
            id_goal=contexto.id_goal,
            pasta=contexto.area,
            briefing=briefing_do_planejador(estado, str(estado.propriedades.get(CAMPO_SPEC, "")), bool(fixos.nos_fixados)),
            conferir=lambda dados: _conferir(dados, fixos.fixados),
            orcamento_restante_usd=contexto.restante(),
        )
    )
    restaurar_head(contexto.area, contexto.configuracao.ramo, head)
    descartar_mudancas(contexto.area, contexto.patch("planejador"))
    if resposta.dados is None:
        return Parada(contexto.id_goal, MotivoDaParada.FALHA, "O plano nao conferiu: " + "; ".join(resposta.problemas))
    _gravar(contexto, estado, Plano.de_json(resposta.dados), fixos=fixos)
    return None


def _conferir(dados: Mapping[str, Any], fixados: IdsFixados) -> tuple[str, ...]:
    """O sentido do plano, depois do schema."""
    return conferir_plano(Plano.de_json(dados), fixados)


def _spec_fixada(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> SpecDoGoal:
    """No Goal do gerente, os critérios e as decisões que o humano fixou; no da spec, nenhum."""
    goal = contexto.livro.view().obter_no(estado.id_goal)
    if goal is None or goal.proveniencia.papel == PapelAutor.ORQUESTRADOR.value:
        return SpecDoGoal(str(estado.propriedades.get(CAMPO_SPEC, "")))
    return montar_spec_do_goal(contexto.livro.view(), estado.id_goal)


def _gravar(contexto: ContextoDoGoal, estado: EstadoDoGoal, plano: Plano, *, fixos: SpecDoGoal) -> None:
    """O documento do Goal commitado na área e o plano no livro-razão."""
    configuracao = contexto.configuracao
    spec = str(estado.propriedades.get(CAMPO_SPEC, ""))
    documento = renderizar_documento(contexto.id_goal, configuracao, plano, spec=spec)
    escrever_documento(contexto.area, configuracao.slug, documento)
    commit = commitar(contexto.area, f"Planeja o Goal {configuracao.slug}: {plano.titulo}\n\nGoal: {contexto.id_goal} | graphow orquestrar")
    gravar_plano(
        contexto.livro,
        PlanoParaGravar(
            plano=plano,
            slug=configuracao.slug,
            commit_do_documento=commit,
            caminho_do_documento=caminho_do_documento(configuracao.slug),
            nos_fixados=fixos.nos_fixados,
            renomear_goal=not fixos.nos_fixados and _criado_pelo_orquestrador(contexto),
        ),
    )


def _criado_pelo_orquestrador(contexto: ContextoDoGoal) -> bool:
    """O Goal nasceu de uma spec no orquestrador, e o título do plano pode virar o rótulo dele."""
    goal = contexto.livro.view().obter_no(contexto.id_goal)
    return goal is not None and goal.proveniencia.papel == PapelAutor.ORQUESTRADOR.value
