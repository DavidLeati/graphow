"""A Evidence sobre código nasce com o commit em que foi vista; a antiga, sem ele, segue no log e editável."""

from pathlib import Path
from typing import Any

import pytest

from graphow.core.falhas import ModoFalhaMAST
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.ancora_da_evidencia import arquivos_afirmados, sobre_codigo
from graphow.kernel.composicao import abrir_kernel_sqlite, montar_kernel_em_memoria
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import ResultadoSubmissao, WriteKernel
from graphow.storage.sqlite_store import SQLiteEventStore

COMMIT: str = "0123456789abcdef0123456789abcdef01234567"
SHA256: str = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
LIDA: dict[str, object] = {"arquivo": "src/precos/fator.py", "linhas": "40", "trecho": "return (1 + taxa) ** (-dias / 252)"}
SEM_ANCORA: str = ModoFalhaMAST.EVIDENCIA_SEM_ANCORA.value


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, Any] | None = None) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(OperacaoPatch.ADD, f"/nos/{id_no}", valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    return ItemPatch(OperacaoPatch.ADD, f"/arestas/{id_aresta}", {"id": id_aresta, "origem_id": origem, "destino_id": destino,
                                                                    "tipo": tipo.value})


def _proposta(papel: PapelAutor, operacoes: list[ItemPatch], goal: str | None = None) -> PropostaPatch:
    """O lote do papel dado; o do orquestrador diz o Goal que conduz."""
    autor = "graphow-orquestrar" if papel == PapelAutor.ORQUESTRADOR else f"autor-{papel.value}"
    return PropostaPatch.criar(DadosPropostaPatch(autor=autor, papel=papel, operacoes=tuple(operacoes), justificativa="teste",
                                                  goal_conduzido=goal))


def _submeter(kernel: WriteKernel, papel: PapelAutor, operacoes: list[ItemPatch], goal: str | None = None) -> ResultadoSubmissao:
    """Submete o lote sob o papel dado."""
    return kernel.submeter_patch(_proposta(papel, operacoes, goal))


def _evidencia(papel: PapelAutor, id_no: str, propriedades: dict[str, object], sessao: str = "sess") -> list[ItemPatch]:
    """A Evidence pendurada na Sessao."""
    return [_no(id_no, TipoNo.EVIDENCE, propriedades), _aresta(sessao, id_no, TipoAresta.PRODUZ)]


@pytest.fixture
def kernel() -> WriteKernel:
    """Projeto, Setor e Sessao do humano; a Sessao do orquestrador e o Goal que ele conduz."""
    kernel = montar_kernel_em_memoria()
    humano = _submeter(kernel, PapelAutor.HUMANO, [
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO), _aresta("setor", "sess", TipoAresta.CONTEM),
    ])
    assert humano.sucesso, humano.mensagem
    recibo = _submeter(kernel, PapelAutor.ORQUESTRADOR, [
        _no("orq-sessao-goal", TipoNo.SESSAO), _aresta("setor", "orq-sessao-goal", TipoAresta.CONTEM),
        _no("goal", TipoNo.GOAL, {"orquestracao": {"modo": "autonomo"}}), _aresta("orq-sessao-goal", "goal", TipoAresta.PRODUZ),
    ], goal="goal")
    assert recibo.sucesso, recibo.mensagem
    return kernel


def test_kernel_recusa_a_evidence_nova_sobre_codigo_sem_commit_nominal(kernel: WriteKernel) -> None:
    """T3d1.3: a leitura localizada num arquivo e a verificação do orquestrador sem commit são recusadas; com ele, aceitas."""
    leitura = _submeter(kernel, PapelAutor.PLANEJADOR, _evidencia(PapelAutor.PLANEJADOR, "evi-lida", dict(LIDA)))
    verificacao = {"acao": "revisao_de_risco", "veredito": "aprovado", "arquivos": ["soma.py"]}
    do_orquestrador = _submeter(kernel, PapelAutor.ORQUESTRADOR,
                                [*_evidencia(PapelAutor.ORQUESTRADOR, "rev-1", verificacao, "orq-sessao-goal")], goal="goal")
    leitura_ancorada = _submeter(kernel, PapelAutor.PLANEJADOR, _evidencia(PapelAutor.PLANEJADOR, "evi-ok", {**LIDA, "commit": COMMIT}))
    ancorada = _submeter(kernel, PapelAutor.ORQUESTRADOR,
                         [*_evidencia(PapelAutor.ORQUESTRADOR, "rev-2", {**verificacao, "commit": COMMIT}, "orq-sessao-goal")], goal="goal")

    assert leitura.sucesso is False and leitura.modo_de_falha == SEM_ANCORA
    assert "falta 'commit' ou, fora de repositorio git, 'sha256'" in leitura.mensagem and "git rev-parse HEAD" in leitura.mensagem
    assert do_orquestrador.sucesso is False and do_orquestrador.modo_de_falha == SEM_ANCORA
    assert "falta 'commit'" in do_orquestrador.mensagem
    assert kernel.obter_view().obter_no("evi-lida") is None and kernel.obter_view().obter_no("rev-1") is None
    assert leitura_ancorada.sucesso, leitura_ancorada.mensagem
    assert ancorada.sucesso, ancorada.mensagem


def test_localizada_fora_do_git_ancora_no_sha256_e_o_orquestrador_nao_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: a ata lida fora de repositório git passa com o sha256; o orquestrador só com o commit."""
    ata = _submeter(kernel, PapelAutor.EXECUTOR, _evidencia(PapelAutor.EXECUTOR, "evi-ata", {**LIDA, "sha256": SHA256}))
    curto = _submeter(kernel, PapelAutor.EXECUTOR, _evidencia(PapelAutor.EXECUTOR, "evi-curta", {**LIDA, "sha256": "abc"}))
    do_orquestrador = _submeter(kernel, PapelAutor.ORQUESTRADOR,
                                [*_evidencia(PapelAutor.ORQUESTRADOR, "rev-1", {"sha256": SHA256, "arquivo": "a.py"}, "orq-sessao-goal")],
                                goal="goal")

    assert ata.sucesso, ata.mensagem
    assert curto.modo_de_falha == SEM_ANCORA and "nao tem 64 caracteres" in curto.mensagem
    assert do_orquestrador.modo_de_falha == SEM_ANCORA


@pytest.mark.parametrize(
    "propriedades",
    [{"arquivo": "saida/pytest.log", "resultado": "14 passed"}, {"fonte": "https://exemplo.org/ata", "trecho": "aprovado"},
     {"resumo": "a suite passou"}],
    ids=["log-de-teste", "fonte-generica", "sem-ponteiro"],
)
def test_evidence_que_nao_e_sobre_codigo_segue_livre_edge_case(kernel: WriteKernel, propriedades: dict[str, object]) -> None:
    """Caso de borda: o log anexado, a fonte genérica e a Evidence sem ponteiro do agente não pedem commit."""
    recibo = _submeter(kernel, PapelAutor.EXECUTOR, _evidencia(PapelAutor.EXECUTOR, "evi", propriedades))

    assert recibo.sucesso, recibo.mensagem


def test_evidence_ancorada_nao_perde_o_commit_edge_case(kernel: WriteKernel) -> None:
    """Caso de borda: apagar o commit da leitura ancorada, no lote seguinte, não passa."""
    assert _submeter(kernel, PapelAutor.EXECUTOR, _evidencia(PapelAutor.EXECUTOR, "evi", {**LIDA, "commit": COMMIT})).sucesso

    recibo = _submeter(kernel, PapelAutor.EXECUTOR, [ItemPatch(OperacaoPatch.REPLACE, "/nos/evi/propriedades/commit", "")])

    assert recibo.modo_de_falha == SEM_ANCORA


def test_evidence_que_vira_sobre_codigo_no_segundo_lote_precisa_de_commit_nominal(kernel: WriteKernel) -> None:
    """T3d3.1: o executor cria o log (`arquivo` sozinho) e põe `linhas` e `trecho` depois: o segundo lote é recusado."""
    log = {"arquivo": "src/x.py", "resultado": "lido"}
    assert _submeter(kernel, PapelAutor.EXECUTOR, _evidencia(PapelAutor.EXECUTOR, "evi", log)).sucesso

    recibo = _submeter(kernel, PapelAutor.EXECUTOR, [ItemPatch(OperacaoPatch.ADD, "/nos/evi/propriedades/linhas", "1-2"),
                                                     ItemPatch(OperacaoPatch.ADD, "/nos/evi/propriedades/trecho", "a = 1")])
    ancorado = _submeter(kernel, PapelAutor.EXECUTOR, [ItemPatch(OperacaoPatch.ADD, "/nos/evi/propriedades/linhas", "1-2"),
                                                       ItemPatch(OperacaoPatch.ADD, "/nos/evi/propriedades/trecho", "a = 1"),
                                                       ItemPatch(OperacaoPatch.ADD, "/nos/evi/propriedades/commit", COMMIT)])

    assert recibo.modo_de_falha == SEM_ANCORA and "Evidence 'evi' sem ancora" in recibo.mensagem
    assert ancorado.sucesso, ancorado.mensagem


def test_planejador_que_troca_a_fonte_por_arquivo_e_linhas_precisa_de_commit_nominal(kernel: WriteKernel) -> None:
    """T3d3.1: a Evidence que nasce com `fonte` e `trecho` e vira leitura de arquivo no lote seguinte é recusada."""
    fonte = {"fonte": "conversa", "trecho": "a = 1"}
    assert _submeter(kernel, PapelAutor.PLANEJADOR, _evidencia(PapelAutor.PLANEJADOR, "evi-p", fonte)).sucesso

    recibo = _submeter(kernel, PapelAutor.PLANEJADOR, [ItemPatch(OperacaoPatch.REMOVE, "/nos/evi-p/propriedades/fonte"),
                                                       ItemPatch(OperacaoPatch.ADD, "/nos/evi-p/propriedades/arquivo", "src/x.py"),
                                                       ItemPatch(OperacaoPatch.ADD, "/nos/evi-p/propriedades/linhas", "1")])

    assert recibo.modo_de_falha == SEM_ANCORA
    assert kernel.obter_view().obter_no("evi-p").obter_propriedade("fonte") == "conversa"  # type: ignore[union-attr]


def test_arquivos_afirmados_e_sobre_codigo_nominal() -> None:
    """A lista gravada vale primeiro; sem ela, o arquivo da localizada; sem nenhum, a Evidence fala do commit inteiro."""
    assert arquivos_afirmados({"arquivos": ["a.py", "b.py"], "arquivo": "c.py"}) == ("a.py", "b.py")
    assert arquivos_afirmados(dict(LIDA)) == ("src/precos/fator.py",)
    assert arquivos_afirmados({"commit": COMMIT}) is None
    assert sobre_codigo(PapelAutor.ORQUESTRADOR.value, {}) and sobre_codigo(PapelAutor.REVISOR.value, dict(LIDA))
    assert not sobre_codigo(PapelAutor.EXECUTOR.value, {"arquivo": "saida/pytest.log"})


def _banco_com_evidence_antiga(caminho: Path) -> None:
    """Um banco gravado antes da regra: a leitura localizada sem commit entra no log sem passar pelos portões."""
    preparo = _proposta(PapelAutor.HUMANO, [_no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR),
                                            _aresta("proj", "setor", TipoAresta.CONTEM), _no("sess", TipoNo.SESSAO),
                                            _aresta("setor", "sess", TipoAresta.CONTEM)])
    antiga = _proposta(PapelAutor.PLANEJADOR, _evidencia(PapelAutor.PLANEJADOR, "evi-antiga", dict(LIDA)))
    eventos = ConversorPatchParaEventos().converter(preparo, 0)
    eventos += ConversorPatchParaEventos().converter(antiga, len(eventos))
    with SQLiteEventStore(caminho) as store:
        store.append_eventos(eventos)


def test_banco_com_evidence_antiga_sem_commit_faz_replay_e_segue_editavel_nominal(tmp_path: Path) -> None:
    """O replay do log antigo não passa pela regra; a antiga, já sobre código, se edita (T3d3.1), e a nova sem commit não."""
    banco = tmp_path / "antigo.db"
    _banco_com_evidence_antiga(banco)

    store, kernel = abrir_kernel_sqlite(banco)
    try:
        antiga = kernel.obter_view().obter_no("evi-antiga")
        edicao = _submeter(kernel, PapelAutor.HUMANO, [ItemPatch(OperacaoPatch.ADD, "/nos/evi-antiga/propriedades/resumo", "revisto"),
                                                       ItemPatch(OperacaoPatch.REPLACE, "/nos/evi-antiga/propriedades/linhas", "40-41")])
        nova = _submeter(kernel, PapelAutor.PLANEJADOR, _evidencia(PapelAutor.PLANEJADOR, "evi-nova", dict(LIDA)))
    finally:
        store.fechar()

    assert antiga is not None and antiga.obter_propriedade("commit") is None
    assert edicao.sucesso, edicao.mensagem
    assert nova.modo_de_falha == SEM_ANCORA
