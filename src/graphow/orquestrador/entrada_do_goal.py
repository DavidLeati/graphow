"""De onde o laço parte: o Goal que uma spec cria (ou retoma), o Goal do gerente que ele adota e a configuração.

A mesma spec no mesmo repositório retoma o Goal aberto que ela criou; depois
de esse Goal fechar, a spec cria outro, com sufixo (`goal-soma-2`) que vale
também para o slug, os ids das fatias e a branch, para nada colidir com o
Goal anterior. A configuração recusa cedo o que não dá para conduzir: o HEAD
destacado sem `--base`, a branch do Goal igual à base, a área no checkout do
humano (ou dentro dele) e a branch que já existe com commits que não são do
Goal, a menos que a chamada diga `--adotar-ramo`.
"""

from dataclasses import dataclass
from pathlib import Path

from graphow.core.exceptions import GraphowError
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.contexto_do_laco import ORCAMENTO_PADRAO_USD, OpcoesDoLaco
from graphow.orquestrador.git_do_goal import TRAILER_DO_GOAL, GitDoGoal, commits_entre, raiz_do_repositorio
from graphow.orquestrador.leitura_do_goal import EstadoDoGoal, ler_estado, setor_do_goal
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, propriedade
from graphow.orquestrador.spec_do_goal import montar_spec_do_goal
from graphow.projection.graph_view import GrafoView

PREFIXO_GENERICO_DA_SPEC: str = "spec-"
SUFIXOS_POSSIVEIS: int = 100


class PedidoInvalido(GraphowError):
    """O que a chamada pediu não dá para conduzir."""


@dataclass(frozen=True)
class GoalDaSpec:
    """O Goal que a spec retoma ou cria: o id, o slug (com o sufixo) e se ele já existe."""

    id_goal: str
    slug: str
    existe: bool


def goal_da_spec(view: GrafoView, spec: Path, texto: str, *, raiz: Path) -> GoalDaSpec:
    """O Goal aberto que a mesma spec criou no mesmo repositório, ou o primeiro id livre para um novo."""
    base = slug_da_spec(spec, raiz)
    for sufixo in ("", *(f"-{n}" for n in range(2, SUFIXOS_POSSIVEIS))):
        slug = base + sufixo
        estado = ler_estado(view, m.id_do_goal(slug))
        if estado is None:
            return GoalDaSpec(m.id_do_goal(slug), slug, existe=False)
        configuracao = estado.configuracao
        mesma = configuracao is not None and Path(configuracao.repositorio) == raiz and estado.propriedades.get(m.CAMPO_SPEC) == texto
        if mesma and not estado.fechado:
            return GoalDaSpec(estado.id_goal, configuracao.slug if configuracao else slug, existe=True)
    raise PedidoInvalido("ids de Goal esgotados para a spec", {"slug": base})


def slug_da_spec(spec: Path, raiz: Path) -> str:
    """O nome da spec sem o prefixo `spec-`; a spec de nome genérico leva o nome do repositório."""
    nome = spec.stem.removeprefix(PREFIXO_GENERICO_DA_SPEC)
    return m.slug_de(raiz.name if nome.lower() in ("spec", "") else nome)


@dataclass(frozen=True)
class PedidoDeConfiguracao:
    """O que a configuração de um Goal novo precisa: o Goal, o repositório, a chamada e onde fica o estado."""

    id_goal: str
    slug: str
    raiz: Path
    opcoes: OpcoesDoLaco
    pasta_de_estado: Path


def configuracao_nova(pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal:
    """A configuração do Goal novo, com os padrões do que a chamada não disse, conferida."""
    opcoes = pedido.opcoes
    base = opcoes.base or GitDoGoal(pedido.raiz).ramo_atual()
    if not base:
        raise PedidoInvalido("o repositorio esta com o HEAD destacado: diga a base com --base", {"repositorio": str(pedido.raiz)})
    ramo = opcoes.ramo or f"graphow/{pedido.slug}"
    if ramo == base:
        raise PedidoInvalido("a branch do Goal nao pode ser a propria base", {"ramo": ramo, "base": base})
    area = opcoes.area or pedido.pasta_de_estado / pedido.id_goal / "area"
    _conferir_area(area, pedido.raiz)
    if not opcoes.adotar_ramo:
        _conferir_ramo_existente(pedido.raiz, ramo, base, id_goal=pedido.id_goal)
    return m.ConfiguracaoDoGoal(
        modo=opcoes.modo or m.MODO_SUPERVISIONADO, repositorio=str(pedido.raiz), area=str(area),
        ramo=ramo, base=base, slug=pedido.slug,
        orcamento_usd=opcoes.orcamento_usd if opcoes.orcamento_usd is not None else ORCAMENTO_PADRAO_USD,
    )


def _conferir_area(area: Path, raiz: Path) -> None:
    """A área do Goal é um worktree à parte: nem o checkout do humano nem uma pasta dentro dele."""
    resolvida, checkout = area.expanduser().resolve(), raiz.resolve()
    if resolvida == checkout or checkout in resolvida.parents:
        raise PedidoInvalido(
            "a area do Goal nao pode ser o checkout do humano nem ficar dentro dele: escolha outra pasta com --area",
            {"area": str(area), "repositorio": str(raiz)},
        )


def _conferir_ramo_existente(raiz: Path, ramo: str, base: str, *, id_goal: str) -> None:
    """A branch que já existe só é adotada se todo commit dela desde a base for deste Goal (pelo trailer)."""
    if not GitDoGoal(raiz).ramo_existe(ramo):
        return
    alheios = [commit for commit in commits_entre(raiz, base, ramo) if not commit.tem_trailer(TRAILER_DO_GOAL, id_goal)]
    if alheios:
        raise PedidoInvalido(
            f"a branch {ramo} ja existe com {len(alheios)} commit(s) que nao sao deste Goal: escolha outra com --ramo, "
            "ou adote-a assim mesmo com --adotar-ramo",
            {"ramo": ramo, "base": base, "commits": ", ".join(commit.hash[:12] for commit in alheios[:5])},
        )


def adotar_goal(livro: LivroRazaoDoGoal, estado: EstadoDoGoal, pedido: PedidoDeConfiguracao) -> m.ConfiguracaoDoGoal:
    """O Goal do gerente passa a ser conduzido: a spec montada dos nós e a configuração da chamada."""
    id_setor = setor_do_goal(livro.view(), estado.id_goal)
    if not id_setor:
        raise PedidoInvalido("o Goal nao esta pendurado numa Sessao de um Setor", {"id_goal": estado.id_goal})
    configuracao = configuracao_nova(pedido)
    livro.adotar_goal(id_setor, montar_spec_do_goal(livro.view(), estado.id_goal).texto, configuracao)
    return configuracao


def pedido_de_adocao(estado: EstadoDoGoal, opcoes: OpcoesDoLaco, *, repositorio: Path | None, pasta_de_estado: Path) -> PedidoDeConfiguracao:
    """O pedido de configuração do Goal do gerente, que pede o repositório na primeira vez."""
    if repositorio is None:
        raise PedidoInvalido("o Goal ainda nao foi orquestrado: diga o repositorio com --repo", {"id_goal": estado.id_goal})
    slug = m.slug_de(estado.id_goal.removeprefix("goal-"))
    return PedidoDeConfiguracao(estado.id_goal, slug, raiz_do_repositorio(repositorio), opcoes, pasta_de_estado)


def atualizar_configuracao(livro: LivroRazaoDoGoal, configuracao: m.ConfiguracaoDoGoal, opcoes: OpcoesDoLaco) -> m.ConfiguracaoDoGoal:
    """O modo e o orçamento que a chamada pede de novo valem daqui em diante, e ficam gravados."""
    modo = opcoes.modo or configuracao.modo
    orcamento = opcoes.orcamento_usd if opcoes.orcamento_usd is not None else configuracao.orcamento_usd
    if (modo, orcamento) == (configuracao.modo, configuracao.orcamento_usd):
        return configuracao
    nova = m.ConfiguracaoDoGoal(**{**configuracao.em_json(), "modo": modo, "orcamento_usd": orcamento})
    livro.gravar([propriedade(livro.id_goal, m.CAMPO_ORQUESTRACAO, nova.em_json())], f"Configuracao do Goal {livro.id_goal}")
    return nova
