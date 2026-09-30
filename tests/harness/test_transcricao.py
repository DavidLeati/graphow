"""O consumo lido da transcrição: cada mensagem do modelo conta uma vez, e o que não se lê não vira número."""

import json
from pathlib import Path

from graphow.harness.transcricao import ler_consumo, ler_transcricao, localizar_transcricao_do_subagente


def _resposta(id_mensagem: str, uso: dict[str, int], modelo: str = "claude-sonnet-5", conteudo: list | None = None) -> str:
    """Uma entrada de resposta do modelo como o ambiente a grava."""
    mensagem = {"id": id_mensagem, "model": modelo, "usage": uso, "content": conteudo or [{"type": "text", "text": "ok"}]}
    return json.dumps({"type": "assistant", "message": mensagem})


def _assumir(id_task: str, id_chamada: str = "toolu_1") -> dict:
    """O bloco de chamada a `assumir_tarefa` de um servidor graphow."""
    return {"type": "tool_use", "id": id_chamada, "name": "mcp__graphow-executor__assumir_tarefa", "input": {"id_task": id_task}}


def _resposta_da_ferramenta(id_chamada: str, recibo: dict) -> str:
    """A entrada com o resultado da ferramenta, como o ambiente grava a resposta de um servidor MCP."""
    conteudo = [{"type": "text", "text": json.dumps(recibo, indent=2)}]
    bloco = {"type": "tool_result", "tool_use_id": id_chamada, "content": conteudo}
    return json.dumps({"type": "user", "message": {"role": "user", "content": [bloco]}})


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


def test_autores_mcp_mostram_o_servidor_que_reiniciou_nominal(tmp_path: Path) -> None:
    """Cada resposta de `assumir_tarefa` traz o autor da conexão; dois autores no Run são um reinício."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", {"input_tokens": 1}, conteudo=[_assumir("task-a", "toolu_1")]),
        _resposta_da_ferramenta("toolu_1", {"sucesso": True, "id_task": "task-a", "autor": "executor-opus#a1b2c3"}),
        _resposta("msg-2", {"input_tokens": 1}, conteudo=[_assumir("task-a", "toolu_2")]),
        json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": json.dumps({"sucesso": False, "autor": "executor-opus#d4e5f6"})},
        ]}}),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.autores_mcp == ("executor-opus#a1b2c3", "executor-opus#d4e5f6")
    assert consumo.em_propriedades()["autores_mcp"] == ["executor-opus#a1b2c3", "executor-opus#d4e5f6"]
    assert consumo.tarefas == ("task-a",)


def test_resposta_de_outra_ferramenta_nao_da_autor_edge_case(tmp_path: Path) -> None:
    """Caso de borda: só a resposta de `assumir_tarefa` conta, e recibo sem autor ou ilegível não inventa um."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", {"input_tokens": 1}, conteudo=[_assumir("task-a", "toolu_1")]),
        _resposta_da_ferramenta("toolu_1", {"sucesso": True, "id_task": "task-a"}),
        _resposta_da_ferramenta("toolu_9", {"sucesso": True, "autor": "revisor#000000"}),
        json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "Error: servidor caiu"},
        ]}}),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.autores_mcp == ()


def _datada(tipo: str, instante: object) -> str:
    """Uma entrada qualquer, sem uso, só com o instante em que o ambiente a gravou."""
    return json.dumps({"type": tipo, "timestamp": instante, "message": {"role": tipo, "content": "..."}})


def test_duracao_sai_da_primeira_e_da_ultima_entrada_datada_nominal(tmp_path: Path) -> None:
    """A janela vai da primeira à última entrada com instante, ainda que nenhuma das duas traga uso."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _datada("user", "2026-09-29T14:03:11.123Z"),
        _resposta("msg-1", {"input_tokens": 1}),
        _datada("assistant", "2026-09-29T14:20:00Z"),
        _datada("user", "2026-09-29T15:03:12.123+00:00"),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    propriedades = consumo.em_propriedades()
    assert propriedades["inicio"] == "2026-09-29T14:03:11.123Z"
    assert propriedades["fim"] == "2026-09-29T15:03:12.123Z"
    assert propriedades["duracao_s"] == 3601


def test_ponta_com_instante_ilegivel_cede_a_vizinha_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a ponta sem instante válido não zera a janela; vale a vizinha."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _datada("user", "ontem"),
        _datada("user", "2026-09-29T10:00:00Z"),
        _datada("assistant", "2026-09-29T10:00:42Z"),
        _datada("assistant", 12345),
        '{"type": "assistant", "timestamp": ',
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.em_propriedades()["duracao_s"] == 42


def test_transcricao_sem_instante_nao_grava_duracao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem timestamp nenhum, o Run fica sem as chaves de tempo, e a leitura não quebra."""
    caminho = _gravar(tmp_path / "t.jsonl", [_resposta("msg-1", {"input_tokens": 1})])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert not {"inicio", "fim", "duracao_s"} & set(consumo.em_propriedades())


def test_leitura_separa_o_arquivo_ausente_do_ilegivel_edge_case(tmp_path: Path) -> None:
    """Caso de borda: ausente e ilegível são motivos diferentes; a leitura boa não traz motivo."""
    pasta = tmp_path / "pasta.jsonl"
    pasta.mkdir()
    boa = _gravar(tmp_path / "t.jsonl", [_resposta("msg-1", {"input_tokens": 1})])

    assert ler_transcricao(tmp_path / "nao-existe.jsonl").motivo_sem_consumo == "transcricao_ausente"
    assert ler_transcricao(pasta).motivo_sem_consumo == "erro_de_leitura"
    assert ler_transcricao(boa).motivo_sem_consumo == ""
