"""Regras da medição: a primeira entrada de cada mensagem, o corte no tempo e o custo acumulado da sessão retomada."""

from datetime import datetime, timezone
import json
from pathlib import Path

from graphow.bancada.medicao import Invocacao, invocacoes_do_log, medir, minutos_das_invocacoes
from graphow.bancada.transcricoes import contar_tokens, localizar_transcricoes
from graphow.sessoes.leitura_stream import ResultadoDoStream, UsoDeTokens


def _instante(minuto: int) -> datetime:
    """Um instante de 11/10/2026 às 10h, mais os minutos."""
    return datetime(2026, 10, 11, 10, minuto, tzinfo=timezone.utc)


def _entrada(id_mensagem: str, minuto: int, saida: int, entrada: int = 100) -> dict[str, object]:
    """Uma entrada de resposta do modelo na transcrição."""
    uso = {"input_tokens": entrada, "output_tokens": saida, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    return {"type": "assistant", "timestamp": _instante(minuto).isoformat(), "message": {"id": id_mensagem, "usage": uso}}


def _transcricao(caminho: Path, entradas: list[dict[str, object]]) -> Path:
    """Grava a transcrição, uma entrada por linha."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("".join(json.dumps(entrada) + "\n" for entrada in entradas), encoding="utf-8")
    return caminho


def _resultado(sessao: str, custo: float, tokens: int) -> ResultadoDoStream:
    """Um resultado com o `modelUsage` todo em entrada."""
    return ResultadoDoStream(sessao, "", False, "success", custo, 1, None, {"opus": UsoDeTokens(entrada=tokens)})


def _invocacao(sessao: str, minutos: tuple[int, int], custo: float, tokens: int) -> Invocacao:
    """Uma invocação com instantes e resultado."""
    return Invocacao(sessao, _instante(minutos[0]), _instante(minutos[1]), _resultado(sessao, custo, tokens))


def test_mensagem_repetida_conta_pela_primeira_entrada_e_confere_pela_ultima_nominal(tmp_path: Path) -> None:
    """O Claude Code repete a mensagem por bloco, e só a última traz a saída final."""
    caminho = _transcricao(tmp_path / "t.jsonl", [_entrada("m1", 1, 5), _entrada("m1", 1, 50), _entrada("m2", 2, 7)])

    tokens = contar_tokens([caminho])

    assert (tokens.pela_primeira, tokens.pela_ultima, tokens.arquivos) == (100 + 5 + 100 + 7, 100 + 50 + 100 + 7, 1)


def test_corte_no_tempo_deixa_de_fora_o_que_veio_depois_edge_case(tmp_path: Path) -> None:
    """Caso de borda: medir só as primeiras invocações de uma sessão retomada corta a transcrição no fim delas."""
    caminho = _transcricao(tmp_path / "t.jsonl", [_entrada("m1", 1, 0), _entrada("m2", 30, 0)])

    assert contar_tokens([caminho], ate=_instante(10)).pela_primeira == 100


def test_transcricoes_da_sessao_em_qualquer_pasta_de_projeto_nominal(tmp_path: Path) -> None:
    """A da sessão e as dos subagentes, por id, sem depender do nome da pasta do projeto."""
    principal = _transcricao(tmp_path / "C--qualquer" / "s-1.jsonl", [])
    subagente = _transcricao(tmp_path / "C--qualquer" / "s-1" / "subagents" / "agent-a.jsonl", [])
    _transcricao(tmp_path / "C--outra" / "s-2.jsonl", [])

    assert localizar_transcricoes(tmp_path, "s-1") == (principal, subagente)
    assert localizar_transcricoes(tmp_path, "") == ()
    assert localizar_transcricoes(tmp_path / "nao-existe", "s-1") == ()


def test_sessao_retomada_vale_o_ultimo_custo_quando_a_transcricao_confirma_nominal(tmp_path: Path) -> None:
    """O `modelUsage` do último resultado bate com a transcrição: o resultado é acumulado, e o custo é o último."""
    _transcricao(tmp_path / "p" / "s.jsonl", [_entrada("m1", 1, 0), _entrada("m2", 21, 0), _entrada("m3", 22, 0)])
    invocacoes = (_invocacao("s", (0, 5), 1.0, 100), _invocacao("s", (20, 25), 3.0, 300))

    medicao = medir(invocacoes, tmp_path)

    assert medicao.custo_usd == 3.0
    assert medicao.tokens == 300
    assert medicao.minutos == 25.0


def test_sessao_que_nao_acumulou_soma_os_custos_edge_case(tmp_path: Path) -> None:
    """Caso de borda: a transcrição bate com a soma dos resultados; cada invocação contou só a si."""
    _transcricao(tmp_path / "p" / "s.jsonl", [_entrada("m1", 1, 0), _entrada("m2", 21, 0), _entrada("m3", 22, 0), _entrada("m4", 23, 0)])
    invocacoes = (_invocacao("s", (0, 5), 1.0, 100), _invocacao("s", (20, 25), 3.0, 300))

    assert medir(invocacoes, tmp_path).custo_usd == 4.0


def test_sem_transcricao_o_acumulado_que_cresce_vale_o_ultimo_edge_case() -> None:
    """Caso de borda: sem transcrição, custo que só cresce é acumulado; os tokens saem do `modelUsage`."""
    invocacoes = (_invocacao("s", (0, 5), 1.0, 100), _invocacao("s", (20, 25), 3.0, 300))

    medicao = medir(invocacoes, None)

    assert (medicao.custo_usd, medicao.tokens, medicao.fonte_dos_tokens) == (3.0, 300, "model_usage")


def test_sem_transcricao_custo_que_diminui_nao_e_acumulado_edge_case() -> None:
    """Caso de borda: um acumulado nunca diminui; se diminuiu, cada invocação contou só a si."""
    invocacoes = (_invocacao("s", (0, 5), 3.0, 300), _invocacao("s", (20, 25), 1.0, 100))

    medicao = medir(invocacoes, None)

    assert (medicao.custo_usd, medicao.tokens) == (4.0, 400)


def test_sessoes_distintas_se_somam_e_a_sem_transcricao_marca_a_fonte_nominal(tmp_path: Path) -> None:
    """Duas sessões (planejador e executor, por exemplo): custos somados; uma sem transcrição deixa a fonte mista."""
    _transcricao(tmp_path / "p" / "a.jsonl", [_entrada("m1", 1, 0)])
    invocacoes = (_invocacao("a", (0, 5), 1.0, 999), _invocacao("b", (5, 10), 2.0, 50))

    medicao = medir(invocacoes, tmp_path)

    assert (medicao.custo_usd, medicao.tokens, medicao.sessoes) == (3.0, 100 + 50, ("a", "b"))
    assert medicao.fonte_dos_tokens == "transcricoes_e_model_usage"


def test_invocacao_que_morreu_conta_os_tokens_da_transcricao_edge_case(tmp_path: Path) -> None:
    """Caso de borda: tempo esgotado, sem resultado; o custo é desconhecido (zero), mas os tokens gastos contam."""
    _transcricao(tmp_path / "p" / "s.jsonl", [_entrada("m1", 1, 0)])

    medicao = medir((Invocacao("s", _instante(0), _instante(9), None),), tmp_path)

    assert (medicao.custo_usd, medicao.tokens, medicao.sessoes) == (0.0, 100, ("s",))


def test_log_do_laboratorio_vira_invocacoes_pelas_marcas_nominal() -> None:
    """Cada par de marcas é uma invocação; a sessão vem do init quando o resultado não chegou."""
    linhas = [
        {"_lab": "inicio", "quando": "2026-10-10T13:16:11-03:00"},
        {"type": "system", "subtype": "init", "session_id": "s-1"},
        {"type": "result", "session_id": "s-1", "total_cost_usd": 0.5},
        {"_lab": "fim", "quando": "2026-10-10T13:16:55-03:00", "exit": 0},
        {"_lab": "inicio", "quando": "2026-10-10T13:17:23-03:00"},
        {"type": "system", "subtype": "init", "session_id": "s-1"},
        {"_lab": "fim", "quando": "2026-10-10T13:20:23-03:00", "exit": 1},
    ]

    invocacoes = invocacoes_do_log(json.dumps(linha) for linha in linhas)

    assert [invocacao.sessao for invocacao in invocacoes] == ["s-1", "s-1"]
    assert invocacoes[0].resultado is not None and invocacoes[1].resultado is None
    assert minutos_das_invocacoes(invocacoes) == 4.2


def test_stream_sem_marcas_tem_uma_invocacao_por_resultado_sem_minutos_edge_case() -> None:
    """Caso de borda: um stream da bancada lido sozinho não diz quando começou; os minutos ficam em aberto."""
    linhas = [json.dumps({"type": "result", "session_id": sessao, "total_cost_usd": 1.0}) for sessao in ("a", "b")]

    invocacoes = invocacoes_do_log(linhas)

    assert [invocacao.sessao for invocacao in invocacoes] == ["a", "b"]
    assert minutos_das_invocacoes(invocacoes) is None
    assert minutos_das_invocacoes(()) is None
