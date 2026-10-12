"""A ontologia 1.7.0: Criterio e Achado são nós, `fere` liga o achado ao que ele fere, e só o humano e o orquestrador os escrevem."""

from collections.abc import Sequence
from typing import Any

import pytest

from graphow.core.governanca import PROPRIEDADE_GOVERNANCA_DO_PROJETO
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.papel_do_orquestrador import sessao_do_goal
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

SESSAO_DO_GERENTE: str = "sess-gerente"
SESSAO: str = sessao_do_goal("goal")


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch], papel: PapelAutor = PapelAutor.HUMANO,
              *, goal: str = "goal") -> ResultadoSubmissao:
    """Um lote do papel dado; o do orquestrador diz o Goal que conduz."""
    conduzido = goal if papel == PapelAutor.ORQUESTRADOR else None
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=tuple(operacoes),
                               justificativa="teste", goal_conduzido=conduzido)
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """A criação de um nó."""
    return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", {"id": id_no, "tipo": tipo.value, "rotulo": id_no,
                                                          "propriedades": propriedades or {}})


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """A criação de uma aresta."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}",
                     {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value})


def _propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """A escrita de uma propriedade."""
    return ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_no}/propriedades/{chave}", valor)


def _produzido(id_no: str, tipo: TipoNo, sessao: str, propriedades: dict[str, Any] | None = None) -> list[ItemPatch]:
    """O nó pendurado na Sessao dada."""
    return [_no(id_no, tipo, propriedades), _aresta(sessao, id_no, TipoAresta.PRODUZ)]


def _kernel_com_goal_do_gerente(**propriedades_do_projeto: object) -> WriteKernel:
    """O Goal do gerente com um Criterio e uma Decision, já adotado pelo orquestrador, e um outro Goal ao lado."""
    kernel = montar_kernel_em_memoria()
    humano = _submeter(kernel, [
        _no("proj", TipoNo.PROJETO, dict(propriedades_do_projeto)), _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no(SESSAO_DO_GERENTE, TipoNo.SESSAO), _aresta("setor", SESSAO_DO_GERENTE, TipoAresta.CONTEM),
        *_produzido("goal", TipoNo.GOAL, SESSAO_DO_GERENTE, {"descricao": "somar"}),
        *_produzido("crit-1", TipoNo.CRITERIO, SESSAO_DO_GERENTE, {"codigo": "C1", "texto": "somar(2, 3) == 5", "verificacao": "teste"}),
        _aresta("crit-1", "goal", TipoAresta.ESCOPA),
        *_produzido("dec-1", TipoNo.DECISION, SESSAO_DO_GERENTE, {"texto": "so stdlib", "motivo": "sem dependencia"}),
        _aresta("dec-1", "goal", TipoAresta.ORIENTA),
        *_produzido("goal-b", TipoNo.GOAL, SESSAO_DO_GERENTE), *_produzido("dec-b", TipoNo.DECISION, SESSAO_DO_GERENTE),
        _aresta("dec-b", "goal-b", TipoAresta.ORIENTA),
    ])
    assert humano.sucesso, humano.mensagem
    adocao = _submeter(kernel, [
        _no(SESSAO, TipoNo.SESSAO), _aresta("setor", SESSAO, TipoAresta.CONTEM),
        _propriedade("goal", "spec", "somar"), _propriedade("goal", "orquestracao", {"modo": "autonomo"}),
        *_produzido("ver-1", TipoNo.EVIDENCE, SESSAO, {"acao": "verificacao_do_goal"}), _aresta("ver-1", "goal", TipoAresta.DERIVA_DE),
    ], PapelAutor.ORQUESTRADOR)
    assert adocao.sucesso, adocao.mensagem
    return kernel


def _achado(id_achado: str, *destinos: str) -> list[ItemPatch]:
    """O Achado da verificação ver-1, ferindo os nós dados."""
    return [*_produzido(id_achado, TipoNo.ACHADO, SESSAO, {"gravidade": "bloqueante", "estado": "aberto"}),
            _aresta(id_achado, "ver-1", TipoAresta.DERIVA_DE), *(_aresta(id_achado, d, TipoAresta.FERE) for d in destinos)]


def test_gerente_grava_criterio_que_escopa_o_goal_nominal() -> None:
    """O humano cria o Criterio com código, texto e tipo de verificação, ligado ao Goal por `escopa`."""
    kernel = _kernel_com_goal_do_gerente()

    criterio = kernel.obter_view().obter_no("crit-1")

    assert criterio is not None and criterio.tipo == TipoNo.CRITERIO
    assert criterio.obter_propriedade("verificacao") == "teste"


def test_orquestrador_grava_achado_que_fere_o_criterio_e_a_decisao_do_goal_nominal() -> None:
    """O Achado nasce da verificação e fere o Criterio e a Decision que o gerente gravou para o Goal."""
    kernel = _kernel_com_goal_do_gerente()

    recibo = _submeter(kernel, _achado("achado-1", "crit-1", "dec-1"), PapelAutor.ORQUESTRADOR)

    assert recibo.sucesso, recibo.mensagem
    feridos = {a.destino_id for a in kernel.obter_view().obter_arestas_saida("achado-1", TipoAresta.FERE)}
    assert feridos == {"crit-1", "dec-1"}


def test_orquestrador_escreve_so_o_que_as_verificacoes_dao_ao_criterio_do_gerente_nominal() -> None:
    """O estado e os testes de aceite do Criterio do humano são do orquestrador; o texto continua do humano."""
    kernel = _kernel_com_goal_do_gerente()

    derivado = _submeter(kernel, [_propriedade("crit-1", "estado", "atende"),
                                  _propriedade("crit-1", "testes_de_aceite", [{"arquivo": "aceite/aceite_c1.py"}])],
                         PapelAutor.ORQUESTRADOR)
    texto = _submeter(kernel, [_propriedade("crit-1", "texto", "outro")], PapelAutor.ORQUESTRADOR)

    assert derivado.sucesso, derivado.mensagem
    assert not texto.sucesso and "fora do Goal" in texto.mensagem


def test_orquestrador_nao_fere_decisao_de_outro_goal_edge_case() -> None:
    """Caso de borda: a porta estreita é só para o que governa o Goal conduzido."""
    kernel = _kernel_com_goal_do_gerente()

    recibo = _submeter(kernel, _achado("achado-1", "dec-b"), PapelAutor.ORQUESTRADOR)

    assert not recibo.sucesso and "fora do Goal" in recibo.mensagem


def test_deriva_de_so_chega_ao_criterio_do_goal_e_nao_a_decisao_edge_case() -> None:
    """Caso de borda: o commit dos testes deriva do Criterio do humano, mas nada do laço deriva da Decision dele."""
    kernel = _kernel_com_goal_do_gerente()

    ao_criterio = _submeter(kernel, [*_produzido("art-aceite", TipoNo.ARTIFACT, SESSAO, {"commit": "abc"}),
                                     _aresta("art-aceite", "crit-1", TipoAresta.DERIVA_DE)], PapelAutor.ORQUESTRADOR)
    a_decisao = _submeter(kernel, [*_produzido("nota", TipoNo.NOTE, SESSAO), _aresta("nota", "dec-1", TipoAresta.DERIVA_DE)],
                          PapelAutor.ORQUESTRADOR)

    assert ao_criterio.sucesso, ao_criterio.mensagem
    assert not a_decisao.sucesso and "fora do Goal" in a_decisao.mensagem


def test_fere_so_vai_do_achado_ao_criterio_ou_a_decisao_edge_case() -> None:
    """Caso de borda: o SchemaGate recusa `fere` que parte de outro tipo ou chega a uma Task."""
    kernel = _kernel_com_goal_do_gerente()

    errada = _submeter(kernel, [*_produzido("ev", TipoNo.EVIDENCE, SESSAO_DO_GERENTE), _aresta("ev", "crit-1", TipoAresta.FERE)])

    assert not errada.sucesso and "fere" in errada.mensagem


@pytest.mark.parametrize("papel", [PapelAutor.PLANEJADOR, PapelAutor.EXECUTOR, PapelAutor.REVISOR, PapelAutor.ARBITRO])
@pytest.mark.parametrize("tipo", [TipoNo.CRITERIO, TipoNo.ACHADO])
def test_agente_nao_cria_criterio_nem_achado_nem_sob_estrutura_ilimitada_edge_case(papel: PapelAutor, tipo: TipoNo) -> None:
    """Caso de borda: o critério é do humano e o achado é do orquestrador, mesmo com a estrutura aberta aos agentes."""
    politica = {"preset": "personalizada", "personalizada": {"estrutura": "ilimitado"}}
    kernel = _kernel_com_goal_do_gerente(**{PROPRIEDADE_GOVERNANCA_DO_PROJETO: politica})

    recibo = _submeter(kernel, _produzido("novo", tipo, SESSAO_DO_GERENTE), papel)

    assert not recibo.sucesso
    assert tipo.value in recibo.mensagem
