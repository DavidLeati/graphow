"""O consumo lido da transcrição: cada mensagem do modelo conta uma vez, e o que não se lê não vira número."""

import json
from pathlib import Path

import pytest

from graphow.harness.linha_de_cota import CotaDeclarada, ultima_cota
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


def _pedido_do_usuario(conteudo: object) -> str:
    """Uma entrada do usuário, como o prompt de despacho que abre a transcrição do subagente."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": conteudo}})


def test_cota_do_despacho_sai_da_primeira_mensagem_do_usuario_nominal(tmp_path: Path) -> None:
    """A raiz escreve a cota no despacho do condutor; a transcrição dele a traz na primeira entrada."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _pedido_do_usuario([{"type": "text", "text": "Alvo: goal-1\nSessao: sess-1\nCota: 5h 40%, semana 12%"}]),
        _resposta("msg-1", {"input_tokens": 1}),
        _pedido_do_usuario("Cota: 5h 99%, semana 99%"),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.cota_do_despacho == CotaDeclarada(cinco_horas=40, semanal=12)
    assert consumo.cota_do_despacho.em_propriedades("inicio") == {"cota_5h_inicio": 40, "cota_semanal_inicio": 12}


def test_ultima_cota_escrita_pelo_modelo_vale_para_a_parada_nominal(tmp_path: Path) -> None:
    """Na transcrição da raiz, vale a última linha de cota que ela escreveu em texto, não a do prompt de despacho."""
    despacho = {"type": "tool_use", "id": "t1", "name": "Agent", "input": {"prompt": "Alvo: g\nCota: 5h 1%, semana 1%"}}
    caminho = _gravar(tmp_path / "t.jsonl", [
        _pedido_do_usuario("orquestre o goal-1"),
        _resposta("msg-1", {"input_tokens": 1}, conteudo=[{"type": "text", "text": "Cota: 5h 50%, semana 20%"}]),
        _resposta("msg-2", {"input_tokens": 1}, conteudo=[despacho]),
        _resposta("msg-3", {"input_tokens": 1}, conteudo=[{"type": "text", "text": "Parei.\nCota: 5h 86%, semana 31%"}]),
        _resposta("msg-4", {"input_tokens": 1}, conteudo=[{"type": "text", "text": "Mais alguma coisa?"}]),
    ])

    consumo = ler_consumo(caminho)

    assert consumo is not None
    assert consumo.ultima_cota_escrita == CotaDeclarada(cinco_horas=86, semanal=31)
    assert consumo.cota_do_despacho is None


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("Cota: 5h 40%, semana 12%", CotaDeclarada(40, 12)),
        ("cota:5h 40 , semana 12", CotaDeclarada(40, 12)),
        ("Cota:  5 h 40,5 %,  semana 12,25%", CotaDeclarada(40.5, 12.25)),
        ("**Cota:** 5h 7.5%; semanal 3%", CotaDeclarada(7.5, 3)),
        ("Cota: 5h 10%, semana 2%\nCota: 5h 30%, semana 4%", CotaDeclarada(30, 4)),
    ],
)
def test_linha_de_cota_tolera_o_formato_de_gente_nominal(texto: str, esperada: CotaDeclarada) -> None:
    """O `%` é opcional, a vírgula decimal vale, e espaço e caixa não importam; vale a última linha."""
    assert ultima_cota(texto) == esperada


@pytest.mark.parametrize("texto", ["", "Cota: alta", "5h 40%, semana 12%", "Cota: 5h 40%"])
def test_texto_sem_linha_de_cota_nao_inventa_numero_edge_case(texto: str) -> None:
    """Caso de borda: sem os dois percentuais depois de `Cota:`, não há cota."""
    assert ultima_cota(texto) is None


def test_cota_com_marcador_e_negrito_conta_nominal() -> None:
    """A linha de cota pode vir como item de lista e com ênfase, como a raiz a escreve no resumo."""
    assert ultima_cota("Parei.\n- **Cota:** 5h 86%, semana 31%") == CotaDeclarada(86, 31)


def test_cota_citada_numa_linha_humano_nao_conta_edge_case() -> None:
    """Caso de borda: a instrução literal do humano que cita uma cota no meio da linha não é a leitura da raiz."""
    assert ultima_cota("Alvo: goal-1\nHumano: segue so ate a cota: 5h 80%, semana 20%") is None


def test_cota_real_vence_a_citada_numa_linha_humano_depois_dela_edge_case() -> None:
    """Caso de borda: com a linha `Humano:` depois da `Cota:`, vale a leitura real, não a cota citada."""
    texto = "Alvo: goal-1\nSessao: sess-1\nCota: 5h 40%, semana 12%\nHumano: para quando a cota: 5h 80%, semana 20%"

    assert ultima_cota(texto) == CotaDeclarada(40, 12)


def _com_instante(linha: str, instante: str) -> str:
    """A mesma entrada com o instante em que o ambiente a gravou."""
    return json.dumps({**json.loads(linha), "timestamp": instante})


def _chamada(nome: str, id_chamada: str, **entrada: str) -> dict:
    """Um bloco de chamada de ferramenta."""
    return {"type": "tool_use", "id": id_chamada, "name": nome, "input": entrada}


def _resultado(id_chamada: str, conteudo: object) -> str:
    """A resposta de uma ferramenta, com o conteúdo em texto solto ou em blocos."""
    bloco = {"type": "tool_result", "tool_use_id": id_chamada, "content": conteudo}
    return json.dumps({"type": "user", "message": {"role": "user", "content": [bloco]}})


def test_forma_do_contexto_conta_cada_mensagem_e_cada_resposta_uma_vez_nominal(tmp_path: Path) -> None:
    """Contexto por turno, saídas grandes, pausa longa e caminhos lidos, sem dobrar a mensagem repetida por bloco."""
    uso_1 = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 90}
    uso_2 = {"input_tokens": 2, "output_tokens": 1, "cache_read_input_tokens": 398}
    leitura = _chamada("Read", "toolu_r", file_path="C:/Repo/src/a.py")
    busca = _chamada("Grep", "toolu_g", pattern="x", path="src")
    caminho = _gravar(tmp_path / "t.jsonl", [
        _com_instante(_resposta("msg-1", uso_1), "2026-10-01T10:00:00.000Z"),
        _com_instante(_resposta("msg-1", uso_1, conteudo=[leitura, busca]), "2026-10-01T10:00:05.000Z"),
        _resultado("toolu_r", "x" * 2500),
        _resultado("toolu_g", [{"type": "text", "text": "y" * 300}, {"type": "text", "text": "z" * 1800}]),
        _com_instante(_resposta("msg-2", uso_2, conteudo=[_chamada("Read", "toolu_r2", file_path="C:/Repo/src/a.py")]), "2026-10-01T10:06:06.000Z"),
        _resultado("toolu_r2", "pequeno"),
    ])

    propriedades = ler_consumo(caminho).em_propriedades()

    assert (propriedades["contexto_medio_turno"], propriedades["contexto_maximo_turno"]) == (300, 400)
    assert (propriedades["maior_saida_ferramenta"], propriedades["saidas_acima_2000"]) == (2500, 2)
    assert (propriedades["pausas_acima_5min"], propriedades["maior_pausa_s"]) == (1, 361)
    assert propriedades["caminhos_lidos"] == ["C:/Repo/src/a.py", "src"]


def test_transcricao_sem_forma_nao_inventa_propriedade_edge_case(tmp_path: Path) -> None:
    """Caso de borda: sem ferramenta, sem instante e com a mensagem sintética zerada, nada da forma vira zero."""
    caminho = _gravar(tmp_path / "t.jsonl", [_resposta("msg-1", {"input_tokens": 0}, modelo="<synthetic>")])

    propriedades = ler_consumo(caminho).em_propriedades()

    chaves = {"contexto_medio_turno", "maior_saida_ferramenta", "pausas_acima_5min", "maior_pausa_s", "caminhos_lidos"}
    assert not chaves & propriedades.keys()


def test_caminhos_lidos_param_no_limite_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a varredura de um explorador não infla o Run além de 200 caminhos."""
    chamadas = [_chamada("Read", f"toolu_{indice}", file_path=f"f{indice}.py") for indice in range(250)]
    caminho = _gravar(tmp_path / "t.jsonl", [_resposta("msg-1", {"input_tokens": 1}, conteudo=chamadas)])

    caminhos = ler_consumo(caminho).em_propriedades()["caminhos_lidos"]

    assert len(caminhos) == 200
    assert caminhos[0] == "f0.py"


def test_shell_e_saidas_grandes_por_ferramenta_tem_campos_proprios_nominal(tmp_path: Path) -> None:
    """A leitura pelo Bash vai para `caminhos_lidos_shell`, e cada saída grande conta para a ferramenta que a deu."""
    chamadas = [
        _chamada("Bash", "toolu_b", command="cd /c/x; sed -n 1,80p src/a.py; grep -n \"x\" -r src/b.py | head"),
        _chamada("mcp__graphow-executor__ler_vista", "toolu_v", id_no="task-1"),
        _chamada("Read", "toolu_r", file_path="src/c.py"),
    ]
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", {"input_tokens": 1}, conteudo=chamadas),
        _resultado("toolu_b", "b" * 2500),
        _resultado("toolu_v", "v" * 4000),
        _resultado("toolu_r", "r" * 100),
    ])

    propriedades = ler_consumo(caminho).em_propriedades()

    assert propriedades["caminhos_lidos_shell"] == ["src/a.py", "src/b.py"]
    assert propriedades["caminhos_lidos"] == ["src/c.py"]
    assert propriedades["saidas_grandes_por_ferramenta"] == {"Bash": 1, "ler_vista": 1}


def test_sem_saida_grande_nao_ha_contagem_por_ferramenta_edge_case(tmp_path: Path) -> None:
    """Caso de borda: saídas pequenas não deixam um dicionário vazio no Run."""
    caminho = _gravar(tmp_path / "t.jsonl", [
        _resposta("msg-1", {"input_tokens": 1}, conteudo=[_chamada("Bash", "toolu_b", command="ls")]),
        _resultado("toolu_b", "pouco"),
    ])

    propriedades = ler_consumo(caminho).em_propriedades()

    assert "saidas_grandes_por_ferramenta" not in propriedades
    assert "caminhos_lidos_shell" not in propriedades
