"""O kernel só deixa o Goal do aceite no centro fechar com a verificação final limpa no commit atual."""

from collections.abc import Sequence
from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.papel_do_orquestrador import sessao_do_goal
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel

SESSAO: str = sessao_do_goal("goal")
PONTA: dict[str, str] = {"commit": "doc123", "commit_do_codigo": "cod123"}


def _submeter(kernel: WriteKernel, operacoes: Sequence[ItemPatch], papel: PapelAutor = PapelAutor.ORQUESTRADOR) -> ResultadoSubmissao:
    """Um lote do papel dado; o do orquestrador conduz o Goal `goal`."""
    conduzido = "goal" if papel == PapelAutor.ORQUESTRADOR else None
    dados = DadosPropostaPatch(autor=f"autor-{papel.value}", papel=papel, operacoes=tuple(operacoes),
                               justificativa="teste", goal_conduzido=conduzido)
    return kernel.submeter_patch(PropostaPatch.criar(dados))


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> list[ItemPatch]:
    """O nó produzido pela Sessao do orquestrador."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return [ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", valor), _aresta(SESSAO, id_no, TipoAresta.PRODUZ)]


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """A criação de uma aresta."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}",
                     {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value})


def _propriedade(id_no: str, chave: str, valor: object) -> ItemPatch:
    """A escrita de uma propriedade."""
    return ItemPatch(OperacaoPatch.REPLACE, f"/nos/{id_no}/propriedades/{chave}", valor)


def _kernel_com_goal(**goal: object) -> WriteKernel:
    """O Goal conduzido com o critério C1 como nó, o plano que o lista e a ponta da branch."""
    kernel = montar_kernel_em_memoria()
    propriedades = {"status": "pendente", "orquestracao": {"modo": "autonomo"}, "ponta_do_ramo": PONTA,
                    "plano": {"criterios": [{"id": "C1", "no": "crit-1"}]}, **goal}
    recibo = _submeter(kernel, [
        *[ItemPatch(OperacaoPatch.ADD, "/nos/proj", {"id": "proj", "tipo": "Projeto", "rotulo": "p", "propriedades": {}})],
        ItemPatch(OperacaoPatch.ADD, "/nos/setor", {"id": "setor", "tipo": "Setor", "rotulo": "s", "propriedades": {}}),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        ItemPatch(OperacaoPatch.ADD, f"/nos/{SESSAO}", {"id": SESSAO, "tipo": "Sessao", "rotulo": "s", "propriedades": {}}),
        _aresta("setor", SESSAO, TipoAresta.CONTEM),
        *_no("goal", TipoNo.GOAL, propriedades),
        *_no("crit-1", TipoNo.CRITERIO, {"codigo": "C1", "texto": "somar", "verificacao": "teste"}),
        _aresta("crit-1", "goal", TipoAresta.ESCOPA),
    ])
    assert recibo.sucesso, recibo.mensagem
    return kernel


def _verificacao(numero: int, *, final: bool = True, veredito: str = "aprovado", commit_do_codigo: str = "cod123",
                 c1: str = "atende") -> list[ItemPatch]:
    """A Evidence de verificação ligada ao Goal."""
    propriedades = {"acao": "verificacao_do_goal", "numero": numero, "final": final, "veredito": veredito,
                    "commit": commit_do_codigo, "commit_do_codigo": commit_do_codigo,
                    "pareceres": [{"id": "C1", "no": "crit-1", "veredito": c1, "prova": "aceite verde"}]}
    id_ver = f"ver-{numero}"
    return [*_no(id_ver, TipoNo.EVIDENCE, propriedades), _aresta(id_ver, "goal", TipoAresta.DERIVA_DE)]


def _achado(id_achado: str, verificacao: str, estado: str, gravidade: str = "bloqueante") -> list[ItemPatch]:
    """O Achado que deriva da verificação e fere C1."""
    return [*_no(id_achado, TipoNo.ACHADO, {"gravidade": gravidade, "estado": estado}),
            _aresta(id_achado, verificacao, TipoAresta.DERIVA_DE), _aresta(id_achado, "crit-1", TipoAresta.FERE)]


FECHAR: ItemPatch = _propriedade("goal", "status", "concluido")


def _fechar(kernel: WriteKernel, papel: PapelAutor = PapelAutor.ORQUESTRADOR) -> ResultadoSubmissao:
    """O lote que fecha o Goal."""
    return _submeter(kernel, [FECHAR], papel)


def _mover(id_achado: str, estado: str, **extra: str) -> list[ItemPatch]:
    """A transição do estado do Achado, com o que ela exige no mesmo lote."""
    return [_propriedade(id_achado, "estado", estado), *(_propriedade(id_achado, chave, valor) for chave, valor in extra.items())]


def test_goal_fecha_com_a_verificacao_final_limpa_na_ponta_nominal() -> None:
    """Verificação final, limpa, no commit do código da ponta, com C1 atende e o bloqueante resolvido."""
    kernel = _kernel_com_goal()
    for lote in ([*_verificacao(1, final=False, veredito="rejeitado", c1="parcial"), *_achado("achado-1", "ver-1", "aberto")],
                 _mover("achado-1", "corrigido", commit_da_correcao="cod123"), _mover("achado-1", "resolvido"), _verificacao(2)):
        recibo = _submeter(kernel, lote)
        assert recibo.sucesso, recibo.mensagem

    recibo = _fechar(kernel)

    assert recibo.sucesso, recibo.mensagem


@pytest.mark.parametrize(
    ("lotes", "motivo"),
    [
        ([], "nao tem verificacao"),
        ([_verificacao(1, final=False)], "nao e a final"),
        ([_verificacao(1, veredito="rejeitado")], "nao e limpa"),
        ([_verificacao(1, commit_do_codigo="antigo")], "ponta da branch do Goal esta em cod123"),
        ([_verificacao(1, c1="parcial")], "o criterio crit-1 esta 'parcial'"),
        ([[*_verificacao(1), *_achado("achado-1", "ver-1", "aberto")]], "o achado bloqueante achado-1 esta 'aberto'"),
        ([[*_verificacao(1), *_achado("achado-1", "ver-1", "aberto")], _mover("achado-1", "corrigido", commit_da_correcao="x")],
         "o achado bloqueante achado-1 esta 'corrigido'"),
        ([_verificacao(2), _verificacao(1, final=False)], "a ultima verificacao (ver-1) nao e a final"),
    ],
    ids=["sem-verificacao", "nao-final", "com-bloqueante", "commit-antigo", "criterio-parcial", "achado-aberto",
         "achado-so-corrigido", "ordem-do-log-vence-o-numero"],
)
def test_kernel_recusa_fechar_sem_a_prova_edge_case(lotes: list[list[ItemPatch]], motivo: str) -> None:
    """Caso de borda: cada falta da prova recusa o lote que fecha o Goal, com o motivo; a última é a do log, não a de maior número."""
    kernel = _kernel_com_goal()
    for lote in lotes:
        assert _submeter(kernel, lote).sucesso

    recibo = _fechar(kernel)

    assert not recibo.sucesso
    assert recibo.modo_de_falha == ModoFalhaMAST.FECHAMENTO_SEM_VERIFICACAO_LIMPA.value
    assert motivo in recibo.mensagem


def test_humano_tambem_nao_fecha_sem_a_prova_edge_case() -> None:
    """Caso de borda: a regra é do livro-razão, não do orquestrador; o humano cai nela também."""
    kernel = _kernel_com_goal()
    assert _submeter(kernel, _verificacao(1, commit_do_codigo="antigo")).sucesso

    recibo = _fechar(kernel, PapelAutor.HUMANO)

    assert not recibo.sucesso and "so o orquestrador conclui o Goal do aceite" in recibo.mensagem


def test_goal_sem_ponta_nao_fecha_edge_case() -> None:
    """Caso de borda: sem a ponta da branch gravada, nenhuma verificação vale para o commit atual."""
    kernel = _kernel_com_goal(ponta_do_ramo=None)
    assert _submeter(kernel, _verificacao(1)).sucesso

    recibo = _fechar(kernel)

    assert not recibo.sucesso and "ponta_do_ramo" in recibo.mensagem


def test_acompanhamento_e_bloqueante_descartado_nao_impedem_o_fechamento_edge_case() -> None:
    """Caso de borda: o acompanhamento é pendência, não prova que falta; o bloqueante que o humano descartou saiu."""
    kernel = _kernel_com_goal()
    assert _submeter(kernel, [*_verificacao(1), *_achado("achado-1", "ver-1", "pendente", "acompanhamento"),
                              *_achado("achado-2", "ver-1", "aberto")]).sucesso
    assert _submeter(kernel, _mover("achado-2", "descartado", motivo_do_descarte="o humano aceita"), PapelAutor.HUMANO).sucesso

    recibo = _fechar(kernel)

    assert recibo.sucesso, recibo.mensagem


def test_descarte_nao_aprova_criterio_so_a_retirada_pelo_humano_tira_da_conta_edge_case() -> None:
    """Caso de borda (ajuste 4): com C1 nao_atende, descartar o Achado não fecha; retirar C1 por Decision do humano fecha."""
    kernel = _kernel_com_goal()
    assert _submeter(kernel, [*_verificacao(1, veredito="rejeitado", c1="nao_atende"), *_achado("achado-1", "ver-1", "aberto")]).sucesso
    assert _submeter(kernel, _mover("achado-1", "descartado", motivo_do_descarte="aceito"), PapelAutor.HUMANO).sucesso

    so_descartado = _fechar(kernel)
    pedido = [*_no("ped-1", TipoNo.DECISION, {"acao_do_humano": "retirar_criterio", "goal": "goal", "alvo": "C1", "motivo": "fora"})]
    assert _submeter(kernel, pedido, PapelAutor.HUMANO).sucesso
    assert _submeter(kernel, [_propriedade("crit-1", "retirado", {"decisao": "ped-1", "motivo": "fora"})]).sucesso
    retirado = _fechar(kernel)

    assert not so_descartado.sucesso and "o criterio crit-1 esta 'nao_atende'" in so_descartado.mensagem
    assert retirado.sucesso, retirado.mensagem


def test_goal_de_antes_do_aceite_no_centro_fecha_como_fechava_edge_case() -> None:
    """Caso de borda: o Goal sem condução nem Criterio (o fluxo do humano de antes) não é alcançado pela regra."""
    kernel = montar_kernel_em_memoria()
    operacoes = [
        ItemPatch(OperacaoPatch.ADD, "/nos/proj", {"id": "proj", "tipo": "Projeto", "rotulo": "p", "propriedades": {}}),
        ItemPatch(OperacaoPatch.ADD, "/nos/setor", {"id": "setor", "tipo": "Setor", "rotulo": "s", "propriedades": {}}),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        ItemPatch(OperacaoPatch.ADD, "/nos/sess", {"id": "sess", "tipo": "Sessao", "rotulo": "s", "propriedades": {}}),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        ItemPatch(OperacaoPatch.ADD, "/nos/g", {"id": "g", "tipo": "Goal", "rotulo": "g", "propriedades": {"status": "pendente"}}),
        _aresta("sess", "g", TipoAresta.PRODUZ),
    ]
    assert _submeter(kernel, operacoes, PapelAutor.HUMANO).sucesso

    recibo = _submeter(kernel, [_propriedade("g", "status", "concluido")], PapelAutor.HUMANO)

    assert recibo.sucesso, recibo.mensagem


def test_criar_o_goal_ja_concluido_tambem_e_conferido_edge_case() -> None:
    """Caso de borda: nascer concluído, com o critério ligado no mesmo lote, não pula a regra."""
    kernel = _kernel_com_goal()
    goal = {"id": "goal-2", "tipo": "Goal", "rotulo": "g2", "propriedades": {"status": "concluido"}}
    criterio = {"id": "crit-2", "tipo": "Criterio", "rotulo": "c", "propriedades": {"codigo": "C1"}}

    recibo = _submeter(kernel, [
        ItemPatch(OperacaoPatch.ADD, "/nos/goal-2", goal), _aresta(SESSAO, "goal-2", TipoAresta.PRODUZ),
        ItemPatch(OperacaoPatch.ADD, "/nos/crit-2", criterio), _aresta(SESSAO, "crit-2", TipoAresta.PRODUZ),
        _aresta("crit-2", "goal-2", TipoAresta.ESCOPA),
    ], PapelAutor.HUMANO)

    assert not recibo.sucesso and "nao tem verificacao" in recibo.mensagem
