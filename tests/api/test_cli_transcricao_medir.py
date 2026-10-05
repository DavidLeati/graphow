"""`graphow transcricao-medir`: a linha de base lida das transcrições, com o banco só lido."""

import json
from pathlib import Path

from graphow.api.cli_execucao import CODIGO_SUCESSO, ExecutorLinhaDeComando
from graphow.api.cli_parser import construir_parser
from graphow.api.console import EscritorConsoleEmMemoria
from graphow.core.types import PapelAutor, TipoAresta, TipoNo
from graphow.kernel.composicao import montar_kernel_sqlite
from graphow.kernel.patch_models import DadosPropostaPatch, ItemPatch, OperacaoPatch, PropostaPatch
from graphow.storage.localizador_banco import AmbienteEmMemoria, LocalizadorBancoEventos
from graphow.storage.sqlite_store import SQLiteEventStore


def _executar(argumentos: list[str], diretorio_dados: Path) -> EscritorConsoleEmMemoria:
    """Executa o subcomando com o diretório de dados num caminho temporário."""
    console = EscritorConsoleEmMemoria()
    ambiente = AmbienteEmMemoria({"LOCALAPPDATA": str(diretorio_dados)}, diretorio_dados)
    executor = ExecutorLinhaDeComando(console, LocalizadorBancoEventos(ambiente))
    assert executor.executar(construir_parser().parse_args(argumentos)) == CODIGO_SUCESSO
    return console


def _transcricao(caminho: Path, id_task: str, tokens: int) -> Path:
    """Uma transcrição de executor que assume a tarefa, lê o alvo pelo Read e um arquivo de fora pelo Bash."""
    leituras = [
        {"type": "tool_use", "id": "toolu_a", "name": "mcp__graphow-executor__assumir_tarefa", "input": {"id_task": id_task}},
        {"type": "tool_use", "id": "toolu_r1", "name": "Read", "input": {"file_path": "C:/repo/src/alvo.py"}},
        {"type": "tool_use", "id": "toolu_r2", "name": "Bash", "input": {"command": "cd /c/repo; sed -n 1,80p src/fora.py | head"}},
    ]
    linhas = [
        {"type": "assistant", "timestamp": "2026-10-01T10:00:00Z",
         "message": {"id": "m1", "model": "claude-sonnet-5", "usage": {"input_tokens": tokens}, "content": leituras}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_r2", "content": "x" * 3000}]}},
        {"type": "assistant", "timestamp": "2026-10-01T10:10:00Z",
         "message": {"id": "m2", "model": "claude-sonnet-5", "usage": {"input_tokens": tokens}, "content": []}},
    ]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8")
    return caminho


def _no(id_no: str, tipo: TipoNo, **propriedades: object) -> ItemPatch:
    """Criação de nó com rótulo igual ao id."""
    valor = {"id": id_no, "tipo": tipo.value, "rotulo": id_no, "propriedades": propriedades}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/nos/{id_no}", value=valor)


def _aresta(origem: str, destino: str, tipo: TipoAresta) -> ItemPatch:
    """Criação de aresta com id derivado das pontas."""
    id_aresta = f"{tipo.value}-{origem}-{destino}"
    valor = {"id": id_aresta, "origem_id": origem, "destino_id": destino, "tipo": tipo.value}
    return ItemPatch(op=OperacaoPatch.ADD, path=f"/arestas/{id_aresta}", value=valor)


def _banco_com_tarefa(banco: Path) -> None:
    """O banco do usuário com a Task e o alvo dela."""
    banco.parent.mkdir(parents=True, exist_ok=True)
    operacoes = (
        _no("proj", TipoNo.PROJETO), _no("setor", TipoNo.SETOR), _no("sess", TipoNo.SESSAO),
        _no("task-1", TipoNo.TASK, arquivos_alvo=["src/alvo.py"]),
        _aresta("proj", "setor", TipoAresta.CONTEM), _aresta("setor", "sess", TipoAresta.CONTEM),
        _aresta("sess", "task-1", TipoAresta.PRODUZ),
    )
    dados = DadosPropostaPatch(autor="david", papel=PapelAutor.HUMANO, operacoes=operacoes, justificativa="cenario")
    with SQLiteEventStore(str(banco)) as store:
        assert montar_kernel_sqlite(store).submeter_patch(PropostaPatch.criar(dados)).sucesso


def test_transcricoes_saem_da_mais_cara_com_leituras_fora_do_alvo_nominal(tmp_path: Path) -> None:
    """A pasta é varrida, a mais cara vem primeiro, e o alvo da Task sai do banco sem escrever nele."""
    banco = tmp_path / "graphow" / "graphow.db"
    _banco_com_tarefa(banco)
    antes = banco.read_bytes()
    _transcricao(tmp_path / "proj" / "sess" / "subagents" / "agent-barato.jsonl", "task-1", 10)
    _transcricao(tmp_path / "proj" / "sess" / "subagents" / "agent-caro.jsonl", "task-1", 1000)

    linhas = _executar(["transcricao-medir", str(tmp_path / "proj"), "--top", "1"], tmp_path).linhas

    assert linhas[0] == "Transcricoes: 2 lidas; as 1 mais caras:"
    assert linhas[1].startswith("  sess/agent-caro [principal] | tokens 2.000")
    assert "maior saida 3.000 car, 1 saidas >2k | >2k: Bash 1 | 1 pausas >5min (maior 10 min) | 1 leituras fora do alvo" in linhas[1]
    assert "turnos max" not in linhas[1]
    assert any(linha.startswith("  contexto: ") and "turnos max 2" in linha for linha in linhas)
    assert any(linha.startswith("Agregado: 2 transcricoes | tokens 2.020") for linha in linhas)
    assert "  leituras fora do alvo medidas em 2 de 2 transcricoes" in linhas
    assert banco.read_bytes() == antes


def test_sem_banco_a_leitura_fora_do_alvo_fica_de_fora_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem banco, a métrica some e o banco não é criado."""
    arquivo = _transcricao(tmp_path / "t.jsonl", "task-1", 10)

    linhas = _executar(["transcricao-medir", str(arquivo)], tmp_path).linhas

    assert linhas[1].startswith("  t.jsonl [principal]")
    assert "fora do alvo" not in linhas[1]
    assert not (tmp_path / "graphow" / "graphow.db").exists()
