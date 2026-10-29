"""O Artifact novo nasce com âncora: o commit do git, ou o sha256 e o caminho do documento fora de código."""

from pathlib import Path
from typing import Any

import pytest

from graphow.core.types import PapelAutor
from graphow.kernel.ancora_do_artifact import ANCORA_COMMIT, ANCORA_SHA256, ancora_do_artifact, diagnosticar_ancora
from graphow.kernel.composicao import abrir_kernel_sqlite
from graphow.kernel.conversao_eventos import ConversorPatchParaEventos
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.kernel.write_kernel import WriteKernel
from graphow.storage.sqlite_store import SQLiteEventStore
from tests.mcp.cenario_governanca import montar_kernel, servidor

SESSAO: str = "sess-a"
COMMIT: str = "0123456789abcdef0123456789abcdef01234567"
SHA256: str = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def _artifact(id_no: str, **propriedades: object) -> list[dict[str, Any]]:
    """O Artifact pendurado na Sessao, como o executor o propõe pelo MCP."""
    produz = f"produz-{SESSAO}-{id_no}"
    return [
        {"op": "add", "path": f"/nos/{id_no}", "value": {"id": id_no, "tipo": "Artifact", "rotulo": id_no, "propriedades": propriedades}},
        {"op": "add", "path": f"/arestas/{produz}", "value": {"id": produz, "origem_id": SESSAO, "destino_id": id_no, "tipo": "produz"}},
    ]


def _propor(kernel: WriteKernel, operacoes: list[dict[str, Any]], papel: str = "executor") -> dict[str, Any]:
    """O `propor_patch` do papel dado, com o recibo aceito ou não."""
    return servidor(kernel, papel).executar_ferramenta("propor_patch", {"operacoes": operacoes, "justificativa": "entrega"})


def test_propor_patch_recusa_artifact_sem_hash_e_aceita_com_sha256_nominal() -> None:
    """Sem hash, o kernel recusa e diz o que falta; com sha256 e caminho, ou com o commit, aceita."""
    kernel = montar_kernel()

    recusa = _propor(kernel, _artifact("art-sem", resumo="relatorio de setembro", arquivos=["relatorio.md"]))
    documento = _propor(kernel, _artifact("art-doc", sha256=SHA256, caminho="relatorios/setembro.md", resumo="relatorio"))
    codigo = _propor(kernel, _artifact("art-cod", commit=COMMIT, arquivos=["soma.py"]))

    assert recusa["sucesso"] is False and recusa["modo_de_falha"] == "artifact_sem_ancora"
    assert "falta 'commit' ou 'sha256'" in recusa["mensagem"] and "40 caracteres" in recusa["mensagem"]
    assert kernel.obter_view().obter_no("art-sem") is None
    assert documento["sucesso"] is True, documento
    assert codigo["sucesso"] is True, codigo


@pytest.mark.parametrize(
    ("propriedades", "falta"),
    [
        ({"commit": "abc123"}, "nao e um hash de commit do git"),
        ({"sha256": SHA256}, "falta 'caminho'"),
        ({"sha256": "abc", "caminho": "a.md"}, "nao tem 64 caracteres hexadecimais"),
        ({"commit": "", "sha256": ""}, "falta 'commit' ou 'sha256'"),
    ],
)
def test_ancora_pela_metade_e_recusada_com_o_que_falta_edge_case(propriedades: dict[str, object], falta: str) -> None:
    """Caso de borda: hash curto, sha256 sem caminho ou sha256 errado não ancoram, de nenhum papel."""
    kernel = montar_kernel()

    recibo = _propor(kernel, _artifact("art-x", **propriedades), papel="humano")

    assert recibo["sucesso"] is False and recibo["modo_de_falha"] == "artifact_sem_ancora"
    assert falta in recibo["mensagem"]


def test_artifact_ancorado_nao_perde_a_ancora_edge_case() -> None:
    """Caso de borda: criar com o commit e apagá-lo no lote seguinte não passa."""
    kernel = montar_kernel()
    assert _propor(kernel, _artifact("art-cod", commit=COMMIT))["sucesso"]

    recibo = _propor(kernel, [{"op": "replace", "path": "/nos/art-cod/propriedades/commit", "value": ""}])

    assert recibo["sucesso"] is False and recibo["modo_de_falha"] == "artifact_sem_ancora"


def test_ancora_do_artifact_diz_a_forma_nominal() -> None:
    """O commit vale primeiro; sem ele, o sha256 com o caminho; sem os dois, nenhuma."""
    assert ancora_do_artifact({"commit": COMMIT, "sha256": SHA256}) == ANCORA_COMMIT
    assert ancora_do_artifact({"sha256": SHA256.upper(), "caminho": "a.md"}) == ANCORA_SHA256
    assert ancora_do_artifact({"resumo": "x"}) is None
    assert diagnosticar_ancora({"commit": COMMIT}) is None


def _banco_com_artifact_antigo(caminho: Path) -> None:
    """Um banco gravado antes da regra: o Artifact sem hash entra no log sem passar pelos portões."""
    operacoes = [ItemPatch(OperacaoPatch(item["op"]), item["path"], item["value"]) for item in _artifact("art-antigo", resumo="feito")]
    proposta = PropostaPatch.criar(DadosPropostaPatch(autor="executor-1", papel=PapelAutor.EXECUTOR, operacoes=tuple(operacoes),
                                                      justificativa="entrega de antes da ancora"))
    eventos = list(montar_kernel().repositorio.ler_eventos("main"))
    eventos += ConversorPatchParaEventos().converter(proposta, len(eventos))
    with SQLiteEventStore(caminho) as store:
        store.append_eventos(eventos)


def test_banco_com_artifact_antigo_sem_hash_faz_replay_e_segue_editavel_nominal(tmp_path: Path) -> None:
    """O replay do log antigo não passa pela regra; o Artifact antigo se edita, e o novo sem hash segue recusado."""
    banco = tmp_path / "antigo.db"
    _banco_com_artifact_antigo(banco)

    store, kernel = abrir_kernel_sqlite(banco)
    try:
        antigo = kernel.obter_view().obter_no("art-antigo")
        edicao = _propor(kernel, [{"op": "replace", "path": "/nos/art-antigo/propriedades/resumo", "value": "revisto"}], papel="humano")
        novo = _propor(kernel, _artifact("art-novo", resumo="feito"))
    finally:
        store.fechar()

    assert antigo is not None and antigo.obter_propriedade("commit") is None
    assert edicao["sucesso"] is True, edicao
    assert novo["sucesso"] is False and novo["modo_de_falha"] == "artifact_sem_ancora"
