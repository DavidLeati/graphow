"""O livro do aceite não se reescreve: cada burla da prova de fechamento, no mesmo lote ou não, é recusada no kernel.

Os casos vêm da sonda da revisão adversarial da fase 2 (sonda_fechamento.py):
trocar a ponta, forjar, editar ou remover a verificação, mudar o estado ou a
gravidade do Achado, tirá-lo do grafo, tirar o Goal do alcance da regra e
fechar com o lote que também mexe na prova.
"""

from collections.abc import Sequence

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.patch_models import ItemPatch, OperacaoPatch
from graphow.kernel.write_kernel import ResultadoSubmissao

from tests.kernel.test_fechamento_do_goal import (
    FECHAR,
    _achado,
    _aresta,
    _kernel_com_goal,
    _no,
    _propriedade,
    _submeter,
    _verificacao,
)

HUMANO: PapelAutor = PapelAutor.HUMANO
ORQ: PapelAutor = PapelAutor.ORQUESTRADOR
ABERTO: list[ItemPatch] = [*_verificacao(1), *_achado("achado-1", "ver-1", "aberto")]


def _remover(caminho: str) -> ItemPatch:
    """A remoção do elemento ou da propriedade no caminho."""
    return ItemPatch(OperacaoPatch.REMOVE, caminho)


def _tentar(preparo: Sequence[ItemPatch] | None, lote: Sequence[ItemPatch], papel: PapelAutor) -> ResultadoSubmissao:
    """O preparo, pelo orquestrador, e depois o lote da burla, pelo papel dado."""
    kernel = _kernel_com_goal()
    if preparo:
        recibo = _submeter(kernel, preparo)
        assert recibo.sucesso, recibo.mensagem
    return _submeter(kernel, lote, papel)


VERIFICACAO_VELHA: list[ItemPatch] = _verificacao(1, commit_do_codigo="antigo")
SEM_ALCANCE: list[ItemPatch] = [
    _remover("/nos/goal/propriedades/orquestracao"), _remover("/nos/goal/propriedades/plano"), _remover("/arestas/escopa-crit-1-goal"),
]


@pytest.mark.parametrize(
    ("preparo", "lote", "papel"),
    [
        (VERIFICACAO_VELHA, [_propriedade("goal", "ponta_do_ramo", {"commit": "x", "commit_do_codigo": "antigo"}), FECHAR], HUMANO),
        (VERIFICACAO_VELHA, [_propriedade("goal", "ponta_do_ramo", {"commit": "x", "commit_do_codigo": "antigo"}), FECHAR], ORQ),
        ([*VERIFICACAO_VELHA, _propriedade("goal", "ponta_do_ramo", {"commit_do_codigo": "antigo"})], [FECHAR], HUMANO),
        (ABERTO, [_propriedade("achado-1", "estado", "resolvido"), FECHAR], HUMANO),
        (ABERTO, [_propriedade("achado-1", "estado", "resolvido"), FECHAR], ORQ),
        (ABERTO, [_remover("/nos/achado-1"), FECHAR], HUMANO),
        (ABERTO, [_remover("/nos/achado-1/propriedades/gravidade"), FECHAR], HUMANO),
        (ABERTO, [_remover("/arestas/deriva_de-achado-1-ver-1"), FECHAR], HUMANO),
        (None, [*_verificacao(99), FECHAR], HUMANO),
        (None, [*SEM_ALCANCE, FECHAR], HUMANO),
        (None, [*SEM_ALCANCE[:2], _remover("/nos/crit-1"), FECHAR], HUMANO),
        (None, [*SEM_ALCANCE, FECHAR], ORQ),
        (_verificacao(1, c1="parcial"), [_propriedade("ver-1", "pareceres", [{"no": "crit-1", "veredito": "atende"}]), FECHAR], HUMANO),
        (_verificacao(1, c1="parcial"), [_propriedade("ver-1", "pareceres", [{"no": "crit-1", "veredito": "atende"}]), FECHAR], ORQ),
        (_verificacao(1, final=False), [_propriedade("ver-1", "final", True), FECHAR], HUMANO),
        (_verificacao(1), [*_no("ver-x", TipoNo.EVIDENCE, {"acao": "verificacao_do_goal", "final": True, "veredito": "rejeitado"}),
                           _aresta("ver-x", "goal", TipoAresta.DERIVA_DE), FECHAR], ORQ),
        (_verificacao(1), [*_no("ver-x", TipoNo.EVIDENCE, {"acao": "verificacao_do_goal", "numero": "9", "final": True,
                                                            "veredito": "rejeitado"}),
                           _aresta("ver-x", "goal", TipoAresta.DERIVA_DE), FECHAR], ORQ),
        ([*_verificacao(1), *_verificacao(2, veredito="rejeitado")], [_remover("/nos/ver-2"), FECHAR], HUMANO),
        (_verificacao(1), [*_no("crit-9", TipoNo.CRITERIO, {"codigo": "C9"}), _aresta("crit-9", "goal", TipoAresta.ESCOPA), FECHAR], ORQ),
        (_verificacao(1), [_remover("/nos/goal/propriedades/ponta_do_ramo"), FECHAR], HUMANO),
        (VERIFICACAO_VELHA, [ItemPatch(OperacaoPatch.ADD, "/nos/goal/propriedades/status", "concluido")], HUMANO),
    ],
    ids=["A-ponta-no-lote-humano", "A-ponta-no-lote-orq", "A-ponta-antes-humano-fecha", "B-resolve-no-lote-humano",
         "B-resolve-no-lote-orq", "C-remove-achado", "C2-remove-gravidade", "C3-remove-deriva-de", "D-verificacao-forjada",
         "E-tira-do-alcance", "E2-remove-criterio", "E3-tira-do-alcance-orq", "G-reescreve-pareceres", "G-reescreve-pareceres-orq",
         "G2-vira-final", "I-verificacao-sem-numero", "J-numero-texto", "K-remove-a-ultima", "M-criterio-novo-no-fechamento",
         "N-remove-a-ponta", "P-status-por-add"],
)
def test_cada_burla_do_fechamento_e_recusada_edge_case(
    preparo: list[ItemPatch] | None, lote: list[ItemPatch], papel: PapelAutor
) -> None:
    """Caso de borda: nenhuma burla da sonda fecha o Goal, venha de quem vier."""
    recibo = _tentar(preparo, lote, papel)

    assert not recibo.sucesso, recibo.mensagem
    assert recibo.modo_de_falha in (ModoFalhaMAST.ALTERACAO_DO_LIVRO_DO_ACEITE.value, ModoFalhaMAST.FECHAMENTO_SEM_VERIFICACAO_LIMPA.value,
                                    ModoFalhaMAST.VIOLACAO_PERMISSAO_PAPEL.value)


def test_achado_sem_a_verificacao_de_onde_deriva_nao_nasce_edge_case() -> None:
    """Caso de borda (L da sonda): o Achado bloqueante solto, só com `fere`, é recusado já na criação."""
    recibo = _tentar(_verificacao(1), [*_no("ach-x", TipoNo.ACHADO, {"gravidade": "bloqueante", "estado": "aberto"}),
                                       _aresta("ach-x", "crit-1", TipoAresta.FERE)], ORQ)

    assert not recibo.sucesso and "deriva, no mesmo lote, da verificacao" in recibo.mensagem


def test_orquestrador_fecha_num_lote_que_so_fecha_nominal() -> None:
    """O fechamento legítimo: a prova em lotes anteriores e um lote só com o status do Goal e o da Sessao."""
    recibo = _tentar(_verificacao(1), [FECHAR, _propriedade("goal", "integrado_em", "cod123"),
                                       _propriedade("orq-sessao-goal", "status", "concluida")], ORQ)

    assert recibo.sucesso, recibo.mensagem


def test_humano_cancela_com_motivo_e_nao_conclui_nominal() -> None:
    """O humano não conclui o Goal do aceite: cancela, e o cancelamento pede o motivo."""
    sem_motivo = _tentar(None, [_propriedade("goal", "status", "cancelado")], HUMANO)
    com_motivo = _tentar(None, [_propriedade("goal", "status", "cancelado"),
                                _propriedade("goal", "motivo_do_cancelamento", "o cliente desistiu")], HUMANO)
    pelo_orquestrador = _tentar(None, [_propriedade("goal", "status", "cancelado"),
                                       _propriedade("goal", "motivo_do_cancelamento", "x")], ORQ)

    assert not sem_motivo.sucesso and "motivo_do_cancelamento" in sem_motivo.mensagem
    assert com_motivo.sucesso, com_motivo.mensagem
    assert not pelo_orquestrador.sucesso


@pytest.mark.parametrize(
    ("estado", "extra", "papel", "passa"),
    [
        ("corrigido", {"commit_da_correcao": "abc"}, ORQ, True),
        ("corrigido", {}, ORQ, False),
        ("corrigido", {"commit_da_correcao": "abc"}, HUMANO, False),
        ("descartado", {"motivo_do_descarte": "o humano aceita o risco"}, HUMANO, True),
        ("descartado", {}, HUMANO, False),
        ("descartado", {"motivo_do_descarte": "x"}, ORQ, False),
        ("resolvido", {}, ORQ, True),
        ("resolvido", {}, HUMANO, False),
        ("pendente", {}, ORQ, False),
    ],
)
def test_transicoes_do_achado_aberto_edge_case(estado: str, extra: dict[str, str], papel: PapelAutor, passa: bool) -> None:
    """Caso de borda: o Achado aberto só anda pelas transições do livro, com o que cada uma exige, pelo papel dela."""
    lote = [_propriedade("achado-1", "estado", estado), *(_propriedade("achado-1", chave, valor) for chave, valor in extra.items())]

    recibo = _tentar(ABERTO, lote, papel)

    assert recibo.sucesso is passa, recibo.mensagem


def test_achado_nao_volta_a_aberto_nem_muda_a_gravidade_edge_case() -> None:
    """Caso de borda: o descartado não reabre por edição, e a gravidade não muda depois de gravada."""
    descartado = [*ABERTO, ]
    kernel = _kernel_com_goal()
    assert _submeter(kernel, descartado).sucesso
    assert _submeter(kernel, [_propriedade("achado-1", "estado", "descartado"),
                              _propriedade("achado-1", "motivo_do_descarte", "aceito")], HUMANO).sucesso

    reaberto = _submeter(kernel, [_propriedade("achado-1", "estado", "aberto")], HUMANO)
    rebaixado = _submeter(kernel, [_propriedade("achado-1", "gravidade", "acompanhamento")], ORQ)

    assert not reaberto.sucesso and not rebaixado.sucesso


def test_derivadas_do_criterio_e_fere_sao_do_orquestrador_edge_case() -> None:
    """Caso de borda: o humano não escreve o estado do Criterio nem cria `fere`; o orquestrador sim."""
    humano_estado = _tentar(None, [_propriedade("crit-1", "estado", "atende")], HUMANO)
    orq_estado = _tentar(None, [_propriedade("crit-1", "estado", "atende")], ORQ)
    humano_fere = _tentar(ABERTO, [_aresta("achado-1", "crit-1", TipoAresta.FERE)], HUMANO)

    assert not humano_estado.sucesso and orq_estado.sucesso
    assert not humano_fere.sucesso


VERIFICACAO_FORJADA: dict[str, object] = {"numero": 7, "final": True, "veredito": "aprovado", "commit": "cod123",
                                          "commit_do_codigo": "cod123",
                                          "pareceres": [{"id": "C1", "no": "crit-1", "veredito": "atende", "prova": "forjada"}]}
ACAO: ItemPatch = _propriedade("ver-f", "acao", "verificacao_do_goal")
LIGA: ItemPatch = _aresta("ver-f", "goal", TipoAresta.DERIVA_DE)


@pytest.mark.parametrize(
    ("preparo", "lote", "papel"),
    [
        (None, [*_no("ver-f", TipoNo.EVIDENCE, VERIFICACAO_FORJADA), ACAO, LIGA], HUMANO),
        (None, [*_no("ver-f", TipoNo.EVIDENCE, VERIFICACAO_FORJADA), LIGA, ACAO], HUMANO),
        ([*_no("ver-f", TipoNo.EVIDENCE, VERIFICACAO_FORJADA)], [ACAO, LIGA], ORQ),
        ([*_no("ver-f", TipoNo.EVIDENCE, VERIFICACAO_FORJADA)], [ACAO], HUMANO),
        (None, [*_no("ped-x", TipoNo.DECISION, {"goal": "goal", "motivo": "x"}),
                _propriedade("ped-x", "acao_do_humano", "descartar_achado")], ORQ),
        (None, [*_no("rev-f", TipoNo.EVIDENCE, {}), _propriedade("rev-f", "acao", "revisao_de_risco")], HUMANO),
        (None, [*_no("crit-h", TipoNo.CRITERIO, {"codigo": "C9", "estado": "atende"})], HUMANO),
        (None, [*_no("crit-h", TipoNo.CRITERIO, {"codigo": "C9"}), _propriedade("crit-h", "testes_de_aceite", [])], HUMANO),
        (_verificacao(1), [*_no("ach-x", TipoNo.ACHADO, {"gravidade": "bloqueante", "estado": "aberto"}),
                           _aresta("ach-x", "ver-1", TipoAresta.DERIVA_DE), _propriedade("ach-x", "estado", "descartado")], ORQ),
    ],
    ids=["acao-num-patch-posterior", "aresta-antes-da-acao", "acao-num-lote-seguinte-orq", "acao-num-lote-seguinte-humano",
         "pedido-forjado-pelo-orquestrador", "revisao-forjada-pelo-humano", "criterio-humano-ja-atende",
         "criterio-humano-com-testes", "achado-nasce-e-muda-no-lote"],
)
def test_o_livro_julga_o_no_pelo_que_ele_e_no_fim_do_lote_edge_case(
    preparo: list[ItemPatch] | None, lote: list[ItemPatch], papel: PapelAutor
) -> None:
    """Caso de borda (N1): a verificação, o pedido, a revisão, o Criterio e o Achado são julgados pelo estado final, não pela operação."""
    recibo = _tentar(preparo, lote, papel)

    assert not recibo.sucesso, recibo.mensagem
    assert recibo.modo_de_falha == ModoFalhaMAST.ALTERACAO_DO_LIVRO_DO_ACEITE.value


def test_o_criterio_do_gerente_nasce_pendente_nominal() -> None:
    """O humano (o gerente) grava o Criterio com código, texto, verificação e o estado pendente."""
    recibo = _tentar(None, [*_no("crit-h", TipoNo.CRITERIO, {"codigo": "C9", "texto": "x", "verificacao": "teste",
                                                            "estado": "pendente"})], HUMANO)

    assert recibo.sucesso, recibo.mensagem


def test_aresta_antes_do_no_nem_chega_ao_livro_edge_case() -> None:
    """Caso de borda: a aresta que liga a verificação forjada antes de o nó existir no lote é recusada já pela estrutura."""
    recibo = _tentar(None, [LIGA, *_no("ver-f", TipoNo.EVIDENCE, VERIFICACAO_FORJADA), ACAO], HUMANO)

    assert not recibo.sucesso and recibo.modo_de_falha == "referencia_inexistente"
