"""O passo do plano: uma sessão do planejador, o documento do Goal commitado e o plano no livro-razão.

O planejador lê a spec e o código e devolve critérios, decisões, o comando da
suíte e as fatias. O orquestrador confere, escreve `docs/goals/<slug>.md` na
área do Goal, commita e grava o plano. No Goal que veio do gerente, os
critérios e as decisões que o humano fixou ficam com o mesmo id e o mesmo nó,
e o critério do humano vale com o texto e o tipo de verificação do nó Criterio
dele, diga o planejador o que disser.

O plano pago não se paga de novo. A saída conferida vai para o Goal
(`plano_proposto`) antes de qualquer outro passo, e a retomada a reaproveita;
se o processo caiu entre o fim da sessão e essa gravação, a saída é relida do
stream da sessão, pela telemetria. O documento só é commitado quando muda: na
retomada depois do commit, vale o commit que já o gravou.
"""

from collections.abc import Mapping
from typing import Any

from graphow.core import aceite as a
from graphow.core.types import PapelAutor
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.briefing import briefing_do_planejador
from graphow.orquestrador.contexto_do_laco import ContextoDoGoal, MotivoDaParada, Parada
from graphow.orquestrador.documento_do_goal import caminho_do_documento, escrever_documento, renderizar_documento
from graphow.orquestrador.esquemas import ESQUEMA_DO_PLANO, PAPEL_PLANEJADOR
from graphow.orquestrador.git_do_goal import (
    descartar_mudancas,
    mensagem_do_orquestrador,
    ultimo_commit_do_arquivo,
)
from graphow.orquestrador.gravacao_do_plano import PlanoParaGravar, gravar_plano
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal
from graphow.orquestrador.replanejamento import bloco_da_recusa, retirados_pela_recusa
from graphow.orquestrador.saidas import IdsFixados, Plano, conferir_plano
from graphow.orquestrador.sessoes_de_papel import PedidoDePapel, saida_conferida_da_telemetria
from graphow.orquestrador.spec_do_goal import SpecDoGoal, montar_spec_do_goal
from graphow.orquestrador.validacao_json import validar_contra_esquema


def planejar(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> Parada | None:
    """O plano já pago, ou uma sessão do planejador; grava o plano, ou diz por que não deu."""
    fixos = _spec_fixada(contexto, estado)
    dados = _plano_ja_pago(contexto, estado, fixos)
    if dados is None:
        sem_orcamento = contexto.sem_orcamento()
        if sem_orcamento is not None:
            return sem_orcamento
        dados, problemas = _sessao_do_planejador(contexto, estado, fixos)
        if dados is None:
            return Parada(contexto.id_goal, MotivoDaParada.FALHA, "O plano nao conferiu: " + "; ".join(problemas))
        contexto.livro.gravar_plano_proposto(dados)
    _gravar(contexto, estado, Plano.de_json(dados).com_criterios_do_humano(fixos.criterios_do_humano), fixos=fixos)
    return None


def _sessao_do_planejador(
    contexto: ContextoDoGoal, estado: EstadoDoGoal, fixos: SpecDoGoal
) -> tuple[Mapping[str, Any] | None, tuple[str, ...]]:
    """Uma sessão do planejador na área, que volta ao commit de onde partiu."""
    resposta = contexto.sessoes.rodar(
        PedidoDePapel(
            papel=PAPEL_PLANEJADOR,
            id_goal=contexto.id_goal,
            pasta=contexto.area,
            briefing=_juntar_blocos(briefing_do_planejador(estado, str(estado.propriedades.get(m.CAMPO_SPEC, "")),
                                                           bool(fixos.nos_fixados)), bloco_da_recusa(estado)),
            conferir=lambda dados: _conferir(dados, fixos.fixados),
            orcamento_restante_usd=contexto.restante(),
        )
    )
    descartar_mudancas(contexto.area, contexto.patch("planejador"))
    return resposta.dados, resposta.problemas


def _plano_ja_pago(contexto: ContextoDoGoal, estado: EstadoDoGoal, fixos: SpecDoGoal) -> Mapping[str, Any] | None:
    """A saída do planejador que já foi conferida: a do Goal, ou a do stream da última sessão dele."""
    proposto = estado.propriedades.get(m.CAMPO_PLANO_PROPOSTO)
    if isinstance(proposto, Mapping) and not _problemas(proposto, fixos.fixados):
        return proposto
    if estado.propriedades.get(a.CAMPO_PLANOS_RECUSADOS):
        return None
    recuperado = saida_conferida_da_telemetria(
        contexto.telemetria.listar(contexto.id_goal), PAPEL_PLANEJADOR, lambda dados: _problemas(dados, fixos.fixados)
    )
    if recuperado is not None:
        contexto.livro.gravar_plano_proposto(recuperado)
    return recuperado


def _problemas(dados: Mapping[str, Any], fixados: IdsFixados) -> tuple[str, ...]:
    """O schema e o sentido do plano."""
    return validar_contra_esquema(dict(dados), ESQUEMA_DO_PLANO) or _conferir(dados, fixados)


def _conferir(dados: Mapping[str, Any], fixados: IdsFixados) -> tuple[str, ...]:
    """O sentido do plano, depois do schema."""
    return conferir_plano(Plano.de_json(dados), fixados)


def _spec_fixada(contexto: ContextoDoGoal, estado: EstadoDoGoal) -> SpecDoGoal:
    """No Goal do gerente, os critérios e as decisões que o humano fixou; no da spec, nenhum."""
    goal = contexto.livro.view().obter_no(estado.id_goal)
    if goal is None or goal.proveniencia.papel == PapelAutor.ORQUESTRADOR.value:
        return SpecDoGoal(str(estado.propriedades.get(m.CAMPO_SPEC, "")))
    return montar_spec_do_goal(contexto.livro.view(), estado.id_goal)


def _gravar(contexto: ContextoDoGoal, estado: EstadoDoGoal, plano: Plano, *, fixos: SpecDoGoal) -> None:
    """O documento do Goal commitado na área (se mudou) e o plano no livro-razão."""
    configuracao = contexto.configuracao
    caminho = caminho_do_documento(configuracao.slug)
    documento = renderizar_documento(contexto.id_goal, configuracao, plano, spec=str(estado.propriedades.get(m.CAMPO_SPEC, "")))
    escrever_documento(contexto.area, configuracao.slug, documento)
    if contexto.git.mudancas():
        mensagem = mensagem_do_orquestrador(f"Planeja o Goal {configuracao.slug}: {plano.titulo}", "", id_goal=contexto.id_goal)
        commit = contexto.commitar(mensagem)
    else:
        commit = ultimo_commit_do_arquivo(contexto.area, caminho)
    gravar_plano(
        contexto.livro,
        PlanoParaGravar(
            plano=plano,
            slug=configuracao.slug,
            commit_do_documento=commit,
            caminho_do_documento=caminho,
            nos_fixados=fixos.nos_fixados,
            renomear_goal=not fixos.nos_fixados and _criado_pelo_orquestrador(contexto),
            versao=m.versao_do_plano(estado.propriedades),
            retirar=retirados_pela_recusa(estado, [criterio.id for criterio in plano.criterios]),
        ),
    )


def _juntar_blocos(*blocos: str) -> str:
    """Os blocos do briefing, sem os vazios."""
    return "\n\n".join(bloco for bloco in blocos if bloco)


def _criado_pelo_orquestrador(contexto: ContextoDoGoal) -> bool:
    """O Goal nasceu de uma spec no orquestrador, e o título do plano pode virar o rótulo dele."""
    goal = contexto.livro.view().obter_no(contexto.id_goal)
    return goal is not None and goal.proveniencia.papel == PapelAutor.ORQUESTRADOR.value
