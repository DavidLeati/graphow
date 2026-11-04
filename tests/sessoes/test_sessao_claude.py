"""A sessão roda o executável certo, na pasta certa, com o ambiente limpo, e lê o resultado do stream."""

from collections.abc import Callable
import contextlib
import ctypes
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
from typing import Any

import pytest

from graphow.sessoes.arvore_da_sessao import CRIACAO_DA_SESSAO, prender_a_arvore
from graphow.sessoes.pedido import PedidoDeSessao
from graphow.sessoes.sessao_claude import ExecutorDeSessao, FalhaAoAbrirSessao

from tests.sessoes.apoio import (
    STREAM_DA_ENXUTA,
    ambiente_de_teste,
    chamadas_registradas,
    comando_do_falso,
    criar_executavel_falso,
    esperar_fim,
    processo_vivo,
)

PROMPT: str = "Implemente a demanda descrita em ../spec.md. Não faça perguntas."


def _pedido(tmp_path: Path, **campos: object) -> PedidoDeSessao:
    """Um pedido de sessão Opus com permissão total e banco descartável."""
    pasta = tmp_path / "repo"
    pasta.mkdir(exist_ok=True)
    return PedidoDeSessao(
        prompt=PROMPT,
        pasta=pasta,
        arquivo_stream=tmp_path / "sessoes" / "enxuta.jsonl",
        modelo="opus",
        modo_de_permissao="bypassPermissions",
        banco_graphow=tmp_path / "graphow.db",
        **campos,
    )


def test_sessao_recebe_comando_pasta_entrada_e_ambiente_certos_nominal(tmp_path: Path) -> None:
    """O falso registra o que recebeu; o stream que ele imprimiu fica gravado e lido."""
    registro = tmp_path / "registro"
    executor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(registro))
    pedido = _pedido(tmp_path)

    resultado = executor.rodar(pedido)

    chamada = chamadas_registradas(registro)[0]
    assert chamada["argv"] == ["-p", "--model", "opus", "--permission-mode", "bypassPermissions",
                               "--output-format", "stream-json", "--verbose"]
    assert Path(str(chamada["cwd"])) == pedido.pasta
    assert chamada["stdin"] == PROMPT
    ambiente = chamada["env"]
    assert isinstance(ambiente, dict)
    assert ambiente["GRAPHOW_DB"] == str(tmp_path / "graphow.db")
    assert not [nome for nome in ambiente if nome.upper().startswith("CLAUDE")]
    gravado = pedido.arquivo_stream.read_text(encoding="utf-8").splitlines()
    assert gravado == STREAM_DA_ENXUTA.read_text(encoding="utf-8").splitlines()
    assert pedido.arquivo_erro.is_file()
    assert resultado.session_id == "4cb36a24-6f3f-4ad6-8179-f4aadfd02d53"
    assert resultado.texto_final.startswith("## Relatório")
    assert (resultado.is_error, resultado.codigo_saida, resultado.tempo_esgotado) == (False, 0, False)
    assert round(resultado.custo_usd, 2) == 5.03
    assert resultado.tokens.total == 6_200_140
    assert resultado.turnos == 88


def test_executavel_vem_de_graphow_claude_quando_nao_injetado_nominal(tmp_path: Path) -> None:
    """Sem executável injetado, o executor acha o de `GRAPHOW_CLAUDE` e o comando começa por ele."""
    falso = criar_executavel_falso(tmp_path / "bin")
    registro = tmp_path / "registro"
    executor = ExecutorDeSessao(ambiente=ambiente_de_teste(registro, GRAPHOW_CLAUDE=str(falso)))

    resultado = executor.rodar(_pedido(tmp_path))

    assert resultado.comando[0] == str(falso)
    assert resultado.is_error is False
    assert len(chamadas_registradas(registro)) == 1


def test_resumo_em_dicionario_tem_o_que_a_bancada_grava_nominal(tmp_path: Path) -> None:
    """Instantes do relógio injetado, comando e números do resultado."""
    instantes = iter([datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc), datetime(2026, 10, 11, 10, 20, tzinfo=timezone.utc)])
    executor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r"), lambda: next(instantes))

    resultado = executor.rodar(_pedido(tmp_path))
    resumo = resultado.em_dicionario()

    assert resultado.duracao_s == timedelta(minutes=20).total_seconds()
    assert resumo["inicio"] == "2026-10-11T10:00:00+00:00"
    assert resumo["arquivo_stream"] == "enxuta.jsonl"
    assert resumo["comando"][-3:] == ["--output-format", "stream-json", "--verbose"]
    assert resumo["tokens_model_usage"]["total"] == 6_200_140


def test_tempo_esgotado_mata_o_processo_e_marca_erro_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o falso dorme antes do resultado; a sessão volta no tempo limite, sem resultado."""
    executor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_DORMIR="30"))
    inicio = datetime.now()

    resultado = executor.rodar(_pedido(tmp_path, tempo_limite_s=2.0))

    assert (datetime.now() - inicio).total_seconds() < 20
    assert resultado.tempo_esgotado is True
    assert resultado.is_error is True
    assert resultado.leitura.resultado is None
    assert resultado.session_id == "4cb36a24-6f3f-4ad6-8179-f4aadfd02d53"
    assert (resultado.custo_usd, resultado.tokens, resultado.turnos) == (None, None, None)
    assert resultado.motivo_do_erro == "tempo esgotado, sem evento result no stream"
    resumo = resultado.em_dicionario()
    assert (resumo["custo_usd"], resumo["tokens_model_usage"], resumo["erro"]) == (None, None, resultado.motivo_do_erro)


def test_tempo_esgotado_mata_a_arvore_aberta_por_um_cmd_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o executável é um `.cmd` (no POSIX, um script de shell) que abre o falso, e o falso abre um
    filho, como o claude real abre os servidores que o agente sobe. No tempo esgotado, os dois morrem."""
    falso = criar_executavel_falso(tmp_path / "bin")
    registro = tmp_path / "registro"
    ambiente = ambiente_de_teste(registro, GRAPHOW_TESTE_DORMIR="60", GRAPHOW_TESTE_FILHO="1")
    executor = ExecutorDeSessao((str(falso),), ambiente)

    resultado = executor.rodar(_pedido(tmp_path, tempo_limite_s=3.0))

    chamada = chamadas_registradas(registro)[0]
    assert resultado.tempo_esgotado is True
    assert esperar_fim(int(str(chamada["pid"]))), "o claude aberto pelo .cmd sobreviveu ao tempo esgotado"
    assert esperar_fim(int(str(chamada["pid_do_filho"]))), "o filho que a sessao abriu sobreviveu ao tempo esgotado"


def test_fim_normal_mata_o_filho_que_a_sessao_deixou_vivo_edge_case(tmp_path: Path) -> None:
    """Caso de borda (T3a3.3): a sessão aberta pelo `.cmd` sai bem e deixa vivo um filho, órfão do falso que saiu.

    Ele podia mexer no clone depois da conferência da sessão: morre antes de `rodar` voltar.
    """
    falso = criar_executavel_falso(tmp_path / "bin")
    registro = tmp_path / "registro"
    executor = ExecutorDeSessao((str(falso),), ambiente_de_teste(registro, GRAPHOW_TESTE_FILHO="1"))

    resultado = executor.rodar(_pedido(tmp_path))

    chamada = chamadas_registradas(registro)[0]
    assert (resultado.tempo_esgotado, resultado.codigo_saida) == (False, 0)
    assert not processo_vivo(int(str(chamada["pid_do_filho"]))), "o filho que a sessao deixou sobreviveu ao fim dela"


class _QuedaNoMeio(RuntimeError):
    """A exceção que o teste injeta no meio da espera de `_lancar`, com a sessão e o filho dela vivos."""


def _registro_completo(registro: Path) -> bool:
    """O falso já abriu o filho e gravou o registro inteiro (o JSON lê)."""
    try:
        return bool(chamadas_registradas(registro))
    except (ValueError, OSError):
        return False


def _esperar_registro(registro: Path) -> None:
    """Até o falso gravar o registro, que ele grava depois de abrir o filho."""
    limite = time.monotonic() + 30
    while not _registro_completo(registro) and time.monotonic() < limite:
        time.sleep(0.05)


def _espera_que_cai(original: Callable[..., Any], registro: Path) -> Callable[..., Any]:
    """O `communicate` que entrega o prompt, espera o falso abrir o filho e levanta no meio da espera."""
    def communicate(entrada: bytes | None = None, timeout: float | None = None) -> Any:
        with contextlib.suppress(subprocess.TimeoutExpired):
            original(entrada, timeout=0.1)
        _esperar_registro(registro)
        raise _QuedaNoMeio("o orquestrador caiu no meio da sessao")

    return communicate


def test_excecao_no_meio_da_sessao_nao_deixa_processo_vivo_edge_case(tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso de borda (T3a4.3): a espera de `_lancar` levanta com o `.cmd`, o claude falso e o filho dele vivos.

    A exceção sobe a quem chamou, e nenhum dos três fica vivo: a árvore
    morre no `finally`, também no caminho de erro.
    """
    falso, registro = criar_executavel_falso(tmp_path / "bin"), tmp_path / "registro"
    ambiente = ambiente_de_teste(registro, GRAPHOW_TESTE_DORMIR="60", GRAPHOW_TESTE_FILHO="1")
    executor, abertos = ExecutorDeSessao((str(falso),), ambiente), []
    abrir = ExecutorDeSessao._abrir

    def abrir_com_espera_que_cai(self: ExecutorDeSessao, *argumentos: Any) -> Any:
        processo, arvore = abrir(self, *argumentos)
        abertos.append(processo)
        monkeypatch.setattr(processo, "communicate", _espera_que_cai(processo.communicate, registro))
        return processo, arvore

    monkeypatch.setattr(ExecutorDeSessao, "_abrir", abrir_com_espera_que_cai)
    with pytest.raises(_QuedaNoMeio):
        executor.rodar(_pedido(tmp_path))

    chamada = chamadas_registradas(registro)[0]
    assert esperar_fim(abertos[0].pid), "o .cmd da sessao sobreviveu a excecao"
    assert esperar_fim(int(str(chamada["pid"]))), "o claude aberto pelo .cmd sobreviveu a excecao"
    assert esperar_fim(int(str(chamada["pid_do_filho"]))), "o filho que a sessao abriu sobreviveu a excecao"


@pytest.mark.skipif(os.name != "nt", reason="Job Object do Windows")
def test_alca_do_job_fechada_sem_terminate_mata_a_arvore_edge_case(tmp_path: Path) -> None:
    """Caso de borda (T3a4): o job leva `KILL_ON_JOB_CLOSE`. Se o orquestrador morre no meio, o Windows fecha a alça
    do job sem `TerminateJobObject`, e o claude aberto pelo `.cmd` e o filho dele morrem com ela."""
    falso, registro = criar_executavel_falso(tmp_path / "bin"), tmp_path / "registro"
    ambiente = ambiente_de_teste(registro, GRAPHOW_TESTE_DORMIR="60", GRAPHOW_TESTE_FILHO="1")
    processo = subprocess.Popen([str(falso)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, env=ambiente,
                                creationflags=CRIACAO_DA_SESSAO)
    try:
        arvore = prender_a_arvore(processo)
        _esperar_registro(registro)
        assert arvore.job is not None
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(arvore.job))
        chamada = chamadas_registradas(registro)[0]
        assert esperar_fim(int(str(chamada["pid"]))), "o claude sobreviveu a alca do job fechada"
        assert esperar_fim(int(str(chamada["pid_do_filho"]))), "o filho sobreviveu a alca do job fechada"
    finally:
        processo.kill()


def test_codigo_de_saida_diferente_de_zero_e_erro_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o resultado diz sucesso, mas o processo saiu com 3; vale o erro."""
    executor = ExecutorDeSessao(comando_do_falso(), ambiente_de_teste(tmp_path / "r", GRAPHOW_TESTE_SAIDA="3"))

    resultado = executor.rodar(_pedido(tmp_path))

    assert resultado.codigo_saida == 3
    assert resultado.is_error is True
    assert resultado.motivo_do_erro == "codigo de saida 3"
    assert resultado.custo_usd is not None and round(resultado.custo_usd, 2) == 5.03


def test_executavel_que_nao_abre_recusa_com_o_comando_edge_case(tmp_path: Path) -> None:
    """Caso de borda: o caminho não existe; a recusa é de domínio, não um `FileNotFoundError` solto."""
    executor = ExecutorDeSessao((str(tmp_path / "nao-existe.exe"),), ambiente_de_teste(tmp_path / "r"))

    with pytest.raises(FalhaAoAbrirSessao) as recusa:
        executor.rodar(_pedido(tmp_path))

    assert "nao-existe" in recusa.value.contexto["comando"]


def test_comando_de_mostra_a_linha_sem_rodar_nominal(tmp_path: Path) -> None:
    """A linha de comando sai do pedido sem lançar processo nem criar o stream."""
    pedido = _pedido(tmp_path)

    comando = ExecutorDeSessao(("claude.exe",), {}).comando_de(pedido)

    assert comando[:2] == ("claude.exe", "-p")
    assert not pedido.arquivo_stream.exists()
