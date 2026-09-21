"""O consumo lido da transcrição: cada mensagem do modelo conta uma vez, e o que não se lê não vira número."""

import json
from pathlib import Path

from graphow.harness.transcricao import ler_consumo, localizar_transcricao_do_subagente


def _resposta(id_mensagem: str, uso: dict[str, int], modelo: str = "claude-sonnet-5", conteudo: list | None = None) -> str:
    """Uma entrada de resposta do modelo como o ambiente a grava."""
    mensagem = {"id": id_mensagem, "model": modelo, "usage": uso, "content": conteudo or [{"type": "text", "text": "ok"}]}
    return json.dumps({"type": "assistant", "message": mensagem})


def _assumir(id_task: str) -> dict:
    """O bloco de chamada a `assumir_tarefa` de um servidor graphow."""
    return {"type": "tool_use", "name": "mcp__graphow-executor__assumir_tarefa", "input": {"id_task": id_task}}


def _gravar(caminho: Path, linhas: list[str]) -> Path:
    """Escreve a transcrição, uma entrada por linha."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def test_mensagem_repetida_por_bloco_conta_uma_vez_nominal(tmp_path: Path) -> None:
    """O ambiente repete o usage em cada bloco da mesma mensagem; a soma não pode dobrar."""
    uso = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", uso),
        _resposta("msg-1", uso, conteudo=[_assumir("task-a")]),
        _resposta("msg-2", {"input_tokens": 1, "output_tokens": 2}),
        json.dumps({"type": "user", "message": {"role": "user", "content": "oi"}}),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.tokens == {"tokens_entrada": 11, "tokens_saida": 7, "tokens_cache_leitura": 100, "tokens_cache_criacao": 7}
    assert consumo.mensagens_de_modelo == 2
    assert consumo.tarefas == ("task-a",)
    assert consumo.modelo_principal == "claude-sonnet-5"


def test_modelo_sintetico_e_linha_quebrada_nao_contam_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a mensagem sintética do ambiente não é modelo, e linha ilegível é pulada."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", {"input_tokens": 3}, modelo="<synthetic>"),
        '{"type": "assistant", "message": {"usage": ',
        _resposta("msg-2", {"input_tokens": 4}, modelo="claude-opus-5"),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.modelos == ("claude-opus-5",)
    assert consumo.tokens["tokens_entrada"] == 7


def test_transcricao_ausente_devolve_none_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem arquivo, o Run fica sem tokens em vez de ficar com zero inventado."""
    assert ler_consumo(tmp_path / "nao-existe.jsonl") is None


def test_transcricao_do_subagente_sai_da_pasta_da_sessao_nominal(tmp_path: Path) -> None:
    """Sem caminho próprio no payload, a transcrição do subagente mora em <sessao>/subagents."""
    principal = tmp_path / "projeto" / "sess-1.jsonl"
    esperado = _gravar(tmp_path / "projeto" / "sess-1" / "subagents" / "agent-abc123.jsonl", [])

    encontrado = localizar_transcricao_do_subagente({"transcript_path": str(principal)}, "abc123")

    assert encontrado == esperado


def test_caminho_do_agente_no_payload_vence_edge_case(tmp_path: Path) -> None:
    """Caso de borda: se o hook disser onde está a transcrição do agente, é ela que vale."""
    declarado = _gravar(tmp_path / "outro" / "agent-abc123.jsonl", [])
    _gravar(tmp_path / "projeto" / "sess-1" / "subagents" / "agent-abc123.jsonl", [])

    encontrado = localizar_transcricao_do_subagente(
        {"agent_transcript_path": str(declarado), "transcript_path": str(tmp_path / "projeto" / "sess-1.jsonl")},
        "abc123",
    )

    assert encontrado == declarado


def test_transcricao_principal_nunca_passa_pela_do_subagente_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem o arquivo do agente, a transcrição da sessão não é contada no lugar dele."""
    principal = _gravar(tmp_path / "projeto" / "sess-1.jsonl", [_resposta("msg-1", {"input_tokens": 9})])

    assert localizar_transcricao_do_subagente({"transcript_path": str(principal)}, "abc123") is None
