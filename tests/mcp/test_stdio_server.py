"""O ponto de entrada `python -m graphow.mcp.stdio_server` como os subagentes o usam.

Montado só sobre o repositório de eventos, o kernel deste ponto de entrada caía
nos locks em memória: cada processo tinha a sua posse, e o segundo executor
assumia a tarefa que o primeiro já tinha tomado.
"""

import io
import json
from pathlib import Path

import pytest

from graphow.core.types import PapelAutor, StatusTask, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.mcp import stdio_server
from graphow.storage.sqlite_store import SQLiteEventStore


def _no(id_no: str, tipo: TipoNo, propriedades: dict[str, object] | None = None) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades or {}}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _preparar_banco(caminho: Path) -> None:
    """Projeto, Setor, Sessao e uma Task pendente, escritos pelo humano no arquivo."""
    operacoes = (
        _no("proj", TipoNo.PROJETO),
        _no("setor", TipoNo.SETOR),
        _aresta("proj", "setor", TipoAresta.CONTEM),
        _no("sess", TipoNo.SESSAO),
        _aresta("setor", "sess", TipoAresta.CONTEM),
        _no("t1", TipoNo.TASK, {"status": StatusTask.PENDENTE.value}),
        _aresta("sess", "t1", TipoAresta.PRODUZ),
    )
    with SQLiteEventStore(str(caminho)) as store:
        kernel = montar_kernel_sqlite(store)
        dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="base")
        assert kernel.submeter_patch(PropostaPatch.criar(dados)).sucesso


def _rodar_servidor(monkeypatch: pytest.MonkeyPatch, argumentos: list[str], chamadas: list[dict[str, object]]) -> list[dict]:
    """Roda o ponto de entrada com a entrada padrão dada e devolve as respostas JSON-RPC."""
    linhas = [json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize"})]
    for numero, (nome, argumentos_da_chamada) in enumerate(chamadas, start=1):
        params = {"name": nome, "arguments": argumentos_da_chamada}
        linhas.append(json.dumps({"jsonrpc": "2.0", "id": numero, "method": "tools/call", "params": params}))
    saida = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(linhas) + "\n"))
    monkeypatch.setattr("sys.stdout", saida)
    assert stdio_server.main(argumentos) == stdio_server.CODIGO_SUCESSO
    return [json.loads(linha) for linha in saida.getvalue().splitlines() if linha.strip()]


def _resultado(resposta: dict) -> dict:
    """O dicionário que a ferramenta devolveu, desembrulhado do conteúdo textual."""
    return json.loads(resposta["result"]["content"][0]["text"])


def test_dois_processos_do_ponto_de_entrada_nao_dividem_a_posse_nominal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A posse tomada por um processo é vista pelo seguinte, porque mora no arquivo."""
    banco = tmp_path / "graphow.db"
    _preparar_banco(banco)
    base = ["--papel", "executor", "--db", str(banco)]

    primeiro = _rodar_servidor(monkeypatch, [*base, "--autor", "agente-a"], [("assumir_tarefa", {"id_task": "t1"})])
    segundo = _rodar_servidor(monkeypatch, [*base, "--autor", "agente-b"], [("assumir_tarefa", {"id_task": "t1"})])

    assert _resultado(primeiro[1])["sucesso"] is True
    recusa = _resultado(segundo[1])
    assert recusa["sucesso"] is False
    assert recusa["dono_atual"] == "agente-a"
