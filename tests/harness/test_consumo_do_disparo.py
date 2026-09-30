"""O que cada disparo grava no Run: consumo e duração lidos da transcrição, ou o motivo de não haver consumo."""

import json
from pathlib import Path

import pytest

from graphow.harness.consumo_do_disparo import descrever_disparo, ler_disparo
from graphow.harness.entrada_hook import EntradaDeHook
from graphow.harness.servico_harness import FaseDoHarness, PedidoDeCicloDeVida, ServicoHarness
from graphow.kernel.composicao import montar_kernel_em_memoria


def _gravar(caminho: Path, entradas: list[dict]) -> Path:
    """Escreve a transcrição, uma entrada por linha."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(json.dumps(entrada) for entrada in entradas) + "\n", encoding="utf-8")
    return caminho


def _resposta(instante: str) -> dict:
    """Uma resposta do modelo, datada."""
    mensagem = {"id": f"m-{instante}", "model": "claude-opus-5", "usage": {"input_tokens": 3}, "content": []}
    return {"type": "assistant", "timestamp": instante, "message": mensagem}


def _gravar_run(fase: FaseDoHarness, entrada: EntradaDeHook) -> dict:
    """Passa o disparo pelo mesmo caminho do hook, até o Run gravado, e devolve as propriedades dele."""
    kernel = montar_kernel_em_memoria()
    leitura = ler_disparo(fase, entrada)
    metadados = descrever_disparo(fase, entrada, leitura.consumo, motivo_sem_consumo=leitura.motivo_sem_consumo)
    pedido = PedidoDeCicloDeVida(
        fase=fase,
        id_sessao="sess-1",
        metadados=metadados,
        id_agente=entrada.id_agente if fase == FaseDoHarness.SUBAGENTE else "",
    )
    recibo = ServicoHarness(kernel).registrar(pedido)
    run = kernel.obter_view().obter_no(recibo.id_run)
    assert run is not None
    return dict(run.propriedades)


def test_subagente_grava_a_duracao_da_transcricao_nominal(tmp_path: Path) -> None:
    """O Run do subagente é um evento só; início, fim e duração vêm das pontas da transcrição."""
    principal = tmp_path / "sess-1.jsonl"
    _gravar(tmp_path / "sess-1" / "subagents" / "agent-ab12.jsonl", [
        {"type": "user", "timestamp": "2026-09-29T14:00:00.000Z", "message": {"role": "user", "content": "Alvo: goal-1"}},
        _resposta("2026-09-29T14:10:30.500Z"),
    ])
    entrada = EntradaDeHook(id_sessao="sess-1", transcricao=str(principal), id_agente="ab12", tipo_agente="graphow-condutor")

    propriedades = _gravar_run(FaseDoHarness.SUBAGENTE, entrada)

    assert propriedades["inicio"] == "2026-09-29T14:00:00.000Z"
    assert propriedades["fim"] == "2026-09-29T14:10:30.500Z"
    assert propriedades["duracao_s"] == 630
    assert "motivo_sem_consumo" not in propriedades


@pytest.mark.parametrize(
    ("fase", "entrada", "motivo"),
    [
        (FaseDoHarness.SUBAGENTE, EntradaDeHook(id_sessao="sess-1", tipo_agente="Explore"), "sem_agent_id"),
        (FaseDoHarness.SUBAGENTE, EntradaDeHook(id_sessao="sess-1", transcricao="x/sess-1.jsonl", id_agente="zz99"), "transcricao_ausente"),
        (FaseDoHarness.FIM, EntradaDeHook(id_sessao="sess-1"), "sem_transcript_path"),
        (FaseDoHarness.FIM, EntradaDeHook(id_sessao="sess-1", transcricao="x/nao-existe.jsonl"), "transcricao_ausente"),
    ],
)
def test_run_sem_consumo_grava_o_motivo_edge_case(fase: FaseDoHarness, entrada: EntradaDeHook, motivo: str) -> None:
    """Caso de borda: sem tokens, o Run diz o que faltou, em vez do mesmo None para toda causa."""
    propriedades = _gravar_run(fase, entrada)

    assert propriedades["motivo_sem_consumo"] == motivo
    assert "tokens_entrada" not in propriedades


def test_transcricao_que_nao_se_le_grava_erro_de_leitura_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o caminho existe e não se lê (aqui, uma pasta); o motivo é outro que o ausente."""
    pasta = tmp_path / "sess-1.jsonl"
    pasta.mkdir()

    propriedades = _gravar_run(FaseDoHarness.FIM, EntradaDeHook(id_sessao="sess-1", transcricao=str(pasta)))

    assert propriedades["motivo_sem_consumo"] == "erro_de_leitura"


def test_fase_de_inicio_nao_le_nem_grava_motivo_edge_case() -> None:
    """Caso de borda: o início não lê transcrição, então não tem consumo a explicar."""
    leitura = ler_disparo(FaseDoHarness.INICIO, EntradaDeHook(id_sessao="sess-1"))

    assert (leitura.consumo, leitura.motivo_sem_consumo) == (None, "")
