"""Quem escreve o plano aprovado e a resposta de desvio de um Goal: o gesto da política, não o papel.

`Goal.planos` é do gesto `aprovar_plano` e `Goal.respostas_de_desvio` é do gesto
`responder_desvio`. O humano exerce os dois sempre; o árbitro, só quando a
política do projeto do Goal lho entrega (`aprovar_plano` na arbitragem máxima;
`responder_desvio` só na personalizada); planejador, executor e revisor, nunca.
Vale por qualquer caminho de escrita, `propor_patch` livre inclusive: criar o
Goal já com a lista, escrever, trocar ou remover a propriedade. A forma da
entrada (versão, seq, autoria, só cresce) é conferida pelo InvariantGate
(kernel/forma_do_escopo.py), que também vale para o humano.

O mesmo ponto de entrada leva a regra D3, que barra o executor na Task de Goal
sem plano (kernel/execucao_sem_plano.py).
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from graphow.core.escopo import CAMPO_PLANOS, CAMPO_RESPOSTAS_DE_DESVIO
from graphow.core.governanca import Gesto
from graphow.core.types import TipoNo
from graphow.kernel.execucao_sem_plano import validar_plano_para_assumir
from graphow.kernel.gestos_de_no import ContextoPermissaoEdicao, GestosDeNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, ResultadoValidacao
from graphow.kernel.permissao_de_aresta import SEGMENTOS_DE_ELEMENTO_INTEIRO, ContextoPapel

SEGMENTOS_DE_UMA_PROPRIEDADE: int = 4

# Propriedade reservada do Goal -> o gesto que a escreve e a ferramenta que o exerce.
GESTO_POR_CAMPO: Mapping[str, Gesto] = MappingProxyType(
    {
        CAMPO_PLANOS: Gesto.APROVAR_PLANO,
        CAMPO_RESPOSTAS_DE_DESVIO: Gesto.RESPONDER_DESVIO,
    }
)


def validar_escrita_de_escopo(ctx: ContextoPermissaoEdicao, gestos: GestosDeNo) -> ResultadoValidacao:
    """Exige o gesto do papel quando a operação escreve uma lista de escopo; depois aplica a regra D3."""
    for campo in _campos_reservados_tocados(ctx.segmentos, ctx.item, ctx.contexto):
        gesto = GESTO_POR_CAMPO[campo]
        o_que = (
            f"escrever '{campo}' no Goal '{ctx.segmentos[1]}': e o gesto '{gesto.value}', que a ferramenta "
            f"'{gesto.value}' exerce. Quem nao o tem abre uma Question ao humano"
        )
        resultado = gestos.exigir(gesto, ctx.segmentos[1], ctx.contexto, o_que=o_que)
        if not resultado.aprovado:
            return resultado
    return validar_plano_para_assumir(ctx.segmentos, ctx.item, ctx.contexto)


def _campos_reservados_tocados(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> tuple[str, ...]:
    """Os campos reservados que a operação escreve num Goal: ao criá-lo ou na propriedade isolada."""
    if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO:
        return _campos_declarados_na_criacao(item)
    if len(segmentos) != SEGMENTOS_DE_UMA_PROPRIEDADE or segmentos[2] != "propriedades":
        return ()
    no = contexto.estado_com_lote.nos.get(segmentos[1])
    if no is None or no.tipo != TipoNo.GOAL or segmentos[3] not in GESTO_POR_CAMPO:
        return ()
    return (segmentos[3],)


def _campos_declarados_na_criacao(item: ItemPatch) -> tuple[str, ...]:
    """Os campos reservados que o Goal criado já traz nas propriedades."""
    valor = item.value if isinstance(item.value, dict) else {}
    propriedades = valor.get("propriedades")
    if item.op != OperacaoPatch.ADD or valor.get("tipo") != TipoNo.GOAL.value or not isinstance(propriedades, dict):
        return ()
    return tuple(campo for campo in GESTO_POR_CAMPO if campo in propriedades)
