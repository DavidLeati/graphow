"""Forma e identidade de cada operação do lote, conferidas pelo SchemaGate antes dos outros portões.

Os portões liam o caminho com o próprio parser, e o conversor gravava outra
coisa: `add` em `/nos/nota` com `"id": "orfa"` criava 'orfa' fora da
hierarquia, `test` no status concluía uma Task com dúvida bloqueante aberta, e
`add` em `/arestas/<id>/...` gravava um evento que o acumulador não sabia
aplicar. Depois destas regras, todo `add` do lote cria um id novo, o mesmo do
caminho, numa forma que o conversor grava como ela é, e é essa a premissa com
que o RoleGate e o InvariantGate leem o lote.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.models import GrafoEstado
from graphow.core.types import TipoNo
from graphow.kernel.conversao_eventos import OPERACOES_POR_FORMA, grava_como_diz
from graphow.kernel.patch_models import ItemPatch, ResultadoValidacao

PORTAO: str = "SchemaGate"

# Todo caminho valido nomeia a colecao e o elemento: '/nos/<id>' ou '/arestas/<id>'.
SEGMENTOS_ATE_O_IDENTIFICADOR: int = 2
COLECAO_DE_NOS: str = "nos"
COLECOES: frozenset[str] = frozenset({COLECAO_DE_NOS, "arestas"})

# Dito na recusa, montado da mesma tabela que o conversor segue.
FORMAS_ACEITAS: str = "; ".join(
    f"{', '.join(sorted(op.value for op in operacoes))} em /{'/'.join(forma)}"
    for forma, operacoes in OPERACOES_POR_FORMA.items()
)


@dataclass(frozen=True)
class ContextoValidacaoNo:
    """DTO imutável para encapsular os parâmetros de validação do nó."""

    segmentos: Sequence[str]
    item: ItemPatch
    estado: GrafoEstado


@dataclass
class CriadosNoLote:
    """O que as operações anteriores do mesmo lote já criaram, na ordem do lote."""

    nos: dict[str, TipoNo] = field(default_factory=dict)
    arestas: set[str] = field(default_factory=set)

    def contem(self, colecao: str, id_elemento: str, estado: GrafoEstado) -> bool:
        """Diz se o id já está no grafo ou foi criado antes neste lote."""
        if colecao == COLECAO_DE_NOS:
            return estado.contem_no(id_elemento) or id_elemento in self.nos
        return id_elemento in estado.arestas or id_elemento in self.arestas


def validar_caminho(item: ItemPatch, segmentos: tuple[str, ...]) -> ResultadoValidacao:
    """O caminho nomeia um nó ou uma aresta, numa forma que o log grava como ela é."""
    if not segmentos:
        return ResultadoValidacao.falha("Caminho de patch vazio", PORTAO, modo=ModoFalhaMAST.CAMINHO_INVALIDO)
    if len(segmentos) < SEGMENTOS_ATE_O_IDENTIFICADOR:
        return ResultadoValidacao.falha(
            f"Caminho '{item.path}' nao identifica um no nem uma aresta",
            PORTAO,
            {"path": item.path},
            modo=ModoFalhaMAST.CAMINHO_INVALIDO,
        )
    if segmentos[0] not in COLECOES:
        return ResultadoValidacao.falha(
            f"Raiz desconhecida '{segmentos[0]}'. Use 'nos' ou 'arestas'",
            PORTAO,
            modo=ModoFalhaMAST.CAMINHO_INVALIDO,
        )
    return _validar_forma(item, segmentos)


def _validar_forma(item: ItemPatch, segmentos: tuple[str, ...]) -> ResultadoValidacao:
    """Aceita só a operação que o conversor grava como ela é.

    `test`, `move` e `copy` viravam escrita no conversor, e um `test` no status
    concluía uma Task com dúvida bloqueante aberta: o InvariantGate só olha
    `add` e `replace`. `add` em `/arestas/<id>/...` criava a aresta sem
    validação nenhuma e envenenava o log do ramo. A tabela é a do próprio
    conversor, para os dois não voltarem a divergir.
    """
    if grava_como_diz(segmentos, item.op):
        return ResultadoValidacao.sucesso()
    return ResultadoValidacao.falha(
        f"O kernel so aceita estas formas: {FORMAS_ACEITAS}. Recebeu '{item.op.value}' em '{item.path}'",
        PORTAO,
        {"path": item.path, "op": item.op.value},
        modo=ModoFalhaMAST.CAMINHO_INVALIDO,
    )


def validar_identidade(ctx: ContextoValidacaoNo, criados: CriadosNoLote) -> ResultadoValidacao:
    """O valor cria o elemento que o caminho nomeia, e esse id ainda não existe."""
    resultado_caminho = _validar_id_do_caminho(ctx)
    if not resultado_caminho.aprovado:
        return resultado_caminho
    return _validar_id_novo(ctx, criados)


def _validar_id_do_caminho(ctx: ContextoValidacaoNo) -> ResultadoValidacao:
    """Exige que o valor crie o mesmo elemento que o caminho nomeia.

    O conversor grava a criação com o `id` do valor, e o acumulador cria o nó
    ou a aresta por ele; já a hierarquia do InvariantGate e a antevisão do
    RoleGate leem o id do caminho. Com os dois diferentes, os portões julgavam
    um elemento e o log gravava outro: `/nos/nota` com `"id": "orfa"` criava
    'orfa' sem aresta de contenção, porque a hierarquia conferida era a de
    'nota', que já existia e já estava pendurada.
    """
    id_caminho = ctx.segmentos[1]
    id_valor = str(ctx.item.value["id"])
    if id_valor == id_caminho:
        return ResultadoValidacao.sucesso()
    return ResultadoValidacao.falha(
        f"O caminho '{ctx.item.path}' nomeia '{id_caminho}', mas o valor declara o id '{id_valor}'. "
        "Use o mesmo id no caminho e no campo 'id' do valor",
        PORTAO,
        {"path": ctx.item.path, "id_caminho": id_caminho, "id_valor": id_valor},
        modo=ModoFalhaMAST.CAMINHO_INVALIDO,
    )


def _validar_id_novo(ctx: ContextoValidacaoNo, criados: CriadosNoLote) -> ResultadoValidacao:
    """Recusa `add` sobre um id que o grafo ou o próprio lote já tem.

    O acumulador trata a criação de um id existente como substituição, e ela
    escapava das regras de edição: um executor transformava uma Constraint em
    Note e trocava a `produz` que não pode remover por uma `deriva_de`,
    deixando o nó sem pai. Remover e recriar o mesmo id no mesmo lote fica de
    fora pelo mesmo motivo: a hierarquia conferida seria a das arestas que a
    remoção apaga.
    """
    if not criados.contem(ctx.segmentos[0], ctx.segmentos[1], ctx.estado):
        return ResultadoValidacao.sucesso()
    return _recusar_elemento_existente(ctx)


def _recusar_elemento_existente(ctx: ContextoValidacaoNo) -> ResultadoValidacao:
    """Diz que o id já existe e como editar sem recriar."""
    id_elemento = ctx.segmentos[1]
    orientacao = "Aresta nao se edita: remova esta e crie outra com id novo"
    if ctx.segmentos[0] == COLECAO_DE_NOS:
        orientacao = (
            f"Para editar, use 'replace' em '/nos/{id_elemento}/rotulo' "
            f"ou '/nos/{id_elemento}/propriedades/<chave>'"
        )
    return ResultadoValidacao.falha(
        f"O id '{id_elemento}' ja existe no grafo ou neste lote, e 'add' em '{ctx.item.path}' so cria. "
        f"{orientacao}",
        PORTAO,
        {"path": ctx.item.path, "id": id_elemento},
        modo=ModoFalhaMAST.ELEMENTO_JA_EXISTENTE,
    )
