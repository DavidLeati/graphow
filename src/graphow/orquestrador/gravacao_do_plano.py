"""O plano do planejador gravado no livro-razão: critérios, decisões e fatias, num lote só.

Cada critério de aceite vira um nó Criterio que escopa o Goal, com o código,
o texto inteiro, o tipo de verificação e o estado `pendente` até a primeira
verificação que o julgar; cada decisão, uma Decision que orienta o Goal, com o
texto inteiro e o motivo; cada fatia, uma Task sob o Goal por `decompoe`, com
as dependências como `depende_de`. O que o Goal já trazia do gerente (critério
ou decisão com id) é reaproveitado, e não duplicado. O Goal guarda o plano
inteiro em `plano`, com o comando da suíte, o nó de cada critério e decisão e
o commit do documento do Goal.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from graphow.core import aceite as a
from graphow.core.types import TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.orquestrador import modelo_do_goal as m
from graphow.orquestrador.livro_razao import LivroRazaoDoGoal, aresta, propriedade
from graphow.orquestrador.saidas import Criterio, Decisao, Fatia, Plano


@dataclass(frozen=True)
class PlanoParaGravar:
    """O plano conferido e o que o cerca: o slug, os nós já fixados e o commit do documento."""

    plano: Plano
    slug: str
    commit_do_documento: str
    caminho_do_documento: str
    nos_fixados: Mapping[str, str] = field(default_factory=dict)
    renomear_goal: bool = False


def gravar_plano(livro: LivroRazaoDoGoal, pedido: PlanoParaGravar) -> None:
    """Grava o plano inteiro num lote."""
    plano = pedido.plano
    criterios = {c.id: pedido.nos_fixados.get(c.id) or m.id_do_criterio(pedido.slug, c.id) for c in plano.criterios}
    decisoes = {d.id: pedido.nos_fixados.get(d.id) or m.id_da_decisao(pedido.slug, d.id) for d in plano.decisoes}
    operacoes: list[ItemPatch] = []
    for criterio in plano.criterios:
        operacoes += _operacoes_do_criterio(livro, criterio, criterios[criterio.id])
    for decisao in plano.decisoes:
        operacoes += _operacoes_da_decisao(livro, decisao, decisoes[decisao.id])
    for ordem, fatia in enumerate(plano.fatias, start=1):
        operacoes += _operacoes_da_fatia(livro, pedido, fatia, ordem=ordem)
    operacoes += _operacoes_do_documento(livro, pedido)
    operacoes.append(propriedade(livro.id_goal, m.CAMPO_PLANO, _plano_em_json(pedido, criterios, decisoes)))
    if pedido.renomear_goal:
        operacoes.append(ItemPatch(OperacaoPatch.REPLACE, f"/nos/{livro.id_goal}/rotulo", plano.titulo))
    livro.gravar(operacoes, f"Plano do Goal {livro.id_goal}: {len(plano.fatias)} fatia(s)")


def _operacoes_do_criterio(livro: LivroRazaoDoGoal, criterio: Criterio, id_no: str) -> list[ItemPatch]:
    """O Criterio novo, que escopa o Goal; nada para o critério que o Goal já trazia."""
    if livro.view().contem_no(id_no):
        return []
    propriedades = {a.CAMPO_CODIGO: criterio.id, a.CAMPO_TEXTO: criterio.texto, a.CAMPO_VERIFICACAO: criterio.verificacao,
                    a.CAMPO_ESTADO: a.ESTADO_PENDENTE}
    return [
        *livro.produzido(id_no, TipoNo.CRITERIO, f"{criterio.id}: {criterio.texto}", propriedades=propriedades),
        aresta(id_no, livro.id_goal, TipoAresta.ESCOPA),
    ]


def _operacoes_da_decisao(livro: LivroRazaoDoGoal, decisao: Decisao, id_no: str) -> list[ItemPatch]:
    """A Decision da decisão nova, que orienta o Goal; nada para a que o Goal já trazia."""
    if livro.view().contem_no(id_no):
        return []
    propriedades = {"codigo": decisao.id, "texto": decisao.texto, "motivo": decisao.motivo}
    return [
        *livro.produzido(id_no, TipoNo.DECISION, decisao.texto, propriedades=propriedades),
        aresta(id_no, livro.id_goal, TipoAresta.ORIENTA),
    ]


def _operacoes_da_fatia(livro: LivroRazaoDoGoal, pedido: PlanoParaGravar, fatia: Fatia, *, ordem: int) -> list[ItemPatch]:
    """A Task da fatia sob o Goal, com as dependências para as fatias anteriores."""
    id_task = m.id_da_fatia(pedido.slug, fatia.id)
    textos = {criterio.id: criterio.texto for criterio in pedido.plano.criterios}
    propriedades = {
        m.CAMPO_STATUS: m.STATUS_PENDENTE,
        m.CAMPO_FATIA: fatia.id,
        m.CAMPO_ORDEM: ordem,
        m.CAMPO_OBJETIVO: fatia.objetivo,
        m.CAMPO_CRITERIOS: list(fatia.criterios),
        m.CAMPO_ARQUIVOS_ALVO: list(fatia.arquivos),
        m.CAMPO_MODELO: fatia.modelo,
        m.CAMPO_TENTATIVAS: 0,
        m.CAMPO_CRITERIO_PRONTO: " ".join(f"{c}: {textos.get(c, '')}" for c in fatia.criterios),
    }
    return [
        *livro.produzido(id_task, TipoNo.TASK, f"{fatia.id}: {fatia.titulo}", propriedades=propriedades),
        aresta(livro.id_goal, id_task, TipoAresta.DECOMPOE),
        *(aresta(id_task, m.id_da_fatia(pedido.slug, dependencia), TipoAresta.DEPENDE_DE) for dependencia in fatia.depende_de),
    ]


def _operacoes_do_documento(livro: LivroRazaoDoGoal, pedido: PlanoParaGravar) -> list[ItemPatch]:
    """O commit do documento do Goal como Artifact do plano."""
    id_artefato = f"art-{livro.id_goal}-plano"
    propriedades = {m.CAMPO_COMMIT: pedido.commit_do_documento, "arquivos": [pedido.caminho_do_documento]}
    return livro.produzido(id_artefato, TipoNo.ARTIFACT, f"Plano do Goal em {pedido.caminho_do_documento}", propriedades=propriedades)


def _plano_em_json(pedido: PlanoParaGravar, criterios: Mapping[str, str], decisoes: Mapping[str, str]) -> dict[str, object]:
    """O plano como propriedade do Goal, com o nó de cada critério e decisão."""
    plano = pedido.plano
    return {
        "titulo": plano.titulo,
        "comando_suite": plano.comando_suite,
        "criterios": [{"id": c.id, "texto": c.texto, "verificacao": c.verificacao, "no": criterios[c.id]} for c in plano.criterios],
        "decisoes": [{"id": d.id, "texto": d.texto, "motivo": d.motivo, "no": decisoes[d.id]} for d in plano.decisoes],
        "fatias": [fatia.id for fatia in plano.fatias],
        "fora_do_escopo": list(plano.fora_do_escopo),
        "documento": {"caminho": pedido.caminho_do_documento, "commit": pedido.commit_do_documento},
    }
