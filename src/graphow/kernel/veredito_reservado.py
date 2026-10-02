"""A propriedade `veredito` de uma Evidence é de quem julga: revisor, humano ou árbitro.

Um executor que criasse a Evidence `veredito=aprovado` e concluísse a própria
Task, ou trocasse o veredito da Evidence do revisor, esvaziava a revisão. O
RoleGate recusa a escrita do veredito a qualquer outro papel, na criação do nó,
no nó inteiro e na propriedade isolada (add, replace e remove), e recusa
também remover a Evidence que carrega um veredito, que devolveria a vez a um
julgamento anterior. A regra do fechamento (kernel/veredito_de_fechamento.py)
confere a proveniência dos nós por conta própria: este portão barra a escrita,
aquela não confia no que já está gravado.
"""

from collections.abc import Sequence

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.orquestracao import CAMPO_VEREDITO
from graphow.core.types import TipoNo
from graphow.kernel.matriz_papeis import PAPEIS_QUE_JULGAM
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch, ResultadoValidacao
from graphow.kernel.permissao_de_aresta import SEGMENTOS_DE_ELEMENTO_INTEIRO, ContextoPapel

SEGMENTOS_DA_PROPRIEDADE: int = 4


def validar_escrita_de_veredito(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> ResultadoValidacao:
    """Recusa o papel que não julga quando a operação escreve ou remove o veredito de uma Evidence."""
    papel = contexto.proposta.papel
    if papel in PAPEIS_QUE_JULGAM or not _toca_o_veredito(segmentos, item, contexto):
        return ResultadoValidacao.sucesso()
    return ResultadoValidacao.falha(
        f"Papel '{papel.value}' nao pode escrever 'veredito' numa Evidence nem remover a que o carrega. "
        "Julgar e do revisor (ou do humano ou do arbitro): o executor entrega e espera a revisao",
        "RoleGate",
        {"propriedade_reservada": CAMPO_VEREDITO, "id_no": segmentos[1] if len(segmentos) > 1 else ""},
        modo=ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL,
    )


def _toca_o_veredito(segmentos: Sequence[str], item: ItemPatch, contexto: ContextoPapel) -> bool:
    """A operação escreve o veredito de uma Evidence: ao criá-la, no nó inteiro, na propriedade ou ao removê-la."""
    if len(segmentos) == SEGMENTOS_DE_ELEMENTO_INTEIRO:
        return _toca_no_inteiro(segmentos[1], item, contexto)
    if len(segmentos) == SEGMENTOS_DA_PROPRIEDADE and segmentos[2:] == ["propriedades", CAMPO_VEREDITO]:
        no = contexto.estado_com_lote.nos.get(segmentos[1])
        return no is not None and no.tipo == TipoNo.EVIDENCE
    return False


def _toca_no_inteiro(id_no: str, item: ItemPatch, contexto: ContextoPapel) -> bool:
    """Cria ou reescreve a Evidence com veredito, ou remove a Evidence que já tem um."""
    if item.op == OperacaoPatch.REMOVE:
        no = contexto.estado.nos.get(id_no)
        return no is not None and no.tipo == TipoNo.EVIDENCE and bool(no.propriedades.get(CAMPO_VEREDITO))
    valor = item.value if isinstance(item.value, dict) else {}
    propriedades = valor.get("propriedades")
    return valor.get("tipo") == TipoNo.EVIDENCE.value and isinstance(propriedades, dict) and CAMPO_VEREDITO in propriedades
