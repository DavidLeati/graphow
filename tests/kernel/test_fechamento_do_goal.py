"""O kernel só deixa o Goal do aceite no centro fechar com a verificação final limpa no commit atual."""

from collections.abc import Sequence
from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel import invariant_gate
from graphow.kernel.composicao import montar_kernel_em_memoria
from graphow.kernel.fechamento_do_goal import motivos_para_nao_fechar
from graphow.kernel.papel_do_orquestrador import sessao_do_goal
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch, ResultadoValidacao
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


def _com_c2(kernel: WriteKernel) -> None:
    """O segundo critério do Goal, C2, como nó que o escopa."""
    assert _submeter(kernel, [*_no("crit-2", TipoNo.CRITERIO, {"codigo": "C2", "texto": "subtrair", "verificacao": "teste"}),
                              _aresta("crit-2", "goal", TipoAresta.ESCOPA)]).sucesso


def _verificacao_com_c2(numero: int, *, c1: str, c2: str = "atende") -> list[ItemPatch]:
    """A verificação final com parecer para C1 e C2."""
    lote = _verificacao(numero, veredito="rejeitado" if "nao_atende" in (c1, c2) else "aprovado", c1=c1)
    valor = dict(lote[0].value)
    valor["propriedades"] = {**valor["propriedades"], "pareceres": [*valor["propriedades"]["pareceres"],
                                                                    {"id": "C2", "no": "crit-2", "veredito": c2, "prova": "aceite verde"}]}
    return [ItemPatch(OperacaoPatch.ADD, lote[0].path, valor), *lote[1:]]


def test_descarte_nao_aprova_criterio_so_a_retirada_pelo_humano_tira_da_conta_edge_case() -> None:
    """Caso de borda (ajuste 4): com C1 nao_atende, descartar o Achado não fecha; retirar C1 por pedido do humano fecha com C2."""
    kernel = _kernel_com_goal()
    _com_c2(kernel)
    assert _submeter(kernel, [*_verificacao_com_c2(1, c1="nao_atende"), *_achado("achado-1", "ver-1", "aberto")]).sucesso
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


def _pedido(id_no: str, **propriedades: object) -> list[ItemPatch]:
    """A Decision do humano: um pedido ao laço, ou uma Decision qualquer quando não leva `acao_do_humano`."""
    return _no(id_no, TipoNo.DECISION, {"motivo": "m", **propriedades})


@pytest.mark.parametrize(
    ("decisao", "vale"),
    [
        (_pedido("dec", acao_do_humano="retirar_criterio", goal="goal", alvo="C1"), True),
        (_pedido("dec", acao_do_humano="recusar_plano", goal="goal", alvo=""), True),
        (_pedido("dec", texto="usar SQLite"), False),
        (_pedido("dec", acao_do_humano="retirar_criterio", goal="goal", alvo="C2"), False),
        (_pedido("dec", acao_do_humano="retirar_criterio", goal="outro-goal", alvo="C1"), False),
        (_pedido("dec", acao_do_humano="descartar_achado", goal="goal", alvo="C1"), False),
    ],
    ids=["retirar-c1", "recusar-plano", "decision-comum", "retirar-outro-criterio", "retirar-de-outro-goal", "outro-pedido"],
)
def test_retirada_so_vale_citando_o_pedido_que_retira_o_criterio_edge_case(decisao: list[ItemPatch], vale: bool) -> None:
    """Caso de borda (rodada 4, item 4): `retirado` cita o retirar_criterio deste critério deste Goal, ou o recusar_plano."""
    kernel = _kernel_com_goal()
    assert _submeter(kernel, decisao, PapelAutor.HUMANO).sucesso

    recibo = _submeter(kernel, [_propriedade("crit-1", "retirado", {"decisao": "dec", "motivo": "m"})])

    assert recibo.sucesso is vale, recibo.mensagem
    assert vale or "cita o pedido do humano que o retira deste Goal" in recibo.mensagem


def test_fechamento_nao_conta_a_retirada_que_cita_outra_decision_nem_com_o_livro_aberto_edge_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caso de borda: com a regra do livro desligada, a retirada que cita uma Decision qualquer não tira C1 da conta."""
    monkeypatch.setattr(invariant_gate, "validar_livro_do_aceite", lambda proposta, estado: ResultadoValidacao.sucesso())
    kernel = _kernel_com_goal()
    assert _submeter(kernel, [*_pedido("dec-g", texto="usar SQLite"), *_pedido("ped-2", acao_do_humano="retirar_criterio",
                                                                               goal="goal", alvo="C9")], PapelAutor.HUMANO).sucesso
    assert _submeter(kernel, _verificacao(1, veredito="rejeitado", c1="nao_atende")).sucesso

    for decisao in ("dec-g", "ped-2"):
        assert _submeter(kernel, [_propriedade("crit-1", "retirado", {"decisao": decisao, "motivo": "m"})]).sucesso
        assert "o criterio crit-1 esta 'nao_atende'" in "; ".join(motivos_para_nao_fechar(kernel.obter_view(), "goal"))


def _retirar(kernel: WriteKernel, *codigos: str) -> None:
    """O pedido do humano que retira cada critério, e a retirada que o orquestrador grava ao atendê-lo."""
    for codigo in codigos:
        id_no = f"crit-{codigo[1:]}"
        assert _submeter(kernel, _pedido(f"ped-{codigo}", acao_do_humano="retirar_criterio", goal="goal", alvo=codigo),
                         PapelAutor.HUMANO).sucesso
        assert _submeter(kernel, [_propriedade(id_no, "retirado", {"decisao": f"ped-{codigo}", "motivo": "m"})]).sucesso


CANCELAR_SEM_CRITERIO: list[ItemPatch] = [_propriedade("goal", "status", "cancelado"),
                                          _propriedade("goal", "motivo_do_cancelamento", "todos os criterios foram retirados")]


def test_goal_com_todos_os_criterios_retirados_nao_conclui_e_o_orquestrador_o_cancela_edge_case() -> None:
    """Caso de borda (rodada 4, item 1): sem critério na conta, o Goal não conclui; o orquestrador o cancela, com o motivo."""
    kernel = _kernel_com_goal()
    _com_c2(kernel)
    assert _submeter(kernel, _verificacao_com_c2(1, c1="nao_atende", c2="nao_atende")).sucesso
    _retirar(kernel, "C1", "C2")

    fechar = _fechar(kernel)
    sem_motivo = _submeter(kernel, CANCELAR_SEM_CRITERIO[:1])
    cancelar = _submeter(kernel, CANCELAR_SEM_CRITERIO)

    assert not fechar.sucesso and "todos os criterios do Goal foram retirados" in fechar.mensagem
    assert not sem_motivo.sucesso and "pede 'motivo_do_cancelamento'" in sem_motivo.mensagem
    assert cancelar.sucesso, cancelar.mensagem


def test_orquestrador_nao_cancela_o_goal_com_criterio_na_conta_edge_case() -> None:
    """Caso de borda: com C2 ainda na conta, o cancelamento é só do humano."""
    kernel = _kernel_com_goal()
    _com_c2(kernel)
    _retirar(kernel, "C1")

    do_orquestrador = _submeter(kernel, CANCELAR_SEM_CRITERIO)
    do_humano = _submeter(kernel, CANCELAR_SEM_CRITERIO, PapelAutor.HUMANO)

    assert not do_orquestrador.sucesso and "so quando todos os criterios dele foram retirados" in do_orquestrador.mensagem
    assert do_humano.sucesso, do_humano.mensagem
