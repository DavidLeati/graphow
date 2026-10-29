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
from tests.mcp.cenario_governanca import DONO_DA_POSSE, montar_kernel, servidor

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


def test_commit_do_repositorio_sha256_ancora_nominal() -> None:
    """O repositório `--object-format=sha256` dá commit de 64 hex: é âncora `commit`; 50 hex não é de formato nenhum."""
    kernel = montar_kernel()

    recibo = _propor(kernel, _artifact("art-cod", commit=SHA256, arquivos=["soma.py"]))
    torto = _propor(kernel, _artifact("art-torto", commit=SHA256[:50]))

    assert ancora_do_artifact({"commit": SHA256}) == ANCORA_COMMIT
    assert recibo["sucesso"] is True, recibo
    assert torto["sucesso"] is False and "40 ou 64 caracteres" in torto["mensagem"]


def _deriva(origem: str, destino: str) -> dict[str, Any]:
    """A aresta `deriva_de` do Artifact a uma Task."""
    id_aresta = f"deriva_de-{origem}-{destino}"
    return {"op": "add", "path": f"/arestas/{id_aresta}",
            "value": {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": "deriva_de"}}


def _kernel_com_acao_externa(*, acao_externa_no_executor: bool) -> WriteKernel:
    """O cenário com a Task de código `task-a` livre e as Tasks de ação externa `t-envio` e `t-aviso`."""
    kernel = montar_kernel()
    if acao_externa_no_executor:
        assert servidor(kernel, "humano").executar_ferramenta("configurar_governanca", {
            "escopo": "proj-a", "preset": "personalizada", "personalizada": {"acao_externa": "executor"}})["sucesso"]
    for id_task in ("t-envio", "t-aviso"):
        assert servidor(kernel, "planejador", "orquestrador").executar_ferramenta("criar_tarefa", {
            "titulo": f"Enviar {id_task}", "id_task": id_task, "id_sessao": SESSAO, "entrega": "acao_externa",
            "criterio_pronto": "enviado"})["sucesso"]
    kernel.liberar_lock_task("task-a", DONO_DA_POSSE)
    return kernel


@pytest.mark.parametrize(("papel", "acao_externa_no_executor"), [("executor", False), ("executor", True), ("humano", False)])
def test_isencao_da_acao_externa_pede_todos_os_deriva_de_edge_case(papel: str, acao_externa_no_executor: bool) -> None:
    """Caso de borda (C2): citar uma Task de ação externa ao lado da Task de código não isenta; só ação externa, isenta."""
    kernel = _kernel_com_acao_externa(acao_externa_no_executor=acao_externa_no_executor)
    assert servidor(kernel, papel).executar_ferramenta("assumir_tarefa", {"id_task": "task-a"})["sucesso"]

    misto = _propor(kernel, [*_artifact("art-cod", resumo="soma.py", arquivos=["soma.py"]),
                             _deriva("art-cod", "task-a"), _deriva("art-cod", "t-envio")], papel)
    puro = _propor(kernel, [*_artifact("art-envio", resumo="e-mail enviado"),
                            _deriva("art-envio", "t-envio"), _deriva("art-envio", "t-aviso")], papel)
    solto = _propor(kernel, _artifact("art-solto", resumo="sem deriva_de"), papel)

    assert misto["sucesso"] is False and misto["modo_de_falha"] == "artifact_sem_ancora"
    assert "todos a Tasks de acao externa" in misto["mensagem"]
    assert kernel.obter_view().obter_no("art-cod") is None
    assert puro["sucesso"] is True, puro
    assert solto["sucesso"] is False and solto["modo_de_falha"] == "artifact_sem_ancora"


def test_artifact_isento_nao_ganha_depois_deriva_de_a_task_de_codigo_edge_case() -> None:
    """Caso de borda: o Artifact sem âncora da ação externa não vira, num lote seguinte, entrega da Task de código."""
    kernel = _kernel_com_acao_externa(acao_externa_no_executor=False)
    assert _propor(kernel, [*_artifact("art-envio", resumo="e-mail enviado"), _deriva("art-envio", "t-envio")], "humano")["sucesso"]

    codigo = _propor(kernel, [_deriva("art-envio", "task-a")], "humano")
    outra_acao = _propor(kernel, [_deriva("art-envio", "t-aviso")], "humano")

    assert codigo["sucesso"] is False and codigo["modo_de_falha"] == "artifact_sem_ancora"
    assert "deriva de Task de acao externa e de Task que nao e" in codigo["mensagem"]
    assert outra_acao["sucesso"] is True, outra_acao
